from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.workspace import WorkspaceMemberRole


class WorkspaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)


class WorkspaceResponse(WorkspaceBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    #: The requesting user's role. Lets the UI hide actions it cannot perform,
    #: while the server still enforces them.
    role: Optional[WorkspaceMemberRole] = None
    member_count: int = 0
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: Optional[str] = None
    role: WorkspaceMemberRole
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberInvite(BaseModel):
    email: EmailStr
    role: WorkspaceMemberRole = WorkspaceMemberRole.MEMBER


class WorkspaceMemberUpdate(BaseModel):
    role: WorkspaceMemberRole
