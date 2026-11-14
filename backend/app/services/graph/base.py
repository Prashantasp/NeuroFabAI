"""Graph persistence and traversal interface.

`workspace_id` is required on every operation. It used to be optional, and every
implementation treated a missing workspace as "match everything", which made the
graph endpoints a cross-tenant read. Making it a required positional concern
means a caller cannot forget it.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.schemas.knowledge import KnowledgeGraphExtraction


class GraphBackend(ABC):
    @abstractmethod
    def health_check(self) -> bool:
        """Check connection health."""

    @abstractmethod
    def ingest_extraction(
        self, extraction: KnowledgeGraphExtraction, workspace_id: str
    ) -> None:
        """Upsert nodes and edges into the workspace's partition of the graph."""

    @abstractmethod
    def get_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Node/relationship counts and type breakdowns for one workspace."""

    @abstractmethod
    def get_node(self, node_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single node by canonical name within a workspace."""

    @abstractmethod
    def get_subgraph(
        self, root_node_id: str, workspace_id: str, depth: int = 1
    ) -> Dict[str, Any]:
        """Retrieve nodes and edges within `depth` hops of a root node."""

    @abstractmethod
    def get_topology(self, workspace_id: str) -> Dict[str, Any]:
        """Retrieve the full workspace graph for visualisation."""

    @abstractmethod
    def delete_document_subgraph(self, document_id: str, workspace_id: str) -> int:
        """Remove nodes/edges sourced from a document. Returns nodes deleted.

        Called when a document is deleted so the knowledge graph does not retain
        entities from content the user believes they removed.
        """
