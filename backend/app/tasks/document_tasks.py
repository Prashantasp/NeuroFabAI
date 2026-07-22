import asyncio
import logging
import time
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentStatus
from app.db.session import SessionLocal
import PyPDF2

logger = logging.getLogger(__name__)

async def update_status(db: Session, doc: Document, status: DocumentStatus):
    doc.status = status
    db.commit()
    logger.info(f"[Document {doc.id}] Pipeline Stage: {status.value} started")
    await asyncio.sleep(0.5)

def set_failure(db: Session, doc: Document, stage: str, message: str, retryable: bool = False):
    doc.status = DocumentStatus.FAILED
    doc.failure_stage = stage
    doc.error_message = message
    doc.retryable = retryable
    db.commit()
    logger.error(f"[Document {doc.id}] FAILED at {stage}: {message}")

async def process_document_task(document_id: str):
    logger.info(f"[Document {document_id}] Ingestion Pipeline Triggered")
    start_time = time.time()
    
    db: Session = SessionLocal()
    doc = None
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning(f"Document {document_id} not found.")
            return

        # 1. QUEUED -> PARSING
        await update_status(db, doc, DocumentStatus.PARSING)
        
        parsed_text = ""
        page_count = 0
        if os.path.exists(doc.file_path):
            with open(doc.file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        parsed_text += text + "\n"
        else:
            raise FileNotFoundError(f"File {doc.file_path} not found.")
            
        if not parsed_text.strip():
            logger.warning(f"Document {doc.id} contains no extractable text.")
            parsed_text = "Empty Document"
            
        # 2. PARSING -> CHUNKING
        await update_status(db, doc, DocumentStatus.CHUNKING)
        chunk_size = 800
        # Simple overlap chunking
        chunks = [parsed_text[i:i+chunk_size] for i in range(0, len(parsed_text), chunk_size - 100)] if parsed_text else []
        
        # 3. CHUNKING -> ENTITY EXTRACTION
        await update_status(db, doc, DocumentStatus.ENTITY_EXTRACTION)
        from app.services.knowledge_extractor import knowledge_extractor
        from app.services.knowledge_validator import knowledge_validator
        
        extraction = knowledge_extractor.extract_from_chunks(document_id, chunks)
        
        is_valid = knowledge_validator.validate(extraction)
        if not is_valid:
            raise ValueError("Knowledge extraction failed validation.")
        
        doc.extracted_knowledge = extraction.model_dump(mode="json")
        
        # 4. GRAPH CONSTRUCTION
        await update_status(db, doc, DocumentStatus.GRAPH_CONSTRUCTION)
        from app.services.graph_service import graph_service
        graph_service.ingest_extraction(extraction)
        
        extracted_entities = [e.canonical_name for e in extraction.entities if e.type == "Equipment"]
        
        base_metadata = {
            "document_id": document_id,
            "document_type": "PDF",
            "detected_equipment": extracted_entities,
            "upload_timestamp": doc.uploaded_at.isoformat() if doc.uploaded_at else datetime.now(timezone.utc).isoformat(),
            "source_filename": doc.filename,
            "page_count": page_count
        }
        
        # 5. EMBEDDING
        await update_status(db, doc, DocumentStatus.EMBEDDING)
        
        from app.services.embeddings.gemini import GeminiEmbeddingProvider
        from app.services.vectorstore.qdrant import QdrantStore
        from app.services.embedding_service import EmbeddingService
        
        # Use Gemini for real embeddings
        provider = GeminiEmbeddingProvider()
        store = QdrantStore()
        embed_service = EmbeddingService(provider, store)
        
        metrics = embed_service.process_chunks(chunks, base_metadata)
        
        doc_metadata = {
            "page_count": page_count,
            "language": "en",
            "detected_equipment": extracted_entities,
            "document_type": "PDF",
            "extracted_entities_count": len(extraction.entities),
            "chunk_count": len(chunks),
            "embedding_status": "completed",
            "graph_status": "completed",
            "performance_metrics": metrics
        }
        
        doc.metadata_json = doc_metadata
        
        # Finalize
        doc.status = DocumentStatus.READY
        doc.processed_at = datetime.now(timezone.utc)
        doc.processing_duration = round(time.time() - start_time, 2)
        db.commit()
        
        logger.info(f"[Document {document_id}] Pipeline Completed in {doc.processing_duration}s")
        
    except Exception as e:
        logger.error(f"Critical pipeline error for document {document_id}: {e}", exc_info=True)
        if doc:
            set_failure(db, doc, stage="UNKNOWN", message=str(e), retryable=True)
    finally:
        db.close()
