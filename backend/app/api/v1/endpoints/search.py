from typing import List, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import WorkspaceContext, get_db, get_workspace_context
from app.schemas.response import StandardResponse
from app.services.search_service import SearchResult, search_service

router = APIRouter()


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=50)
    strategy: Literal["keyword", "semantic", "graph", "hybrid"] = "hybrid"


@router.post(
    "",
    response_model=StandardResponse[List[SearchResult]],
    summary="Search documents, excerpts, and graph entities",
)
def search(
    payload: SearchQuery,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Scoped to the caller's verified workspace across all strategies."""
    results = search_service.search(
        query=payload.query,
        strategy=payload.strategy,
        limit=payload.limit,
        workspace_id=ctx.workspace_id,
        db=db,
    )
    return StandardResponse(data=results)
