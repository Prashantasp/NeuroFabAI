from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user, get_db
from app.core.config import Settings, get_settings
from app.core.rate_limit import auth_rate_limit
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.response import StandardResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import auth_service

router = APIRouter()

REFRESH_COOKIE = "refresh_token"
# Legacy marker retained for cookie cleanup; never used to decide authentication.
SESSION_HINT_COOKIE = "nf_session"


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,  # not readable by JavaScript, so XSS cannot steal the session
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        key=SESSION_HINT_COOKIE,
        value="1",
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
        max_age=max_age,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    for key, http_only in ((REFRESH_COOKIE, True), (SESSION_HINT_COOKIE, False)):
        response.delete_cookie(
            key=key,
            httponly=http_only,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            domain=settings.COOKIE_DOMAIN,
            path="/",
        )


@router.post(
    "/register",
    response_model=StandardResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
    summary="Create an account",
)
def register(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    user = auth_service.register(
        db,
        user_in,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    return StandardResponse(data=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=StandardResponse[Token],
    dependencies=[Depends(auth_rate_limit)],
    summary="Sign in",
)
def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Returns a short-lived access token; the refresh token is set as an
    HttpOnly cookie and is never exposed to JavaScript."""
    token, refresh_token = auth_service.authenticate(
        db,
        login_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    _set_refresh_cookie(response, refresh_token, settings)
    return StandardResponse(data=token)


@router.post(
    "/refresh",
    response_model=StandardResponse[Token],
    summary="Rotate the session",
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    try:
        if not refresh_token:
            raise HTTPException(status_code=401, detail="No active session.")
        token, new_refresh = auth_service.refresh(
            db,
            refresh_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=getattr(request.state, "request_id", None),
        )
    except HTTPException as exc:
        # A rejected refresh token is dead; clear it so the browser stops
        # replaying it on every request.
        rejected = JSONResponse(status_code=exc.status_code, content={
            "success": False, "data": None,
            "error": {"code": "UNAUTHORIZED", "message": str(exc.detail)},
        })
        _clear_refresh_cookie(rejected, settings)
        return rejected

    _set_refresh_cookie(response, new_refresh, settings)
    return StandardResponse(data=token)


@router.post("/logout", response_model=StandardResponse[dict], summary="Sign out")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    auth_service.logout(
        db,
        request.cookies.get(REFRESH_COOKIE),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    _clear_refresh_cookie(response, settings)
    return StandardResponse(data={"message": "Signed out."})


@router.get(
    "/me", response_model=StandardResponse[UserRead], summary="Current user profile"
)
def me(current_user: User = Depends(get_current_user)):
    return StandardResponse(data=UserRead.model_validate(current_user))
