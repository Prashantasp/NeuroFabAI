"""Embedding provider registry."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.embeddings.base import EmbeddingError, EmbeddingProvider
from app.services.embeddings.deterministic import DeterministicEmbeddingProvider
from app.services.embeddings.gemini import GeminiEmbeddingProvider

__all__ = [
    "EmbeddingError",
    "EmbeddingProvider",
    "get_embedding_provider",
    "reset_embedding_provider",
]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER == "gemini" and settings.llm_api_key:
        return GeminiEmbeddingProvider(settings)
    # No credential: fall back to the deterministic provider so ingestion and
    # retrieval still work end-to-end locally and in CI.
    return DeterministicEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)


def reset_embedding_provider() -> None:
    get_embedding_provider.cache_clear()
