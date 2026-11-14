"""Exception handlers producing the standard `{success, data, error}` envelope."""

from __future__ import annotations

import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.schemas.response import ErrorDetail

logger = logging.getLogger(__name__)

STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class NeuroFabException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "BAD_REQUEST",
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _envelope(status_code: int, error: ErrorDetail, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": error.model_dump()},
        headers=headers,
    )


async def neurofab_exception_handler(request: Request, exc: NeuroFabException):
    return _envelope(exc.status_code, ErrorDetail(code=exc.code, message=exc.message))


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _envelope(
        exc.status_code,
        ErrorDetail(code=code, message=detail),
        headers=getattr(exc, "headers", None),
    )


# Pydantic's built-in messages are written for developers. These render next to
# a form field, so the common ones are rewritten for the person filling it in.
_MESSAGE_REWRITES = (
    ("value is not a valid email address", "Enter a valid email address."),
    ("field required", "This field is required."),
    ("string should have at least", "This value is too short."),
    ("string should have at most", "This value is too long."),
    ("input should be a valid", "This value has the wrong format."),
)


def _humanise(message: str) -> str:
    # Custom validators come through prefixed with "Value error, ".
    cleaned = message.removeprefix("Value error, ").strip()
    lowered = cleaned.lower()
    for needle, replacement in _MESSAGE_REWRITES:
        if lowered.startswith(needle):
            return replacement
    return cleaned or "Invalid value."


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return field-level errors the UI can attach to inputs.

    Pydantic's raw error list includes the submitted value, which for a login
    request is the password. Only the location and a cleaned message are
    surfaced -- never `input`.
    """
    details = [
        {
            "field": ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query")),
            "message": _humanise(err.get("msg", "Invalid value")),
        }
        for err in exc.errors()
    ]
    return _envelope(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorDetail(
            code="VALIDATION_ERROR",
            message=details[0]["message"] if details else "Please check the submitted values.",
            details=details,
        ),
    )


async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all. Logs the real error; returns an opaque message to the client."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unhandled exception on %s %s (request_id=%s)",
        request.method, request.url.path, request_id,
        exc_info=True,
    )

    settings = get_settings()
    message = "An unexpected error occurred. Please try again."
    if request_id:
        message += f" (reference: {request_id})"

    return _envelope(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorDetail(
            code="INTERNAL_ERROR",
            message=message,
            # Stack details are exposed only outside production.
            details=None if settings.is_production else f"{type(exc).__name__}: {exc}",
        ),
    )
