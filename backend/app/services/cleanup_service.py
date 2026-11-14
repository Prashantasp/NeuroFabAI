"""Retry deletion without making removed documents visible during an index outage."""

import logging
from sqlalchemy import select
from app.models.document_cleanup import DocumentCleanup

logger = logging.getLogger(__name__)


def pending_document_ids(workspace_id: str) -> set[str]:
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        return set(db.scalars(select(DocumentCleanup.document_id).where(
            DocumentCleanup.workspace_id == workspace_id
        )))


def queue_cleanup(db, document):
    paths = {document.file_path}
    paths.update(version.file_path for version in document.versions)
    paths.update(version.storage_path for version in document.versions)
    db.add(DocumentCleanup(document_id=document.id, workspace_id=document.workspace_id,
                           file_paths=sorted(path for path in paths if path)))


def cleanup_workspace(db, workspace_id: str) -> int:
    """Caller holds the workspace write lock. Failed rows remain durable and hidden."""
    from app.core.config import get_settings
    from app.services.graph_service import get_graph_backend
    from app.services.vectorstore.qdrant import QdrantStore
    from app.services.storage import get_storage_provider

    completed = 0
    for task in db.scalars(select(DocumentCleanup).where(
        DocumentCleanup.workspace_id == workspace_id
    )).all():
        try:
            QdrantStore().delete_by_document(get_settings().QDRANT_COLLECTION, task.document_id, workspace_id)
            get_graph_backend().delete_document_subgraph(task.document_id, workspace_id)
            storage = get_storage_provider()
            for path in task.file_paths:
                storage.delete(path)
            db.delete(task)
            db.commit()
            completed += 1
        except Exception:
            db.rollback()
            logger.exception("Document cleanup will be retried for %s", task.document_id)
    return completed
