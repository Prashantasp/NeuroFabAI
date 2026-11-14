"""Structured logging and HTTP middleware."""

from __future__ import annotations

import logging
import sys
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings

# Header values that must never reach the logs.
_REDACTED_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key"}


def setup_logging() -> None:
    settings = get_settings()

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    for noisy in ("httpx", "httpcore", "neo4j", "urllib3", "qdrant_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    # JSON for log aggregation in production; human-readable locally.
    processors.append(
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "neurofab"):
    return structlog.get_logger(name)


logger = get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request ID, bind log context, and record latency."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            workspace_id=request.headers.get("x-workspace-id"),
        )

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed", latency_ms=round((time.perf_counter() - started) * 1000, 2)
            )
            raise
        finally:
            structlog.contextvars.bind_contextvars(
                user_id=getattr(request.state, "user_id", None)
            )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        log = logger.warning if response.status_code >= 500 else logger.info
        log("request_completed", status_code=response.status_code, latency_ms=latency_ms)

        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline response hardening.

    The API returns JSON and streams file downloads; it never renders HTML, so a
    highly restrictive CSP is appropriate here. The frontend sets its own.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        settings = get_settings()

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
