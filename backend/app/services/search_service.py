"""Multi-strategy search across documents, vectors, and the knowledge graph."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.services.embeddings import EmbeddingError, get_embedding_provider
from app.services.entity_resolver import entity_resolver
from app.services.graph_service import get_graph_backend
from app.services.vectorstore.base import VectorStoreError
from app.services.vectorstore.qdrant import QdrantStore

logger = logging.getLogger(__name__)

SearchStrategyName = Literal["keyword", "semantic", "graph", "hybrid"]


class SearchResult(BaseModel):
    id: str
    score: float
    source: SearchStrategyName
    title: str
    snippet: str = ""
    document_id: str | None = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class SearchStrategy(ABC):
    @abstractmethod
    def search(
        self, query: str, limit: int, workspace_id: str, db: Session
    ) -> List[SearchResult]:
        ...


class KeywordSearchStrategy(SearchStrategy):
    def search(self, query, limit, workspace_id, db) -> List[SearchResult]:
        term = f"%{query.strip()}%"
        documents = db.execute(
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                or_(Document.title.ilike(term), Document.filename.ilike(term)),
            )
            .limit(limit)
        ).scalars()

        return [
            SearchResult(
                id=doc.id,
                score=0.75,
                source="keyword",
                title=doc.title or doc.filename,
                # `doc.summary` is a real column now; the previous version read an
                # attribute that did not exist and raised on every keyword search.
                snippet=(doc.summary or "")[:280],
                document_id=doc.id,
                payload={
                    "filename": doc.filename,
                    "status": doc.status.value,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                },
            )
            for doc in documents
        ]


class SemanticSearchStrategy(SearchStrategy):
    def search(self, query, limit, workspace_id, db) -> List[SearchResult]:
        settings = get_settings()
        provider = get_embedding_provider()
        try:
            vector = provider.embed_texts([query])[0]
            hits = QdrantStore(dimension=provider.get_dimension()).search(
                collection_name=settings.QDRANT_COLLECTION,
                query_vector=vector,
                workspace_id=workspace_id,
                limit=limit,
            )
        except (EmbeddingError, VectorStoreError) as exc:
            # One failing strategy must not fail the whole search.
            logger.warning("Semantic search unavailable: %s", exc)
            return []

        results = []
        for hit in hits:
            payload = hit.get("payload") or {}
            results.append(
                SearchResult(
                    id=hit["id"],
                    score=float(hit.get("score", 0.0)),
                    source="semantic",
                    title=payload.get("document_title") or payload.get("source_filename") or "Document excerpt",
                    snippet=(payload.get("text") or "")[:280],
                    document_id=payload.get("document_id"),
                    payload={"chunk_index": payload.get("chunk_index")},
                )
            )
        return results


class GraphSearchStrategy(SearchStrategy):
    def search(self, query, limit, workspace_id, db) -> List[SearchResult]:
        backend = get_graph_backend()
        try:
            topology = backend.get_topology(workspace_id)
            names = entity_resolver.extract_and_resolve(query, topology)
            if not names and query.strip():
                names = [query.strip()]

            results = []
            for name in names[:limit]:
                node = backend.get_node(name, workspace_id)
                if node is None:
                    continue
                subgraph = backend.get_subgraph(name, workspace_id, depth=1)
                results.append(
                    SearchResult(
                        id=name,
                        score=0.9,
                        source="graph",
                        title=name,
                        snippet=(node.get("evidence_snippet") or "")[:280],
                        document_id=node.get("source_document_id") or None,
                        payload={
                            "type": node.get("type"),
                            "connected_count": len(subgraph.get("edges", [])),
                            "neighbours": [
                                n.get("name") for n in subgraph.get("nodes", [])[:10]
                            ],
                        },
                    )
                )
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph search unavailable: %s", exc)
            return []


class HybridSearchStrategy(SearchStrategy):
    def __init__(self) -> None:
        self.strategies = [
            SemanticSearchStrategy(),
            GraphSearchStrategy(),
            KeywordSearchStrategy(),
        ]

    def search(self, query, limit, workspace_id, db) -> List[SearchResult]:
        combined: List[SearchResult] = []
        for strategy in self.strategies:
            combined.extend(strategy.search(query, limit, workspace_id, db))

        # Deduplicate by (document, snippet) keeping the highest-scoring variant,
        # so one document does not fill the page via three strategies.
        best: Dict[Any, SearchResult] = {}
        for result in combined:
            key = (result.source, result.document_id, result.title)
            if key not in best or result.score > best[key].score:
                best[key] = result

        return sorted(best.values(), key=lambda r: r.score, reverse=True)[:limit]


class SearchService:
    def __init__(self) -> None:
        self._strategies: Dict[str, SearchStrategy] = {
            "keyword": KeywordSearchStrategy(),
            "semantic": SemanticSearchStrategy(),
            "graph": GraphSearchStrategy(),
            "hybrid": HybridSearchStrategy(),
        }

    def search(
        self,
        *,
        query: str,
        strategy: str,
        limit: int,
        workspace_id: str,
        db: Session,
    ) -> List[SearchResult]:
        if not query.strip():
            return []
        chosen = self._strategies.get(strategy, self._strategies["hybrid"])
        return chosen.search(query.strip(), max(1, min(limit, 50)), workspace_id, db)


search_service = SearchService()
