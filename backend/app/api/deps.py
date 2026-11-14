"""Shared FastAPI dependencies: database session, authentication, tenancy.

`get_workspace_context` is the single chokepoint that turns the client-supplied
`X-Workspace-ID` header into a *verified* workspace. Every workspace-scoped
endpoint must depend on it -- reading the header directly reintroduces the
cross-tenant read that this replaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, List, Optional, Sequence

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceMemberRole
from app.repositories.user_repository import user_repo

# auto_error=False lets us return a consistent envelope instead of Starlette's
# bare {"detail": "Not authenticated"}.
bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_EXCEPTION

    try:
        payload = decode_token(credentials.credentials, settings.SECRET_KEY)
    except ValueError:
        # Deliberately opaque: distinguishing "expired" from "malformed" tells an
        # attacker whether a forged token had a valid signature.
        raise CREDENTIALS_EXCEPTION

    if payload.get("type") != "access":
        raise CREDENTIALS_EXCEPTION

    user_id = payload.get("sub")
    if not user_id:
        raise CREDENTIALS_EXCEPTION

    user = user_repo.get(db, id=user_id)
    if not user:
        raise CREDENTIALS_EXCEPTION
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    # Lets the rate limiter key on the user rather than a shared egress IP.
    request.state.user_id = user.id
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Optional[User]:
    if credentials is None:
        return None
    try:
        return get_current_user(request, db, credentials, settings)
    except HTTPException:
        return None


@dataclass
class WorkspaceContext:
    """A workspace the current user has been *proven* to be a member of."""

    workspace: Workspace
    user: User
    role: WorkspaceMemberRole

    @property
    def workspace_id(self) -> str:
        return self.workspace.id

    @property
    def user_id(self) -> str:
        return self.user.id

    def require_role(self, allowed: Sequence[WorkspaceMemberRole]) -> None:
        if self.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action in this workspace.",
            )

    @property
    def can_write(self) -> bool:
        return self.role in (
            WorkspaceMemberRole.OWNER,
            WorkspaceMemberRole.ADMIN,
            WorkspaceMemberRole.MEMBER,
        )


def get_workspace_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_workspace_id: Optional[str] = Header(
        None, alias="X-Workspace-ID", description="Active workspace ID"
    ),
) -> WorkspaceContext:
    workspace_id = (x_workspace_id or "").strip()

    # Fall back to the user's last active workspace so a client that has not yet
    # hydrated its workspace list still gets a correctly scoped response.
    if not workspace_id:
        workspace_id = (current_user.last_workspace_id or "").strip()
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workspace. Select a workspace and try again.",
        )

    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        .one_or_none()
    )
    if member is None:
        # 404 rather than 403: confirming that a workspace exists but is not
        # yours is itself an information leak.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )

    return WorkspaceContext(workspace=workspace, user=current_user, role=member.role)


def require_workspace_roles(*roles: WorkspaceMemberRole):
    """Dependency factory enforcing a minimum workspace role."""
    allowed: List[WorkspaceMemberRole] = list(roles)

    def dependency(
        ctx: WorkspaceContext = Depends(get_workspace_context),
    ) -> WorkspaceContext:
        ctx.require_role(allowed)
        return ctx

    return dependency


require_workspace_writer = require_workspace_roles(
    WorkspaceMemberRole.OWNER,
    WorkspaceMemberRole.ADMIN,
    WorkspaceMemberRole.MEMBER,
)
require_workspace_admin = require_workspace_roles(
    WorkspaceMemberRole.OWNER, WorkspaceMemberRole.ADMIN
)


@dataclass
class AuditContext:
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]


def get_audit_context(request: Request) -> AuditContext:
    return AuditContext(
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        request_id=getattr(request.state, "request_id", None),
    )
