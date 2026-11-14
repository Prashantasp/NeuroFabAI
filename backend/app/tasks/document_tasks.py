"""Document ingestion pipeline.

Runs out-of-band from the upload request: extract text, chunk, embed, index, then
extract a knowledge graph. Each stage writes its progress to PostgreSQL so the
Knowledge Hub can show real progress and so a failure is attributable to a stage.

Stages degrade independently. A document whose vectors indexed but whose graph
extraction failed is still searchable, and says so, rather than being marked
wholly FAILED.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentStatus, EmbeddingStatus, GraphStatus

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """A stage failed in a way that should mark the document FAILED."""

    def __init__(self, stage: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.retryable = retryable


# -- stage helpers ----------------------------------------------------------


def _set_stage(
    db: Session, doc: Document, status: DocumentStatus, stage: str, progress: int
) -> None:
    doc.status = status
    doc.current_stage = stage
    doc.progress_percentage = progress
    db.commit()
    logger.info("[document %s] %s (%d%%)", doc.id, stage, progress)


def _fail(db: Session, doc: Document, stage: str, message: str, retryable: bool) -> None:
    doc.status = DocumentStatus.FAILED
    doc.current_stage = stage
    doc.failure_stage = stage
    doc.failure_reason = message[:1024]
    doc.error_message = message[:1024]
    doc.retryable = retryable
    doc.completed_at = datetime.now(timezone.utc)
    if doc.embedding_status == EmbeddingStatus.RUNNING:
        doc.embedding_status = EmbeddingStatus.FAILED
    if doc.graph_status == GraphStatus.RUNNING:
        doc.graph_status = GraphStatus.FAILED
    db.commit()
    logger.error("[document %s] FAILED at %s: %s", doc.id, stage, message)


def extract_text(doc: Document) -> Tuple[str, int]:
    """Extract text from the stored PDF. Raises PipelineError on failure."""
    import io

    from app.services.storage import get_storage_provider

    storage = get_storage_provider()
    if not storage.exists(doc.file_path):
        raise PipelineError(
            "TEXT_EXTRACTION",
            "The stored file is missing. Re-upload the document.",
            retryable=False,
        )

    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise PipelineError("TEXT_EXTRACTION", "PDF support is not installed on the server.", retryable=False) from exc

    with storage.open(doc.file_path) as handle:
        raw = handle.read()

    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            # An empty password unlocks many "protected" PDFs; if it does not,
            # we genuinely cannot read the file.
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                raise PipelineError(
                    "TEXT_EXTRACTION",
                    "This PDF is password-protected and cannot be read.",
                    retryable=False,
                )

        pages: List[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # noqa: BLE001 - one bad page is survivable
                logger.warning("[document %s] page extraction failed: %s", doc.id, exc)
                pages.append("")
        text = "\n\n".join(p for p in pages if p.strip())
        page_count = len(reader.pages)
    except PipelineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PipelineError("TEXT_EXTRACTION", f"Could not read this PDF: {exc}", retryable=False) from exc

    if not text.strip():
        # Previously this substituted the placeholder string "Operational Manual
        # for Industrial Assets." and continued, so scanned PDFs produced a
        # knowledge graph about a document that was never read.
        raise PipelineError(
            "TEXT_EXTRACTION",
            "No selectable text found. This looks like a scanned PDF and needs OCR before ingestion.",
            retryable=False,
        )

    return text, page_count


def chunk_text(text: str) -> List[str]:
    """Split into overlapping chunks, preferring paragraph and sentence breaks."""
    settings = get_settings()
    size = settings.CHUNK_SIZE
    overlap = min(settings.CHUNK_OVERLAP, size // 2)

    normalised = "\n".join(line.strip() for line in text.splitlines())
    normalised = "\n".join(filter(None, normalised.split("\n")))
    if not normalised:
        return []

    chunks: List[str] = []
    start = 0
    length = len(normalised)

    while start < length:
        end = min(start + size, length)
        if end < length:
            # Prefer a natural boundary within the last 20% of the window so
            # chunks do not cut mid-sentence.
            window_start = max(start + int(size * 0.8), start + 1)
            boundary = max(
                normalised.rfind("\n", window_start, end),
                normalised.rfind(". ", window_start, end),
            )
            if boundary > start:
                end = boundary + 1

        chunk = normalised[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks


def embed_and_index(doc: Document, chunks: List[str], page_count: int) -> dict:
    from app.services.embeddings import EmbeddingError, get_embedding_provider
    from app.services.vectorstore.base import VectorStoreError
    from app.services.vectorstore.qdrant import QdrantStore
    import uuid as _uuid

    settings = get_settings()
    provider = get_embedding_provider()
    store = QdrantStore(dimension=provider.get_dimension())

    started = time.perf_counter()
    try:
        vectors = provider.embed_texts(chunks)
    except EmbeddingError as exc:
        raise PipelineError("EMBEDDING", str(exc)) from exc
    embed_seconds = time.perf_counter() - started

    ids = [str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{doc.workspace_id}/{doc.id}/{index}")) for index in range(len(chunks))]
    payloads = [
        {
            "chunk_id": chunk_id,
            "chunk_index": index,
            "total_chunks": len(chunks),
            "text": chunk,
            "document_id": doc.id,
            "workspace_id": doc.workspace_id,
            "source_filename": doc.filename,
            "document_title": doc.title,
            "page_count": page_count,
        }
        for index, (chunk_id, chunk) in enumerate(zip(ids, chunks))
    ]

    index_started = time.perf_counter()
    try:
        store.insert_vectors(settings.QDRANT_COLLECTION, ids, vectors, payloads)
    except VectorStoreError as exc:
        raise PipelineError("VECTOR_INDEXING", str(exc)) from exc
    index_seconds = time.perf_counter() - index_started

    return {
        "embedding_seconds": round(embed_seconds, 3),
        "indexing_seconds": round(index_seconds, 3),
        "vector_count": len(ids),
        "embedding_provider": provider.name,
        "embedding_dimension": provider.get_dimension(),
        "average_chunk_chars": round(sum(len(c) for c in chunks) / len(chunks), 1),
    }


def build_knowledge_graph(doc: Document, chunks: List[str]):
    from app.services.graph_service import get_graph_backend
    from app.services.knowledge_extractor import knowledge_extractor
    from app.services.knowledge_validator import knowledge_validator
    from app.services.llm import LLMError

    try:
        extraction = knowledge_extractor.extract_from_chunks(doc.id, chunks)
    except LLMError as exc:
        raise PipelineError("KNOWLEDGE_GRAPH", exc.user_message) from exc

    issues = knowledge_validator.validate(extraction)
    if issues:
        raise PipelineError(
            "KNOWLEDGE_GRAPH", f"Extracted knowledge failed validation: {'; '.join(issues)}"
        )

    return extraction


# -- orchestration ----------------------------------------------------------


def _process_document_pipeline(
    document_id: str, workspace_id: str, user_id: Optional[str] = None
) -> None:
    """Run the full ingestion pipeline for one document.

    Synchronous by design: it is invoked from a background worker thread, and a
    sync function keeps the SQLAlchemy session usage straightforward.
    """
    started = time.perf_counter()
    from app.db.session import SessionLocal
    db: Session = SessionLocal()
    doc: Optional[Document] = None

    try:
        doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.workspace_id == workspace_id)
            .one_or_none()
        )
        if doc is None:
            logger.warning("Document %s not found in workspace %s", document_id, workspace_id)
            return

        if doc.status.is_terminal:
            return
        if doc.started_at is not None:
            doc.retry_count += 1
            if doc.retry_count >= 3:
                _fail(db, doc, "RECOVERY", "Processing was interrupted repeatedly. Please reprocess the document.", True)
                return
        doc.started_at = datetime.now(timezone.utc)
        doc.failure_reason = None
        doc.failure_stage = None

        _set_stage(db, doc, DocumentStatus.VALIDATING, "VALIDATING", 5)
        from app.services.vectorstore.qdrant import QdrantStore
        from app.services.graph_service import get_graph_backend
        QdrantStore().delete_by_document(get_settings().QDRANT_COLLECTION, doc.id, workspace_id)
        get_graph_backend().delete_document_subgraph(doc.id, workspace_id)
        doc.extracted_knowledge = {}
        doc.entity_count = doc.relationship_count = 0
        db.commit()

        _set_stage(db, doc, DocumentStatus.TEXT_EXTRACTION, "TEXT_EXTRACTION", 15)
        text, page_count = extract_text(doc)
        doc.page_count = page_count
        doc.summary = text.strip()[:2000]
        db.commit()

        _set_stage(db, doc, DocumentStatus.CHUNKING, "CHUNKING", 30)
        chunks = chunk_text(text)
        if not chunks:
            raise PipelineError("CHUNKING", "The document produced no usable text chunks.", retryable=False)
        doc.chunk_count = len(chunks)
        db.commit()

        _set_stage(db, doc, DocumentStatus.EMBEDDING, "EMBEDDING", 45)
        doc.embedding_status = EmbeddingStatus.RUNNING
        db.commit()

        _set_stage(db, doc, DocumentStatus.VECTOR_INDEXING, "VECTOR_INDEXING", 60)
        metrics = embed_and_index(doc, chunks, page_count)
        doc.embedding_status = EmbeddingStatus.COMPLETED
        db.commit()

        # From here the document is already searchable. Graph extraction failing
        # degrades the document rather than failing it outright.
        _set_stage(db, doc, DocumentStatus.KNOWLEDGE_GRAPH, "KNOWLEDGE_GRAPH", 80)
        doc.graph_status = GraphStatus.RUNNING
        db.commit()

        graph_error: Optional[str] = None
        try:
            extraction = build_knowledge_graph(doc, chunks)
            doc.extracted_knowledge = extraction.model_dump(mode="json")
            # Persist extraction before touching the derived graph so it can be replayed.
            db.commit()
            get_graph_backend().ingest_extraction(extraction, workspace_id=doc.workspace_id)
            doc.entity_count = len(extraction.entities)
            doc.relationship_count = len(extraction.relationships)
            doc.graph_status = GraphStatus.COMPLETED
        except PipelineError as exc:
            graph_error = exc.message
            doc.graph_status = GraphStatus.FAILED
            doc.extracted_knowledge = {}
            logger.warning("[document %s] graph extraction failed: %s", doc.id, exc.message)

        doc.metadata_json = {
            "page_count": page_count,
            "chunk_count": len(chunks),
            "entity_count": doc.entity_count,
            "relationship_count": doc.relationship_count,
            "performance": metrics,
            "graph_error": graph_error,
        }

        _set_stage(db, doc, DocumentStatus.READY, "READY", 100)
        doc.completed_at = datetime.now(timezone.utc)
        doc.processed_at = doc.completed_at
        doc.processing_duration = round(time.perf_counter() - started, 2)
        doc.retryable = graph_error is not None
        doc.failure_reason = graph_error
        db.commit()

        logger.info("[document %s] pipeline completed in %.2fs", doc.id, doc.processing_duration)

    except PipelineError as exc:
        if doc is not None:
            _fail(db, doc, exc.stage, exc.message, exc.retryable)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Unexpected pipeline failure for document %s", document_id)
        if doc is not None:
            _fail(
                db,
                doc,
                doc.current_stage or "PIPELINE",
                "An unexpected error occurred while processing this document.",
                retryable=True,
            )
    finally:
        db.close()


def process_document_pipeline(document_id: str, workspace_id: str, user_id=None) -> None:
    from app.db.session import SessionLocal
    from app.services.workspace_lock import workspace_lock
    with SessionLocal() as db:
        with workspace_lock(db.get_bind(), workspace_id) as acquired:
            if acquired:
                _process_document_pipeline(document_id, workspace_id, user_id)
