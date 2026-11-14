"""Vector retrieval over the workspace-scoped Qdrant collection."""

from __future__ import annotations

from typing import List, Optional

from app.core.config import get_settings
from app.schemas.rag import EvidencePackage, QueryPlan
from app.services.embeddings import get_embedding_provider
from app.services.retrieval.base import RetrievalStrategy
from app.services.vectorstore.qdrant import QdrantStore

DEFAULT_LIMIT = 8


class VectorRetrieval(RetrievalStrategy):
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.QDRANT_COLLECTION
        self.vector_store = QdrantStore()
        self.embedder = get_embedding_provider()

    def retrieve(
        self,
        query: str,
        plan: QueryPlan,
        workspace_id: str,
        limit: int = DEFAULT_LIMIT,
    ) -> EvidencePackage:
        if not workspace_id:
            raise ValueError("workspace_id is required for vector retrieval")

        query_vector = self.embedder.embed_texts([query])[0]
        results = self.vector_store.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=limit,
            workspace_id=workspace_id,
        )

        chunks = [r["payload"] for r in results if r.get("payload")]
        provenance: List[str] = sorted(
            {c["document_id"] for c in chunks if c.get("document_id")}
        )
        confidence = max((r.get("score", 0.0) for r in results), default=0.0)

        return EvidencePackage(
            retrieved_chunks=chunks,
            retrieved_nodes=[],
            retrieved_relationships=[],
            provenance_links=provenance,
            overall_confidence=float(confidence),
        )
