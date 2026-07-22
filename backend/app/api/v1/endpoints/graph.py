from fastapi import APIRouter
from app.services.graph_service import graph_service

router = APIRouter()

@router.get("/stats")
def get_graph_stats():
    """
    Returns statistics about the current Knowledge Graph structure.
    Used for the dashboard and to verify Phase 6 Graph Construction.
    """
    return graph_service.get_stats()

@router.get("/topology")
def get_graph_topology():
    """
    Returns the entire graph topology (nodes and relationships)
    for frontend visualization.
    """
    return graph_service.get_topology()
