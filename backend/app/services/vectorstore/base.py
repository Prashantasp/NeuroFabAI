from abc import ABC, abstractmethod
from typing import Any, Dict, List


class VectorStoreError(Exception):
    """Raised when the vector store cannot serve a request."""

    user_message = "The search index is temporarily unavailable. Please try again."


class VectorStore(ABC):
    """Abstract base class for vector databases.

    `workspace_id` is required on both write and read. Tenant scoping is not
    optional -- an unfiltered search returns other customers' document text.
    """

    @abstractmethod
    def insert_vectors(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> None:
        """Insert vectors and their metadata payloads."""

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        workspace_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return the nearest payloads within a workspace, with scores."""

    @abstractmethod
    def delete_by_document(
        self, collection_name: str, document_id: str, workspace_id: str
    ) -> None:
        """Delete every vector produced from a document."""

    @abstractmethod
    def health_check(self) -> bool:
        """Check connection health."""
