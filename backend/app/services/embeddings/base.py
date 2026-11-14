from abc import ABC, abstractmethod
from typing import List


class EmbeddingError(Exception):
    """Raised when text cannot be embedded."""

    user_message = "Could not generate embeddings. Please try again later."


class EmbeddingProvider(ABC):
    """Abstract base class for embedding models."""

    name: str = "base"

    @property
    @abstractmethod
    def available(self) -> bool:
        """False when the provider has no usable credentials."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts. Output order matches input order."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Vector dimensionality. Must match the vector store collection."""
