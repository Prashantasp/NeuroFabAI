from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class VectorStore(ABC):
    """Abstract base class for vector databases."""
    
    @abstractmethod
    def insert_vectors(self, collection_name: str, ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        """Insert vectors and rich metadata payloads into the store."""
        pass
        
    @abstractmethod
    def search(self, collection_name: str, query_vector: List[float], limit: int = 5, filter_kwargs: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search the vector store and return matching payloads with their scores."""
        pass
