"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    NeuroFabException,
    global_exception_handler,
    http_exception_handler,
    neurofab_exception_handler,
    validation_exception_handler,
)
from app.core.logging import LoggingMiddleware, SecurityHeadersMiddleware, setup_logging

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown.

    Schema creation lives in Alembic, not here. The previous version called
    `Base.metadata.create_all()` at import time, which meant importing the module
    required a live database, raced with migrations, and made unit tests
    impossible.
    """
    setup_logging()
    logger.info(
        "Starting %s v%s in %s mode", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT
    )

    if not settings.ai_enabled:
        logger.warning(
            "No AI credential configured (GOOGLE_API_KEY / GEMINI_API_KEY). "
            "The Copilot will return a clear 'AI not configured' error, and "
            "ingestion will use local deterministic embeddings without graph extraction."
        )

    # Replay persisted graph evidence; the recovery loop resumes interrupted jobs.
    try:
        from app.services.graph_service import hydrate_graph_from_db

        hydrate_graph_from_db()
    except Exception:  # noqa: BLE001 - never block startup
        logger.exception("Knowledge graph hydration failed")

    try:
        from app.services.task_service import task_service

        if settings.ENVIRONMENT != "test":
            task_service.start()
    except Exception:  # noqa: BLE001
        logger.exception("Stuck-document recovery failed")

    yield

    from app.services.task_service import task_service

    task_service.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NeuroFab AI - industrial GraphRAG platform API",
    lifespan=lifespan,
    # Interactive docs are a fingerprinting aid in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    # Explicit origins, never "*": credentials are sent with every request.
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

app.add_exception_handler(NeuroFabException, neurofab_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.PROJECT_NAME, "version": settings.VERSION, "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
