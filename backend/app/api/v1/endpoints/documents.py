from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceContext, get_db, get_workspace_context
from app.core.config import Settings, get_settings
from app.core.rate_limit import upload_rate_limit
from app.models.document import DocumentStatus
from app.schemas.document import DocumentDetailResponse, DocumentResponse
from app.schemas.response import PaginatedResponse, StandardResponse, paginate
from app.services.document_service import document_service
from app.services.storage import get_storage_provider
from app.services.task_service import task_service

router = APIRouter()


@router.post(
    "/upload",
    response_model=StandardResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(upload_rate_limit)],
    summary="Upload a PDF for ingestion",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    settings: Settings = Depends(get_settings),
):
    """Stores the file, then queues ingestion. Returns immediately; poll the
    document's `status` and `progress_percentage` for pipeline progress."""
    # Size is measured server-side; a client-supplied Content-Length is not trusted.
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    document = document_service.upload(
        db,
        ctx,
        title=title,
        filename=file.filename or "document.pdf",
        file_obj=file.file,
        mime_type=file.content_type or "",
        file_size=file_size,
        request_id=getattr(request.state, "request_id", None),
    )

    task_service.enqueue_document_processing(
        document_id=document.id, workspace_id=ctx.workspace_id, user_id=ctx.user_id
    )
    return StandardResponse(data=DocumentResponse.model_validate(document))


@router.get(
    "",
    response_model=PaginatedResponse[DocumentResponse],
    summary="List documents in the active workspace",
)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200),
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    sort: str = Query("uploaded_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    items, total = document_service.list(
        db,
        ctx,
        page=page,
        page_size=page_size,
        search=search,
        doc_status=status_filter,
        sort=sort,
        order=order,
    )
    return paginate(
        [DocumentResponse.model_validate(d) for d in items], page, page_size, total
    )


@router.get(
    "/stats",
    response_model=StandardResponse[dict],
    summary="Document counts for the active workspace",
)
def document_stats(
    db: Session = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)
):
    return StandardResponse(data=document_service.stats(db, ctx))


@router.get(
    "/{document_id}",
    response_model=StandardResponse[DocumentDetailResponse],
    summary="Get one document",
)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    document = document_service.get(db, ctx, document_id)
    return StandardResponse(data=DocumentDetailResponse.model_validate(document))


@router.get("/{document_id}/download", summary="Download the original PDF")
def download_document(
    document_id: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Streamed through the API so the file is never served from a public path;
    workspace membership is checked before a byte is read."""
    document = document_service.get(db, ctx, document_id)
    handle = get_storage_provider().open(document.file_path)

    # Quote the filename so a name containing a quote cannot break out of the
    # Content-Disposition header.
    safe_name = document.filename.replace('"', "")
    return StreamingResponse(
        handle,
        media_type=document.mime_type or "application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(document.file_size),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{document_id}/reprocess",
    response_model=StandardResponse[DocumentResponse],
    dependencies=[Depends(upload_rate_limit)],
    summary="Re-run the ingestion pipeline",
)
def reprocess_document(
    document_id: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    document = document_service.mark_for_retry(db, ctx, document_id)
    task_service.enqueue_document_processing(
        document_id=document.id, workspace_id=ctx.workspace_id, user_id=ctx.user_id
    )
    return StandardResponse(data=DocumentResponse.model_validate(document))


@router.delete(
    "/{document_id}",
    response_model=StandardResponse[dict],
    summary="Delete a document and its derived data",
)
def delete_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    document_service.delete(
        db, ctx, document_id, request_id=getattr(request.state, "request_id", None)
    )
    return StandardResponse(data={"message": "Document deleted."})
