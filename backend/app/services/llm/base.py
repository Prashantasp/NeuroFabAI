"""Provider-agnostic LLM interface.

Everything in the application talks to an `LLMProvider`, never to a vendor SDK
directly. Swapping Gemini for another model means adding one file here and
changing `LLM_PROVIDER`.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional, Type

from pydantic import BaseModel


class LLMError(Exception):
    """Base class for all provider failures."""

    #: Message safe to show an end user. Never contains provider internals.
    user_message = "The AI service is temporarily unavailable. Please try again."


class LLMNotConfigured(LLMError):
    user_message = "AI features are not configured on this server."


class LLMTimeout(LLMError):
    user_message = "The AI service took too long to respond. Please try again."


class LLMRateLimited(LLMError):
    user_message = "The AI service is busy right now. Please retry in a moment."


class LLMQuotaExceeded(LLMError):
    user_message = "The AI usage quota for this deployment has been exhausted."


class LLMInvalidResponse(LLMError):
    user_message = "The AI returned a malformed response. Please try again."


class LLMModelUnavailable(LLMError):
    """The configured model does not exist or was retired by the provider."""

    user_message = (
        "The configured AI model is unavailable. An administrator needs to update "
        "LLM_MODEL on the server."
    )


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_json_response(raw: Optional[str]) -> Dict[str, Any]:
    """Parse model output into a dict, tolerating the usual LLM formatting noise.

    Models wrap JSON in markdown fences or add a leading sentence even when told
    not to. A malformed response must never surface as a 500.
    """
    if not raw or not raw.strip():
        raise LLMInvalidResponse("Model returned an empty response")

    text = raw.strip()

    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} span.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMInvalidResponse("Model response contained no JSON object")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMInvalidResponse(f"Model response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMInvalidResponse("Model response was not a JSON object")
    return parsed


def coerce_str_list(value: Any, *, limit: int = 12) -> List[str]:
    """Normalise a field that should be a list of strings but may not be."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                # Blank strings must be dropped, not stringified -- they render
                # as empty evidence bullets in the UI.
                if item.strip():
                    out.append(item.strip())
            elif isinstance(item, dict):
                out.append(json.dumps(item, ensure_ascii=False))
            else:
                out.append(str(item))
        return out[:limit]
    return [str(value)]


class LLMProvider(ABC):
    """Minimal surface the application needs from a language model."""

    name: str = "base"

    @property
    @abstractmethod
    def available(self) -> bool:
        """False when the provider has no usable credentials."""

    @abstractmethod
    def generate_text(self, prompt: str, *, system: Optional[str] = None) -> str:
        """Return a plain-text completion."""

    @abstractmethod
    def stream_text(self, prompt: str, *, system: Optional[str] = None) -> Iterator[str]:
        """Yield incremental text deltas."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        *,
        system: Optional[str] = None,
    ) -> BaseModel:
        """Return a validated instance of `schema`."""
