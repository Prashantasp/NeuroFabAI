"""Workspace lifecycle and membership."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceMemberRole
from app.repositories.user_repository import user_repo
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.services.audit_service import audit_service
from app.services.cleanup_service import queue_cleanup, cleanup_workspace
from app.services.workspace_lock import serialized_workspace

logger = logging.getLogger(__name__)

MAX_WORKSPACES_PER_USER = 25


class WorkspaceService:
    # -- reads --------------------------------------------------------------

    def get_membership(
        self, db: Session, workspace_id: str, user_id: str
    ) -> Optional[WorkspaceMember]:
        return db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        ).scalar_one_or_none()

    def verify_access(
        self,
        db: Session,
        user_id: str,
        workspace_id: str,
        required_roles: Sequence[WorkspaceMemberRole] = (),
    ) -> WorkspaceMember:
        member = self.get_membership(db, workspace_id, user_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
            )
        if required_roles and member.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action in this workspace.",
            )
        return member

    def list_for_user(self, db: Session, user_id: str) -> List[dict]:
        """Workspaces the user belongs to, with the counts the UI displays.

        Counts are aggregated in SQL rather than by loading relationships, so
        listing N workspaces stays a fixed number of queries.
        """
        rows = db.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.asc())
        ).all()

        if not rows:
            workspace = self._provision_personal_workspace(db, user_id)
            if workspace is None:
                return []
            rows = [(workspace, WorkspaceMemberRole.OWNER)]

        workspace_ids = [w.id for w, _ in rows]

        member_counts = dict(
            db.execute(
                select(WorkspaceMember.workspace_id, func.count())
                .where(WorkspaceMember.workspace_id.in_(workspace_ids))
                .group_by(WorkspaceMember.workspace_id)
            ).all()
        )
        document_counts = dict(
            db.execute(
                select(Document.workspace_id, func.count())
                .where(Document.workspace_id.in_(workspace_ids))
                .group_by(Document.workspace_id)
            ).all()
        )

        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "owner_id": w.owner_id,
                "created_at": w.created_at,
                "updated_at": w.updated_at,
                "role": role,
                "member_count": member_counts.get(w.id, 0),
                "document_count": document_counts.get(w.id, 0),
            }
            for w, role in rows
        ]

    def _provision_personal_workspace(self, db: Session, user_id: str) -> Optional[Workspace]:
        """Backfill for accounts created before workspaces existed."""
        user = db.get(User, user_id)
        if user is None:
            return None

        name = f"{user.full_name}'s Workspace" if user.full_name else "Personal Workspace"
        workspace = Workspace(
            name=name[:120], description="Default personal workspace", owner_id=user_id
        )
        db.add(workspace)
        db.flush()
        db.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=user_id, role=WorkspaceMemberRole.OWNER
            )
        )
        user.last_workspace_id = workspace.id
        db.commit()
        db.refresh(workspace)
        return workspace

    # -- writes -------------------------------------------------------------

    def create(
        self,
        db: Session,
        user_id: str,
        workspace_in: WorkspaceCreate,
        *,
        request_id: Optional[str] = None,
    ) -> dict:
        owned = db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
        ) or 0
        if owned >= MAX_WORKSPACES_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You have reached the limit of {MAX_WORKSPACES_PER_USER} workspaces.",
            )

        workspace = Workspace(
            name=workspace_in.name.strip(),
            description=(workspace_in.description or "").strip() or None,
            owner_id=user_id,
        )
        db.add(workspace)
        db.flush()
        db.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=user_id, role=WorkspaceMemberRole.OWNER
            )
        )
        db.commit()
        db.refresh(workspace)

        audit_service.log_action(
            db,
            action="WORKSPACE_CREATED",
            resource_type="workspace",
            resource_id=workspace.id,
            user_id=user_id,
            workspace_id=workspace.id,
            request_id=request_id,
        )
        return _to_dict(workspace, WorkspaceMemberRole.OWNER, member_count=1, document_count=0)

    def update(
        self, db: Session, workspace: Workspace, role: WorkspaceMemberRole, data: WorkspaceUpdate
    ) -> dict:
        if data.name is not None:
            workspace.name = data.name.strip()
        if data.description is not None:
            workspace.description = data.description.strip() or None
        db.commit()
        db.refresh(workspace)
        return _to_dict(
            workspace,
            role,
            member_count=self.member_count(db, workspace.id),
            document_count=self.document_count(db, workspace.id),
        )

    @serialized_workspace
    def delete(self, db: Session, workspace: Workspace, user_id: str) -> None:
        if workspace.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the workspace owner can delete it.",
            )

        remaining = db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id != workspace.id,
            )
        ) or 0
        if remaining == 0:
            # Deleting the only workspace leaves the account with nowhere to put
            # documents and every screen in a broken empty state.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your only workspace. Create another one first.",
            )

        workspace_id = workspace.id
        for document in db.scalars(select(Document).where(Document.workspace_id == workspace_id)).all():
            queue_cleanup(db, document)
            db.delete(document)

        db.delete(workspace)
        db.commit()
        cleanup_workspace(db, workspace_id)

        # Any user whose "last workspace" pointer referenced this one must be
        # repointed, or their next request 400s on a dangling id.
        db.query(User).filter(User.last_workspace_id == workspace_id).update(
            {User.last_workspace_id: None}, synchronize_session=False
        )
        db.commit()

        audit_service.log_action(
            db,
            action="WORKSPACE_DELETED",
            resource_type="workspace",
            resource_id=workspace_id,
            user_id=user_id,
        )

    # -- members ------------------------------------------------------------

    def list_members(self, db: Session, workspace_id: str) -> List[dict]:
        rows = db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        ).all()
        return [
            {
                "user_id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": member.role,
                "joined_at": member.joined_at,
            }
            for member, user in rows
        ]

    def add_member(
        self, db: Session, workspace_id: str, email: str, role: WorkspaceMemberRole
    ) -> dict:
        user = user_repo.get_by_email(db, email=email.lower().strip())
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No NeuroFab account exists with that email. Ask them to sign up first.",
            )
        if self.get_membership(db, workspace_id, user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That user is already a member of this workspace.",
            )
        if role == WorkspaceMemberRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A workspace can only have one owner.",
            )

        member = WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role)
        db.add(member)
        db.commit()

        audit_service.log_action(
            db,
            action="WORKSPACE_MEMBER_ADDED",
            resource_type="workspace_member",
            resource_id=user.id,
            workspace_id=workspace_id,
        )
        return {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": member.role,
            "joined_at": member.joined_at,
        }

    def update_member_role(
        self, db: Session, workspace: Workspace, user_id: str, role: WorkspaceMemberRole
    ) -> None:
        if user_id == workspace.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The workspace owner's role cannot be changed.",
            )
        member = self.verify_access(db, user_id, workspace.id)
        member.role = role
        db.commit()

    def remove_member(self, db: Session, workspace: Workspace, user_id: str) -> None:
        if user_id == workspace.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The workspace owner cannot be removed.",
            )
        member = self.get_membership(db, workspace.id, user_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="That user is not a member."
            )
        db.delete(member)
        db.commit()

        audit_service.log_action(
            db,
            action="WORKSPACE_MEMBER_REMOVED",
            resource_type="workspace_member",
            resource_id=user_id,
            workspace_id=workspace.id,
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def member_count(db: Session, workspace_id: str) -> int:
        return db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
        ) or 0

    @staticmethod
    def document_count(db: Session, workspace_id: str) -> int:
        return db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.workspace_id == workspace_id)
        ) or 0


def _to_dict(
    workspace: Workspace,
    role: WorkspaceMemberRole,
    *,
    member_count: int,
    document_count: int,
) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "description": workspace.description,
        "owner_id": workspace.owner_id,
        "created_at": workspace.created_at,
        "updated_at": workspace.updated_at,
        "role": role,
        "member_count": member_count,
        "document_count": document_count,
    }


workspace_service = WorkspaceService()
