from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import auth_rate_limit
from app.models.user import User
from app.repositories.user_repository import user_repo
from app.schemas.response import StandardResponse
from app.schemas.user import PasswordChange, UserRead, UserUpdate
from app.services.auth_service import auth_service

router = APIRouter()


@router.get("/me", response_model=StandardResponse[UserRead], summary="Get my profile")
def read_me(current_user: User = Depends(get_current_user)):
    return StandardResponse(data=UserRead.model_validate(current_user))


@router.patch("/me", response_model=StandardResponse[UserRead], summary="Update my profile")
def update_me(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """`UserUpdate` intentionally excludes role and account-status fields, so a
    user cannot escalate their own privileges through this endpoint."""
    updates = user_in.model_dump(exclude_unset=True)

    username = updates.get("username")
    if username:
        existing = user_repo.get_by_username(db, username=username)
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="That username is taken."
            )

    for field, value in updates.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return StandardResponse(data=UserRead.model_validate(current_user))


@router.post(
    "/me/password",
    response_model=StandardResponse[dict],
    dependencies=[Depends(auth_rate_limit)],
    summary="Change my password",
)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.change_password(
        db, current_user, payload.current_password, payload.new_password
    )
    return StandardResponse(
        data={"message": "Password updated. Other sessions have been signed out."}
    )


@router.patch(
    "/me/workspace/{workspace_id}",
    response_model=StandardResponse[UserRead],
    summary="Remember the active workspace",
)
def set_last_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist workspace selection server-side so it survives a new device."""
    from app.services.workspace_service import workspace_service

    workspace_service.verify_access(db, current_user.id, workspace_id)
    current_user.last_workspace_id = workspace_id
    db.commit()
    db.refresh(current_user)
    return StandardResponse(data=UserRead.model_validate(current_user))
