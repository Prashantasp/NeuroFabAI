from typing import Dict, Any, Optional
from app.schemas.knowledge import KnowledgeGraphExtraction
from app.services.graph.base import GraphBackend

class Neo4jBackend(GraphBackend):
    """
    Neo4j implementation for production use.
    Stubbed out for Phase 7 as requested (ready for configuration swap).
    """

    def ingest_extraction(self, extraction: KnowledgeGraphExtraction) -> None:
        raise NotImplementedError("Neo4jBackend is not yet implemented.")

    def get_stats(self) -> Dict[str, Any]:
        raise NotImplementedError("Neo4jBackend is not yet implemented.")

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Neo4jBackend is not yet implemented.")

    def get_subgraph(self, root_node_id: str, depth: int = 1) -> Dict[str, Any]:
        raise NotImplementedError("Neo4jBackend is not yet implemented.")
