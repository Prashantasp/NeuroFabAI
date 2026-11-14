"""Bounded execution of durable database jobs, claimed with workspace locks."""
from concurrent.futures import ThreadPoolExecutor
import logging
import threading

from sqlalchemy import select
from app.models.document import Document, DocumentStatus
from app.models.document_cleanup import DocumentCleanup

logger = logging.getLogger(__name__)
MAX_WORKERS = 2
MAX_PENDING = 32
RECOVERY_INTERVAL_SECONDS = 10
IN_FLIGHT_STATUSES = tuple(status for status in DocumentStatus if not status.is_terminal)


class TaskService:
    def __init__(self):
        self._executor = None
        self._lock = threading.Lock()
        self._pending = set()
        self._stop = threading.Event()
        self._recovery_thread = None

    def enqueue_document_processing(self, *, document_id, workspace_id, user_id=None):
        from app.tasks.document_tasks import process_document_pipeline
        with self._lock:
            if document_id in self._pending or len(self._pending) >= MAX_PENDING:
                return False
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="neurofab-ingest")
            self._pending.add(document_id)
            executor = self._executor

        def run():
            try:
                process_document_pipeline(document_id, workspace_id, user_id)
            except Exception:
                logger.exception("Ingestion crashed for %s", document_id)
            finally:
                with self._lock:
                    self._pending.discard(document_id)
        try:
            executor.submit(run)
        except RuntimeError:
            with self._lock:
                self._pending.discard(document_id)
            return False
        return True

    def recover_stuck_documents(self):
        from app.db.session import SessionLocal
        requeued = 0
        with SessionLocal() as db:
            rows = db.execute(select(Document.id, Document.workspace_id, Document.owner_id)
                .where(Document.status.in_(IN_FLIGHT_STATUSES))
                .order_by(Document.updated_at, Document.id))
            for document_id, workspace_id, user_id in rows:
                if self.enqueue_document_processing(document_id=document_id, workspace_id=workspace_id, user_id=user_id):
                    requeued += 1
        return requeued

    def recover_cleanup(self):
        from app.db.session import SessionLocal
        from app.services.cleanup_service import cleanup_workspace
        from app.services.workspace_lock import workspace_lock
        with SessionLocal() as db:
            workspaces = db.scalars(select(DocumentCleanup.workspace_id).distinct()).all()
            for workspace_id in workspaces:
                with workspace_lock(db.get_bind(), workspace_id) as acquired:
                    if acquired:
                        cleanup_workspace(db, workspace_id)

    def start(self):
        if self._recovery_thread is not None:
            return
        self._stop.clear()
        def recover():
            while not self._stop.is_set():
                try:
                    self.recover_stuck_documents()
                    self.recover_cleanup()
                except Exception:
                    logger.exception("Background recovery will retry")
                self._stop.wait(RECOVERY_INTERVAL_SECONDS)
        self._recovery_thread = threading.Thread(target=recover, name="neurofab-recovery", daemon=True)
        self._recovery_thread.start()

    def shutdown(self):
        self._stop.set()
        if self._recovery_thread is not None:
            self._recovery_thread.join()
            self._recovery_thread = None
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        with self._lock:
            self._pending.clear()


task_service = TaskService()
