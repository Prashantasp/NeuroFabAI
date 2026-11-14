"""Knowledge graph access.

The backend is resolved lazily. It used to be constructed at import time and
immediately replay every document in Postgres into the graph, which meant
importing any module transitively made network and database calls -- the app
could not start without a database and could not be unit tested at all.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

from app.core.config import get_settings
from app.schemas.knowledge import KnowledgeGraphExtraction
from app.services.graph.base import GraphBackend
from app.services.graph.networkx_backend import NetworkXBackend
from app.services.graph.neo4j_backend import Neo4jBackend
from app.services.graph.view import VisibleGraph

logger = logging.getLogger(__name__)

_backend: Optional[GraphBackend] = None
_lock = threading.Lock()


def _build_backend() -> GraphBackend:
    settings = get_settings()

    if settings.GRAPH_BACKEND == "neo4j":
        try:
            backend = Neo4jBackend()
            if backend.health_check():
                logger.info("Knowledge graph backend: Neo4j at %s", settings.NEO4J_URI)
                return backend
            logger.warning("Neo4j health check failed; falling back to in-memory NetworkX graph.")
        except Exception as exc:  # noqa: BLE001 - fall back rather than fail startup
            if settings.is_production:
                raise ConnectionError("The configured graph server is unavailable") from exc
            logger.warning("Neo4j unavailable (%s); falling back to in-memory NetworkX graph.", exc)

    if settings.is_production:
        raise ConnectionError("Production requires the configured Neo4j server")
    logger.info("Knowledge graph backend: NetworkX (in-memory)")
    return NetworkXBackend()


def get_graph_backend() -> GraphBackend:
    global _backend
    if _backend is None:
        with _lock:
            if _backend is None:
                _backend = _build_backend()
    return VisibleGraph(_backend)


def reset_graph_backend() -> None:
    """Drop the cached backend. Used by tests and by config reloads."""
    global _backend
    with _lock:
        _backend = None


def hydrate_graph_from_db() -> int:
    """Replay persisted extractions into the graph backend.

    PostgreSQL is the source of truth: `documents.extracted_knowledge` holds every
    current extraction. Replay restores the in-memory graph and migrates legacy
    Neo4j nodes to document-scoped ownership. Each document is replaced atomically.
    """
    from app.db.session import SessionLocal
    from app.models.document import Document

    backend = get_graph_backend()

    hydrated = 0
    db = SessionLocal()
    try:
        documents = (
            db.query(Document)
            .filter(Document.extracted_knowledge.isnot(None))
            .yield_per(50)
        )
        for doc in documents:
            payload = doc.extracted_knowledge
            if not payload:
                continue
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("Document %s has unparseable extracted_knowledge", doc.id)
                    continue
            if not (isinstance(payload, dict) and payload.get("entities")):
                continue
            try:
                extraction = KnowledgeGraphExtraction.model_validate(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping document %s during hydration: %s", doc.id, exc)
                continue
            from app.services.workspace_lock import workspace_lock
            with workspace_lock(db.get_bind(), doc.workspace_id) as acquired:
                if acquired:
                    db.refresh(doc)
                    if not doc.status.is_terminal:
                        continue
                    extraction = KnowledgeGraphExtraction.model_validate(doc.extracted_knowledge)
                    backend.ingest_extraction(extraction, workspace_id=doc.workspace_id)
                    hydrated += 1
        logger.info("Hydrated knowledge graph from %d document(s).", hydrated)
    except Exception as exc:  # noqa: BLE001 - never block startup on hydration
        logger.error("Graph hydration failed: %s", exc, exc_info=True)
    finally:
        db.close()
    return hydrated
