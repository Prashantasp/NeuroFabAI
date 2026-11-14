"""Health and system status.

`/health` is unauthenticated and intentionally shallow -- it is a liveness probe
for load balancers and must not touch dependencies.

`/status` is authenticated and reports the real state of each dependency. The
Settings and Dashboard pages render it instead of the hardcoded "Online" badges
they used to show.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.response import StandardResponse

router = APIRouter()


@router.get("", summary="Liveness probe")
def health(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


@router.get(
    "/status",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Dependency status",
)
def system_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
):
    from app.services.graph_service import get_graph_backend
    from app.services.llm import get_llm_provider
    from app.services.vectorstore.qdrant import QdrantStore

    def probe(name: str, fn, detail: str) -> Dict[str, Any]:
        try:
            ok = bool(fn())
        except Exception as exc:  # noqa: BLE001
            return {"name": name, "online": False, "detail": f"Unavailable: {type(exc).__name__}"}
        return {"name": name, "online": ok, "detail": detail if ok else "Unavailable"}

    llm = get_llm_provider()

    components = [
        probe(
            "Database",
            lambda: db.execute(text("SELECT 1")).scalar() == 1,
            settings.DATABASE_URL.split("@")[-1],  # host/db only, never credentials
        ),
        probe("Vector store", lambda: QdrantStore().health_check(), settings.QDRANT_URL),
        probe(
            "Knowledge graph",
            lambda: get_graph_backend().health_check(),
            settings.GRAPH_BACKEND,
        ),
        {
            "name": "AI provider",
            "online": llm.available,
            "detail": (
                f"{llm.name} / {settings.LLM_MODEL}"
                if llm.available
                else "Not configured - set GOOGLE_API_KEY"
            ),
        },
    ]

    return StandardResponse(
        data={
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
            "components": components,
            "all_online": all(c["online"] for c in components),
            "models": {
                "reasoning": settings.LLM_MODEL if llm.available else None,
                "embedding": settings.EMBEDDING_MODEL if llm.available else "deterministic (local)",
                "embedding_dimension": settings.EMBEDDING_DIMENSION,
            },
        }
    )
