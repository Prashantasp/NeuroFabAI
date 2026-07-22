from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.schemas.knowledge import KnowledgeGraphExtraction

class GraphBackend(ABC):
    """
    Abstract interface for Graph Persistence and Traversal.
    """

    @abstractmethod
    def ingest_extraction(self, extraction: KnowledgeGraphExtraction) -> None:
        """Upsert nodes and edges from extraction into the graph."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics about the current graph."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific node by its canonical ID."""
        pass
        
    @abstractmethod
    def get_subgraph(self, root_node_id: str, depth: int = 1) -> Dict[str, Any]:
        """
        Retrieves a subgraph radiating from a root node up to a certain depth.
        Returns a dict containing 'nodes' and 'edges'.
        """
        pass

    @abstractmethod
    def get_topology(self) -> Dict[str, Any]:
        """
        Retrieves the entire graph topology (nodes and edges).
        Useful for visualization.
        """
        pass
