"""LLM provider registry."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.llm.base import (
    LLMError,
    LLMInvalidResponse,
    LLMModelUnavailable,
    LLMNotConfigured,
    LLMProvider,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMTimeout,
    coerce_str_list,
    parse_json_response,
)
from app.services.llm.gemini import GeminiProvider
from app.services.llm.null import NullProvider

__all__ = [
    "LLMError",
    "LLMInvalidResponse",
    "LLMModelUnavailable",
    "LLMNotConfigured",
    "LLMProvider",
    "LLMQuotaExceeded",
    "LLMRateLimited",
    "LLMTimeout",
    "coerce_str_list",
    "parse_json_response",
    "get_llm_provider",
    "reset_llm_provider",
]


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER == "gemini" and settings.llm_api_key:
        return GeminiProvider(settings)
    return NullProvider()


def reset_llm_provider() -> None:
    """Clear the cached provider. Used by tests that swap configuration."""
    get_llm_provider.cache_clear()
