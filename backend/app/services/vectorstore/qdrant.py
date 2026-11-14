"""Qdrant vector store with mandatory workspace filtering."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.config import get_settings
from app.services.vectorstore.base import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

_client: Optional[QdrantClient] = None
_client_lock = threading.Lock()


def get_qdrant_client() -> QdrantClient:
    """Lazily create a shared client.

    Built on first use rather than at import so that importing any service does
    not require a running Qdrant.
    """
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        settings = get_settings()
        if settings.QDRANT_URL:
            try:
                client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=10.0,
                )
                client.get_collections()
                logger.info("Connected to Qdrant at %s", settings.QDRANT_URL)
                _client = client
                return _client
            except Exception as exc:  # noqa: BLE001
                if settings.is_production:
                    raise VectorStoreError("The configured vector server is unavailable") from exc
                logger.warning(
                    "Qdrant unreachable at %s (%s); using embedded local storage at %s",
                    settings.QDRANT_URL, exc, settings.QDRANT_LOCAL_PATH,
                )

        if settings.is_production:
            raise VectorStoreError("Production requires a shared vector server")
        _client = QdrantClient(path=settings.QDRANT_LOCAL_PATH)
        return _client


def reset_qdrant_client() -> None:
    global _client
    with _client_lock:
        _client = None


class QdrantStore(VectorStore):
    def __init__(self, dimension: Optional[int] = None):
        settings = get_settings()
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self._ensured: set[str] = set()

    @property
    def client(self) -> QdrantClient:
        return get_qdrant_client()

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant health check failed: %s", exc)
            return False

    def _ensure_collection(self, collection_name: str) -> None:
        if collection_name in self._ensured:
            return
        try:
            existing = {c.name for c in self.client.get_collections().collections}
            if collection_name not in existing:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension, distance=Distance.COSINE
                    ),
                )
                logger.info(
                    "Created Qdrant collection %s (dim=%d)", collection_name, self.dimension
                )

            # Without a payload index, workspace filtering degrades to a full
            # scan as the collection grows.
            for field in ("workspace_id", "document_id"):
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field,
                        field_schema=PayloadSchemaType.KEYWORD,
                    )
                except Exception:  # noqa: BLE001 - already exists
                    pass

            self._ensured.add(collection_name)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Could not prepare collection {collection_name}: {exc}") from exc

    @staticmethod
    def _workspace_filter(workspace_id: str, document_id: Optional[str] = None) -> Filter:
        conditions = [
            FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id))
        ]
        if document_id:
            conditions.append(
                FieldCondition(key="document_id", match=MatchValue(value=document_id))
            )
        return Filter(must=conditions)

    def insert_vectors(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> None:
        if not ids:
            return
        if not (len(ids) == len(vectors) == len(payloads)):
            raise VectorStoreError("ids, vectors, and payloads must be the same length")

        for payload in payloads:
            if not payload.get("workspace_id"):
                raise VectorStoreError("Every vector payload must carry a workspace_id")

        actual_dim = len(vectors[0])
        if actual_dim != self.dimension:
            # Mismatched dimensions produce an opaque Qdrant error deep in a
            # background task; fail here with something actionable instead.
            raise VectorStoreError(
                f"Embedding dimension {actual_dim} does not match collection dimension "
                f"{self.dimension}. Set EMBEDDING_DIMENSION to {actual_dim} or recreate "
                f"the '{collection_name}' collection."
            )

        self._ensure_collection(collection_name)
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(id=pid, vector=vec, payload=payload)
                    for pid, vec, payload in zip(ids, vectors, payloads)
                ],
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Failed to index vectors: {exc}") from exc

        logger.info("Indexed %d vectors into %s", len(ids), collection_name)

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        workspace_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        if not workspace_id:
            raise VectorStoreError("workspace_id is required for vector search")

        self._ensure_collection(collection_name)
        try:
            hits = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=self._workspace_filter(workspace_id),
                limit=50,
                with_payload=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant search failed on %s: %s", collection_name, exc)
            raise VectorStoreError(f"Vector search failed: {exc}") from exc

        from app.services.cleanup_service import pending_document_ids
        deleted = pending_document_ids(workspace_id)
        return [
            {"id": str(hit.id), "score": float(hit.score), "payload": hit.payload or {}}
            for hit in hits
            if (hit.payload or {}).get("document_id") not in deleted
        ][:max(1, min(limit, 50))]

    def delete_by_document(
        self, collection_name: str, document_id: str, workspace_id: str
    ) -> None:
        if not (document_id and workspace_id):
            return
        self._ensure_collection(collection_name)
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=self._workspace_filter(workspace_id, document_id),
                wait=True,
            )
            logger.info("Deleted vectors for document %s", document_id)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError("Could not remove document vectors") from exc
