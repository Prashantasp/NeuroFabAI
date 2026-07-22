from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    """Abstract base class for embedding models."""
    
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Given a list of texts, return a list of embeddings (float vectors)."""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Return the vector dimensionality (e.g. 1536 for OpenAI, 768 for Gemini/Mock)."""
        pass
