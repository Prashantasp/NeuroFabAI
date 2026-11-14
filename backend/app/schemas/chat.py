from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents import CopilotMode, DecisionResponse, ReasoningTimelineEvent


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    mode: CopilotMode = "general"
    conversation_id: Optional[str] = None


class AskResponse(BaseModel):
    conversation_id: str
    conversation_title: str
    message_id: str
    decision: DecisionResponse
    reasoning_timeline: List[ReasoningTimelineEvent] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    id: str
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationSummary):
    messages: List[MessageResponse] = Field(default_factory=list)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
