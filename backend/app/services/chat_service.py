"""Conversation persistence and the ask/stream entry points for the Copilot.

Every question and answer is written to PostgreSQL, so a conversation survives a
page refresh, a new browser, and a server restart. The `Conversation`/`Message`
tables existed before this but were never written to -- the Copilot kept all
state in React component memory.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import WorkspaceContext
from app.models.chat import Conversation, Message
from app.schemas.agents import AgentState, CopilotMode
from app.services.agents.workflow import get_agent_workflow
from app.services.llm import LLMError, get_llm_provider

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 4000
HISTORY_TURNS = 8
DEFAULT_TITLE = "New conversation"


class ChatService:
    # -- conversations ------------------------------------------------------

    def list_conversations(
        self, db: Session, ctx: WorkspaceContext, *, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Conversation], int]:
        base = select(Conversation).where(
            Conversation.workspace_id == ctx.workspace_id,
            Conversation.user_id == ctx.user_id,
        )
        total = db.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0
        items = list(
            db.execute(
                base.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
            ).scalars()
        )
        return items, total

    def get_conversation(
        self, db: Session, ctx: WorkspaceContext, conversation_id: str
    ) -> Conversation:
        conversation = db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                # Ownership is part of the lookup, not a check afterwards: there
                # is no code path that loads a conversation without scoping it.
                Conversation.workspace_id == ctx.workspace_id,
                Conversation.user_id == ctx.user_id,
            )
        ).scalar_one_or_none()

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
            )
        return conversation

    def delete_conversation(
        self, db: Session, ctx: WorkspaceContext, conversation_id: str
    ) -> None:
        conversation = self.get_conversation(db, ctx, conversation_id)
        db.delete(conversation)
        db.commit()

    def rename_conversation(
        self, db: Session, ctx: WorkspaceContext, conversation_id: str, title: str
    ) -> Conversation:
        conversation = self.get_conversation(db, ctx, conversation_id)
        conversation.title = title.strip()[:255] or DEFAULT_TITLE
        db.commit()
        db.refresh(conversation)
        return conversation

    # -- asking -------------------------------------------------------------

    @staticmethod
    def _validate_query(query: str) -> str:
        cleaned = (query or "").strip()
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Please enter a question.",
            )
        if len(cleaned) > MAX_QUERY_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Questions are limited to {MAX_QUERY_LENGTH} characters.",
            )
        return cleaned

    def _resolve_conversation(
        self,
        db: Session,
        ctx: WorkspaceContext,
        conversation_id: Optional[str],
        mode: CopilotMode,
        query: str,
    ) -> Conversation:
        if conversation_id:
            return self.get_conversation(db, ctx, conversation_id)

        conversation = Conversation(
            user_id=ctx.user_id,
            workspace_id=ctx.workspace_id,
            title=_derive_title(query),
            mode=mode,
        )
        db.add(conversation)
        db.flush()
        return conversation

    @staticmethod
    def _history(conversation: Conversation) -> List[Dict[str, str]]:
        return [
            {"role": m.role, "content": m.content}
            for m in conversation.messages[-HISTORY_TURNS:]
        ]

    def ask(
        self,
        db: Session,
        ctx: WorkspaceContext,
        *,
        query: str,
        mode: CopilotMode = "general",
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = self._validate_query(query)
        conversation = self._resolve_conversation(db, ctx, conversation_id, mode, query)
        history = self._history(conversation)

        user_message = Message(
            conversation_id=conversation.id, role="user", content=query, citations=[], payload={}
        )
        db.add(user_message)
        # Commit the question before the (slow, fallible) model call so it is not
        # lost if synthesis fails or the request is cancelled.
        db.commit()
        db.refresh(user_message)

        state = get_agent_workflow().run(
            AgentState(
                query=query,
                workspace_id=ctx.workspace_id,
                mode=mode,
                history=history,
            )
        )

        decision = state.final_decision
        payload = {
            "decision": decision.model_dump() if decision else None,
            "reasoning_timeline": [e.model_dump() for e in state.timeline],
            "errors": state.errors,
            "mode": mode,
        }

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=decision.executive_summary if decision else "",
            citations=[c.model_dump() for c in decision.citations] if decision else [],
            payload=payload,
            error="; ".join(state.errors) if state.errors and not decision else None,
        )
        db.add(assistant_message)

        conversation.mode = mode
        if conversation.title == DEFAULT_TITLE:
            conversation.title = _derive_title(query)
        # Touch so the conversation list orders by real activity.
        conversation.updated_at = func.now()

        db.commit()
        db.refresh(assistant_message)
        db.refresh(conversation)

        if decision is None:
            # Retrieval succeeded but the model could not answer. Surface it as a
            # real failure rather than returning fabricated analysis.
            raise CopilotUnavailable(
                message=state.errors[0] if state.errors else "The AI could not produce an answer.",
                conversation_id=conversation.id,
                timeline=payload["reasoning_timeline"],
            )

        return {
            "conversation_id": conversation.id,
            "conversation_title": conversation.title,
            "message_id": assistant_message.id,
            "decision": decision.model_dump(),
            "reasoning_timeline": payload["reasoning_timeline"],
            "errors": state.errors,
        }

    def stream(
        self,
        db: Session,
        ctx: WorkspaceContext,
        *,
        query: str,
        mode: CopilotMode = "general",
        conversation_id: Optional[str] = None,
    ) -> Iterator[str]:
        """Yield Server-Sent Events for a single question.

        Event sequence:
          `conversation` -> ids, so the client can attach before the answer lands
          `timeline`     -> each agent step as it completes
          `decision`     -> the structured answer
          `error`        -> user-safe failure message
          `done`         -> terminal
        """
        try:
            query = self._validate_query(query)
            conversation = self._resolve_conversation(db, ctx, conversation_id, mode, query)
            history = self._history(conversation)

            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=query,
                    citations=[],
                    payload={},
                )
            )
            db.commit()

            yield _sse(
                "conversation",
                {"conversation_id": conversation.id, "title": conversation.title},
            )

            state = get_agent_workflow().run(
                AgentState(
                    query=query, workspace_id=ctx.workspace_id, mode=mode, history=history
                )
            )

            for event in state.timeline:
                yield _sse("timeline", event.model_dump())

            decision = state.final_decision
            payload = {
                "decision": decision.model_dump() if decision else None,
                "reasoning_timeline": [e.model_dump() for e in state.timeline],
                "errors": state.errors,
                "mode": mode,
            }

            assistant = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=decision.executive_summary if decision else "",
                citations=[c.model_dump() for c in decision.citations] if decision else [],
                payload=payload,
                error="; ".join(state.errors) if state.errors and not decision else None,
            )
            db.add(assistant)
            conversation.mode = mode
            if conversation.title == DEFAULT_TITLE:
                conversation.title = _derive_title(query)
            db.commit()
            db.refresh(assistant)

            if decision is None:
                yield _sse(
                    "error",
                    {
                        "message": state.errors[0]
                        if state.errors
                        else "The AI could not produce an answer.",
                        "conversation_id": conversation.id,
                    },
                )
            else:
                yield _sse(
                    "decision",
                    {
                        "conversation_id": conversation.id,
                        "conversation_title": conversation.title,
                        "message_id": assistant.id,
                        "decision": decision.model_dump(),
                        "errors": state.errors,
                    },
                )
        except HTTPException as exc:
            yield _sse("error", {"message": exc.detail})
        except LLMError as exc:
            yield _sse("error", {"message": exc.user_message})
        except Exception:  # noqa: BLE001
            logger.exception("Copilot stream failed")
            db.rollback()
            yield _sse("error", {"message": "Something went wrong while answering. Please try again."})
        finally:
            yield _sse("done", {})

    @staticmethod
    def ai_status() -> Dict[str, Any]:
        provider = get_llm_provider()
        return {"provider": provider.name, "available": provider.available}


class CopilotUnavailable(Exception):
    """The workflow ran but produced no answer (model unavailable or malformed)."""

    def __init__(self, message: str, conversation_id: str, timeline: List[Dict[str, Any]]):
        super().__init__(message)
        self.message = message
        self.conversation_id = conversation_id
        self.timeline = timeline


def _derive_title(query: str) -> str:
    """Title from the question itself -- no extra model call, no extra latency."""
    cleaned = " ".join((query or "").split())
    if len(cleaned) <= 60:
        return cleaned or DEFAULT_TITLE
    return cleaned[:57].rstrip(" ,.;:") + "..."


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


chat_service = ChatService()
