from typing import List

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import (
    WorkspaceContext,
    get_current_user,
    get_db,
    get_workspace_context,
    require_workspace_admin,
)
from app.models.user import User
from app.schemas.response import StandardResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberInvite,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import workspace_service

router = APIRouter()


@router.get(
    "",
    response_model=StandardResponse[List[WorkspaceResponse]],
    summary="List my workspaces",
)
def list_workspaces(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Not paginated: workspaces are capped per user and the switcher needs them all."""
    return StandardResponse(data=workspace_service.list_for_user(db, current_user.id))


@router.post(
    "",
    response_model=StandardResponse[WorkspaceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
def create_workspace(
    workspace_in: WorkspaceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = workspace_service.create(
        db,
        current_user.id,
        workspace_in,
        request_id=getattr(request.state, "request_id", None),
    )
    return StandardResponse(data=workspace)


@router.get(
    "/active",
    response_model=StandardResponse[WorkspaceResponse],
    summary="Get the active workspace",
)
def get_active_workspace(
    db: Session = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)
):
    return StandardResponse(
        data={
            "id": ctx.workspace.id,
            "name": ctx.workspace.name,
            "description": ctx.workspace.description,
            "owner_id": ctx.workspace.owner_id,
            "created_at": ctx.workspace.created_at,
            "updated_at": ctx.workspace.updated_at,
            "role": ctx.role,
            "member_count": workspace_service.member_count(db, ctx.workspace_id),
            "document_count": workspace_service.document_count(db, ctx.workspace_id),
        }
    )


@router.patch(
    "/active",
    response_model=StandardResponse[WorkspaceResponse],
    summary="Rename the active workspace",
)
def update_workspace(
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(require_workspace_admin),
):
    return StandardResponse(
        data=workspace_service.update(db, ctx.workspace, ctx.role, payload)
    )


@router.delete(
    "/active",
    response_model=StandardResponse[dict],
    summary="Delete the active workspace",
)
def delete_workspace(
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    workspace_service.delete(db, ctx.workspace, ctx.user_id)
    return StandardResponse(data={"message": "Workspace deleted."})


@router.get(
    "/active/members",
    response_model=StandardResponse[List[WorkspaceMemberResponse]],
    summary="List workspace members",
)
def list_members(
    db: Session = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)
):
    return StandardResponse(data=workspace_service.list_members(db, ctx.workspace_id))


@router.post(
    "/active/members",
    response_model=StandardResponse[WorkspaceMemberResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a member",
)
def add_member(
    payload: WorkspaceMemberInvite,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(require_workspace_admin),
):
    return StandardResponse(
        data=workspace_service.add_member(db, ctx.workspace_id, payload.email, payload.role)
    )


@router.patch(
    "/active/members/{user_id}",
    response_model=StandardResponse[dict],
    summary="Change a member's role",
)
def update_member(
    user_id: str,
    payload: WorkspaceMemberUpdate,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(require_workspace_admin),
):
    workspace_service.update_member_role(db, ctx.workspace, user_id, payload.role)
    return StandardResponse(data={"message": "Member role updated."})


@router.delete(
    "/active/members/{user_id}",
    response_model=StandardResponse[dict],
    summary="Remove a member",
)
def remove_member(
    user_id: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(require_workspace_admin),
):
    workspace_service.remove_member(db, ctx.workspace, user_id)
    return StandardResponse(data={"message": "Member removed."})
