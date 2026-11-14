from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import WorkspaceContext, get_workspace_context
from app.schemas.response import StandardResponse
from app.services.graph_service import get_graph_backend

router = APIRouter()

MAX_TOPOLOGY_NODES = 1500


@router.get(
    "/stats",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Knowledge graph statistics for the active workspace",
)
def get_graph_stats(ctx: WorkspaceContext = Depends(get_workspace_context)):
    """Scoped to the caller's verified workspace.

    This endpoint previously had no authentication and treated the workspace
    header as advisory, so it returned every tenant's entity names to anonymous
    callers.
    """
    return StandardResponse(data=get_graph_backend().get_stats(ctx.workspace_id))


@router.get(
    "/topology",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Full graph topology for visualisation",
)
def get_graph_topology(ctx: WorkspaceContext = Depends(get_workspace_context)):
    topology = get_graph_backend().get_topology(ctx.workspace_id)

    nodes = topology.get("nodes", [])
    truncated = len(nodes) > MAX_TOPOLOGY_NODES
    if truncated:
        # The force-directed canvas becomes unusable well before this, and the
        # payload gets large. Tell the client so it can say so in the UI.
        kept = {n["id"] for n in nodes[:MAX_TOPOLOGY_NODES]}
        topology = {
            "nodes": nodes[:MAX_TOPOLOGY_NODES],
            "edges": [
                e
                for e in topology.get("edges", [])
                if e.get("source") in kept and e.get("target") in kept
            ],
        }

    topology["truncated"] = truncated
    topology["total_nodes"] = len(nodes)
    return StandardResponse(data=topology)


@router.get(
    "/nodes/{node_id}",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Get one entity and its immediate neighbourhood",
)
def get_graph_node(
    node_id: str,
    depth: int = Query(1, ge=1, le=3),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    backend = get_graph_backend()
    node = backend.get_node(node_id, ctx.workspace_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found in this workspace."
        )
    subgraph = backend.get_subgraph(node_id, ctx.workspace_id, depth=depth)
    return StandardResponse(data={"node": node, "subgraph": subgraph})
