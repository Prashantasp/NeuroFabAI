"""Document lifecycle: upload, list, retry, delete."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import BinaryIO, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceContext
from app.core.config import get_settings
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.workspace import WorkspaceMemberRole
from app.services.audit_service import audit_service
from app.services.storage import get_storage_provider
from app.services.cleanup_service import queue_cleanup, cleanup_workspace
from app.services.workspace_lock import serialized_workspace

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}
PDF_MAGIC = b"%PDF-"

SORTABLE_COLUMNS = {
    "uploaded_at": Document.uploaded_at,
    "title": Document.title,
    "file_size": Document.file_size,
    "status": Document.status,
}

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(filename: str) -> str:
    """Reduce an uploaded name to a safe basename.

    Strips any directory component so a filename like `../../etc/passwd` cannot
    escape the storage root, and removes characters that are awkward or unsafe
    on the filesystem.
    """
    base = os.path.basename(filename or "").strip()
    base = base.replace("\x00", "")
    base = _UNSAFE_FILENAME.sub("_", base)
    base = base.lstrip(".") or "document.pdf"
    return base[:200]


class DocumentService:
    # -- validation ---------------------------------------------------------

    @staticmethod
    def _validate(filename: str, mime_type: str, file_obj: BinaryIO, file_size: int) -> None:
        settings = get_settings()

        if file_size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty."
            )
        if file_size > settings.MAX_UPLOAD_BYTES:
            limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File is too large. The maximum size is {limit_mb} MB.",
            )

        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported.",
            )
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported.",
            )

        # Extension and Content-Type are both client-controlled. Check the magic
        # bytes so a renamed executable is not accepted as a PDF.
        file_obj.seek(0)
        header = file_obj.read(len(PDF_MAGIC))
        file_obj.seek(0)
        if header != PDF_MAGIC:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That file is not a valid PDF.",
            )

    @staticmethod
    def _checksum(file_obj: BinaryIO) -> str:
        digest = hashlib.sha256()
        file_obj.seek(0)
        for block in iter(lambda: file_obj.read(65536), b""):
            digest.update(block)
        file_obj.seek(0)
        return digest.hexdigest()

    # -- writes -------------------------------------------------------------

    @serialized_workspace
    def upload(
        self,
        db: Session,
        ctx: WorkspaceContext,
        *,
        title: Optional[str],
        filename: str,
        file_obj: BinaryIO,
        mime_type: str,
        file_size: int,
        request_id: Optional[str] = None,
    ) -> Document:
        ctx.require_role(
            [WorkspaceMemberRole.OWNER, WorkspaceMemberRole.ADMIN, WorkspaceMemberRole.MEMBER]
        )

        safe_name = sanitize_filename(filename)
        self._validate(safe_name, mime_type, file_obj, file_size)

        checksum = self._checksum(file_obj)
        existing = db.execute(
            select(Document).where(
                Document.workspace_id == ctx.workspace_id, Document.checksum == checksum
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{existing.title}' already contains this exact content.",
            )

        document = Document(
            title=(title or safe_name).strip()[:512],
            filename=safe_name,
            file_path="",
            workspace_id=ctx.workspace_id,
            owner_id=ctx.user_id,
            file_size=file_size,
            mime_type=mime_type,
            checksum=checksum,
            version=1,
            status=DocumentStatus.UPLOADING,
        )
        db.add(document)
        db.flush()

        storage = get_storage_provider()
        storage_key = f"{ctx.workspace_id}/{document.id}/v1_{safe_name}"
        try:
            saved_path = storage.save(file_obj, storage_key)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.error("Failed to persist upload %s: %s", safe_name, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store the uploaded file. Please try again.",
            )

        document.file_path = saved_path
        document.status = DocumentStatus.QUEUED
        db.add(
            DocumentVersion(
                document_id=document.id,
                version=1,
                file_path=saved_path,
                storage_path=saved_path,
                file_size=file_size,
                checksum=checksum,
                uploaded_by=ctx.user_id,
            )
        )
        db.commit()
        db.refresh(document)

        audit_service.log_action(
            db,
            action="DOCUMENT_UPLOADED",
            resource_type="document",
            resource_id=document.id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            request_id=request_id,
        )
        return document

    @serialized_workspace
    def mark_for_retry(self, db: Session, ctx: WorkspaceContext, document_id: str) -> Document:
        ctx.require_role(
            [WorkspaceMemberRole.OWNER, WorkspaceMemberRole.ADMIN, WorkspaceMemberRole.MEMBER]
        )
        document = self.get(db, ctx, document_id)

        if document.status not in (DocumentStatus.FAILED, DocumentStatus.READY):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This document is still processing. Wait for it to finish before reprocessing.",
            )

        document.status = DocumentStatus.QUEUED
        document.started_at = None
        document.current_stage = None
        document.progress_percentage = 0
        document.failure_reason = None
        document.failure_stage = None
        document.error_message = None
        document.retryable = False
        document.retry_count = (document.retry_count or 0) + 1
        db.commit()
        db.refresh(document)

        audit_service.log_action(
            db,
            action="DOCUMENT_REPROCESS_REQUESTED",
            resource_type="document",
            resource_id=document.id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
        )
        return document

    @serialized_workspace
    def delete(
        self,
        db: Session,
        ctx: WorkspaceContext,
        document_id: str,
        *,
        request_id: Optional[str] = None,
    ) -> None:
        document = self.get(db, ctx, document_id)
        # Members may delete what they uploaded; admins and owners may delete anything.
        if ctx.role == WorkspaceMemberRole.VIEWER or (
            ctx.role == WorkspaceMemberRole.MEMBER and document.owner_id != ctx.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this document.",
            )

        queue_cleanup(db, document)
        db.delete(document)
        db.commit()
        cleanup_workspace(db, ctx.workspace_id)

        audit_service.log_action(
            db,
            action="DOCUMENT_DELETED",
            resource_type="document",
            resource_id=document_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            request_id=request_id,
        )

    # -- reads --------------------------------------------------------------

    def get(self, db: Session, ctx: WorkspaceContext, document_id: str) -> Document:
        document = db.execute(
            select(Document).where(
                Document.id == document_id, Document.workspace_id == ctx.workspace_id
            )
        ).scalar_one_or_none()
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
            )
        return document

    def list(
        self,
        db: Session,
        ctx: WorkspaceContext,
        *,
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        doc_status: Optional[DocumentStatus] = None,
        sort: str = "uploaded_at",
        order: str = "desc",
    ) -> Tuple[List[Document], int]:
        """Return one page of documents plus the true total.

        The previous implementation reported `total_items = len(current_page)`,
        so `has_next` was always false and pagination silently truncated.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        conditions = [Document.workspace_id == ctx.workspace_id]
        if search:
            term = f"%{search.strip()}%"
            conditions.append(or_(Document.title.ilike(term), Document.filename.ilike(term)))
        if doc_status:
            conditions.append(Document.status == doc_status)

        total = db.scalar(
            select(func.count()).select_from(Document).where(*conditions)
        ) or 0

        column = SORTABLE_COLUMNS.get(sort, Document.uploaded_at)
        ordering = column.asc() if order.lower() == "asc" else column.desc()

        items = list(
            db.execute(
                select(Document)
                .where(*conditions)
                .order_by(ordering, Document.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars()
        )
        return items, total

    def stats(self, db: Session, ctx: WorkspaceContext) -> dict:
        """Aggregate document counts in a single grouped query."""
        rows = db.execute(
            select(Document.status, func.count())
            .where(Document.workspace_id == ctx.workspace_id)
            .group_by(Document.status)
        ).all()

        by_status = {status_value.value: count for status_value, count in rows}
        total = sum(by_status.values())
        ready = by_status.get(DocumentStatus.READY.value, 0)
        failed = by_status.get(DocumentStatus.FAILED.value, 0)

        totals = db.execute(
            select(
                func.coalesce(func.sum(Document.chunk_count), 0),
                func.coalesce(func.avg(Document.processing_duration), 0.0),
                func.coalesce(func.sum(Document.file_size), 0),
            ).where(Document.workspace_id == ctx.workspace_id)
        ).one()

        return {
            "total": total,
            "ready": ready,
            "failed": failed,
            "processing": total - ready - failed,
            "by_status": by_status,
            "total_chunks": int(totals[0] or 0),
            "avg_processing_seconds": round(float(totals[1] or 0.0), 2),
            "total_bytes": int(totals[2] or 0),
        }


document_service = DocumentService()
