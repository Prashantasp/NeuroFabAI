from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceContext, get_db, get_workspace_context
from app.core.rate_limit import chat_rate_limit
from app.schemas.chat import (
    AskRequest,
    AskResponse,
    ConversationDetail,
    ConversationSummary,
    RenameConversationRequest,
)
from app.schemas.response import PaginatedResponse, StandardResponse, paginate
from app.services.chat_service import CopilotUnavailable, chat_service

router = APIRouter()


@router.post(
    "/ask",
    response_model=StandardResponse[AskResponse],
    dependencies=[Depends(chat_rate_limit)],
    summary="Ask the Copilot a question",
)
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Runs the multi-agent GraphRAG workflow over the active workspace only.

    Requires authentication and workspace membership: this endpoint performs
    billed model calls and reads workspace document content.
    """
    try:
        result = chat_service.ask(
            db,
            ctx,
            query=payload.query,
            mode=payload.mode,
            conversation_id=payload.conversation_id,
        )
    except CopilotUnavailable as exc:
        # 503, not 500: the request was valid and the failure is transient or
        # configuration-related, so the client should offer a retry.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        )
    return StandardResponse(data=result)


@router.post(
    "/stream",
    dependencies=[Depends(chat_rate_limit)],
    summary="Ask the Copilot with incremental progress (SSE)",
)
def ask_stream(
    payload: AskRequest,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Server-Sent Events: `conversation`, `timeline`, `decision`/`error`, `done`.

    Streaming here means progressive *reasoning steps* rather than token-level
    output: the answer is a validated structured object, so the useful thing to
    stream is which agent is working and what it found.
    """
    return StreamingResponse(
        chat_service.stream(
            db,
            ctx,
            query=payload.query,
            mode=payload.mode,
            conversation_id=payload.conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # stops nginx buffering the stream
        },
    )


@router.get(
    "/conversations",
    response_model=PaginatedResponse[ConversationSummary],
    summary="List my conversations in this workspace",
)
def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    items, total = chat_service.list_conversations(
        db, ctx, limit=page_size, offset=(page - 1) * page_size
    )
    return paginate(
        [ConversationSummary.model_validate(c) for c in items], page, page_size, total
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=StandardResponse[ConversationDetail],
    summary="Get a conversation with its full history",
)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    conversation = chat_service.get_conversation(db, ctx, conversation_id)
    return StandardResponse(data=ConversationDetail.model_validate(conversation))


@router.patch(
    "/conversations/{conversation_id}",
    response_model=StandardResponse[ConversationSummary],
    summary="Rename a conversation",
)
def rename_conversation(
    conversation_id: str,
    payload: RenameConversationRequest,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    conversation = chat_service.rename_conversation(db, ctx, conversation_id, payload.title)
    return StandardResponse(data=ConversationSummary.model_validate(conversation))


@router.delete(
    "/conversations/{conversation_id}",
    response_model=StandardResponse[dict],
    summary="Delete a conversation",
)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    chat_service.delete_conversation(db, ctx, conversation_id)
    return StandardResponse(data={"message": "Conversation deleted."})
