"""Authentication: registration, login, refresh rotation, logout."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceMemberRole
from app.repositories.refresh_token_repository import RefreshTokenCreate, refresh_token_repo
from app.repositories.user_repository import user_repo
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 8
LOCKOUT_MINUTES = 15

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password.",
)


def hash_token(token: str) -> str:
    """Refresh tokens are stored hashed: a database leak must not yield sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; comparisons need a consistent tzinfo."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class AuthService:
    # -- registration -------------------------------------------------------

    def register(
        self,
        db: Session,
        user_in: UserCreate,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> User:
        email = user_in.email.lower().strip()

        if user_repo.get_by_email(db, email=email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            email=email,
            username=(user_in.username or None),
            full_name=(user_in.full_name or None),
            company=(user_in.company or None),
            hashed_password=get_password_hash(user_in.password),
        )
        db.add(user)

        try:
            db.flush()
        except IntegrityError:
            # Two concurrent signups with the same email: the unique index is the
            # real guard, the check above is just for a friendlier message.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        workspace = self._provision_default_workspace(db, user)
        db.commit()
        db.refresh(user)

        audit_service.log_action(
            db,
            action="USER_REGISTERED",
            resource_type="user",
            resource_id=user.id,
            user_id=user.id,
            workspace_id=workspace.id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        return user

    @staticmethod
    def _provision_default_workspace(db: Session, user: User) -> Workspace:
        """Every user gets a workspace at signup so the app is never empty-state-broken."""
        name = f"{user.full_name}'s Workspace" if user.full_name else "Personal Workspace"
        workspace = Workspace(
            name=name[:120], description="Default personal workspace", owner_id=user.id
        )
        db.add(workspace)
        db.flush()

        db.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceMemberRole.OWNER,
            )
        )
        user.last_workspace_id = workspace.id
        return workspace

    # -- login --------------------------------------------------------------

    def authenticate(
        self,
        db: Session,
        login_data: LoginRequest,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[Token, str]:
        email = login_data.email.lower().strip()
        user = user_repo.get_by_email(db, email=email)

        if user is None:
            # Hash anyway so response time does not reveal whether the account
            # exists (a trivial user-enumeration oracle otherwise).
            get_password_hash(login_data.password)
            raise INVALID_CREDENTIALS

        locked_until = _as_aware(user.locked_until)
        if locked_until and locked_until > _utc_now():
            remaining = int((locked_until - _utc_now()).total_seconds() // 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {remaining} minute(s).",
            )

        if not verify_password(login_data.password, user.hashed_password):
            self._record_failure(db, user, ip_address, user_agent, request_id)
            raise INVALID_CREDENTIALS

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated.",
            )

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = _utc_now()

        access_token = create_access_token(subject=user.id)
        refresh_plain, expires_at = create_refresh_token(subject=user.id)
        self._store_refresh_token(db, user.id, refresh_plain, expires_at, ip_address, user_agent)
        db.commit()

        audit_service.log_action(
            db,
            action="USER_LOGIN",
            resource_type="auth",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        return Token(access_token=access_token), refresh_plain

    def _record_failure(
        self,
        db: Session,
        user: User,
        ip_address: Optional[str],
        user_agent: Optional[str],
        request_id: Optional[str],
    ) -> None:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = _utc_now() + timedelta(minutes=LOCKOUT_MINUTES)
            logger.warning("Account %s locked after %d failed attempts", user.id, user.failed_login_attempts)
        db.commit()

        audit_service.log_action(
            db,
            action="USER_LOGIN_FAILED",
            resource_type="auth",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

    @staticmethod
    def _store_refresh_token(
        db: Session,
        user_id: str,
        token_plain: str,
        expires_at: datetime,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        refresh_token_repo.create(
            db,
            obj_in=RefreshTokenCreate(
                user_id=user_id,
                hashed_token=hash_token(token_plain),
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:255] or None,
            ),
        )

    # -- refresh ------------------------------------------------------------

    def refresh(
        self,
        db: Session,
        refresh_token_plain: str,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[Token, str]:
        settings = get_settings()
        invalid = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again."
        )

        try:
            payload = decode_token(refresh_token_plain, settings.JWT_SECRET)
        except ValueError:
            raise invalid
        if payload.get("type") != "refresh":
            raise invalid

        stored = refresh_token_repo.get_by_token(db, hashed_token=hash_token(refresh_token_plain))
        if stored is None:
            raise invalid

        if stored.revoked:
            # A revoked token being presented means it was captured and replayed
            # (or a client raced). Revoke the whole family: the safe response to
            # a possible token theft is to end every session for that user.
            logger.warning("Reuse of revoked refresh token for user %s", stored.user_id)
            refresh_token_repo.revoke_all_for_user(db, user_id=stored.user_id)
            audit_service.log_action(
                db,
                action="REFRESH_TOKEN_REUSE_DETECTED",
                resource_type="auth",
                user_id=stored.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            )
            raise invalid

        if _as_aware(stored.expires_at) <= _utc_now():
            raise invalid

        user = user_repo.get(db, id=stored.user_id)
        if not user or not user.is_active:
            raise invalid

        refresh_token_repo.revoke_token(db, token_id=stored.id)
        access_token = create_access_token(subject=user.id)
        new_refresh, expires_at = create_refresh_token(subject=user.id)
        self._store_refresh_token(db, user.id, new_refresh, expires_at, ip_address, user_agent)
        db.commit()

        return Token(access_token=access_token), new_refresh

    # -- logout -------------------------------------------------------------

    def logout(
        self,
        db: Session,
        refresh_token_plain: Optional[str],
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        if not refresh_token_plain:
            return
        stored = refresh_token_repo.get_by_token(db, hashed_token=hash_token(refresh_token_plain))
        if stored and not stored.revoked:
            refresh_token_repo.revoke_token(db, token_id=stored.id)
            audit_service.log_action(
                db,
                action="USER_LOGOUT",
                resource_type="auth",
                user_id=stored.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            )

    # -- password change ----------------------------------------------------

    def change_password(
        self, db: Session, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your current password is incorrect.",
            )
        user.hashed_password = get_password_hash(new_password)
        # Changing a password must end other sessions, otherwise a compromised
        # session survives the very action taken to stop it.
        refresh_token_repo.revoke_all_for_user(db, user_id=user.id)
        db.commit()

        audit_service.log_action(
            db, action="PASSWORD_CHANGED", resource_type="auth", user_id=user.id
        )


auth_service = AuthService()
