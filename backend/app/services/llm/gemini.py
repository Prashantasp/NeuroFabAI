"""Google Gemini implementation of `LLMProvider`."""

from __future__ import annotations

import logging
import random
import time
from typing import Iterator, Optional, Type

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.services.llm.base import (
    LLMError,
    LLMInvalidResponse,
    LLMModelUnavailable,
    LLMNotConfigured,
    LLMProvider,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMTimeout,
    parse_json_response,
)

logger = logging.getLogger(__name__)

# Substrings used to classify vendor errors without depending on SDK exception
# types, which change between google-genai releases.
_RATE_LIMIT_MARKERS = ("429", "rate limit", "resource_exhausted", "too many requests")
_QUOTA_MARKERS = ("quota", "billing", "exceeded your current quota")
_TIMEOUT_MARKERS = ("timeout", "timed out", "deadline exceeded", "504")
# 503 UNAVAILABLE means the model is momentarily oversubscribed. It is transient
# and retryable, and reads to the user the same as being rate limited.
_OVERLOADED_MARKERS = ("503", "unavailable", "overloaded", "experiencing high demand")
_MODEL_MARKERS = (
    "404", "not_found", "is not found", "no longer available",
    "not supported for", "is not supported",
)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings):
        self._settings = settings
        self._api_key = settings.llm_api_key
        self._model = settings.LLM_MODEL
        self._client = None  # created lazily so import never needs credentials

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if not self._api_key:
            raise LLMNotConfigured(
                "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set on the server"
            )
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    # -- error mapping ------------------------------------------------------

    @staticmethod
    def _classify(exc: Exception) -> LLMError:
        """Map any provider failure onto a typed `LLMError`.

        Every branch returns an `LLMError`, including the fallback. An
        unclassified exception escaping this layer surfaces to the user as a
        generic 500 naming an internal agent step, which is both unhelpful and
        an information leak.
        """
        if isinstance(exc, LLMError):
            return exc

        text = f"{type(exc).__name__}: {exc}".lower()
        if any(m in text for m in _QUOTA_MARKERS):
            return LLMQuotaExceeded(str(exc))
        if any(m in text for m in _RATE_LIMIT_MARKERS):
            return LLMRateLimited(str(exc))
        if any(m in text for m in _TIMEOUT_MARKERS):
            return LLMTimeout(str(exc))
        # Checked before the model markers: a 503 body can also contain "not
        # available", which would otherwise be misread as a retired model.
        if any(m in text for m in _OVERLOADED_MARKERS):
            return LLMRateLimited(str(exc))
        if any(m in text for m in _MODEL_MARKERS):
            return LLMModelUnavailable(str(exc))

        logger.error("Unclassified provider error: %s", exc, exc_info=True)
        return LLMError(str(exc))

    def _call_with_retry(self, fn, *, op: str):
        """Run `fn`, retrying transient failures with jittered backoff.

        Quota exhaustion is never retried -- retrying a hard billing failure just
        multiplies the latency of an error the user has to see anyway.
        """
        attempts = max(1, self._settings.LLM_MAX_RETRIES + 1)
        last: Exception | None = None

        for attempt in range(attempts):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - re-raised after mapping
                mapped = self._classify(exc)
                last = mapped

                # Retrying a hard configuration failure only multiplies latency.
                if isinstance(
                    mapped, (LLMQuotaExceeded, LLMNotConfigured, LLMModelUnavailable)
                ):
                    raise mapped from exc
                if attempt == attempts - 1:
                    break

                delay = (2**attempt) * 0.5 + random.uniform(0, 0.4)
                logger.warning(
                    "LLM %s failed (attempt %d/%d): %s -- retrying in %.1fs",
                    op, attempt + 1, attempts, mapped, delay,
                )
                time.sleep(delay)

        logger.error("LLM %s failed after %d attempts: %s", op, attempts, last)
        raise last  # type: ignore[misc]

    def _config(self, *, system: Optional[str], json_mode: bool, schema=None):
        from google.genai import types

        kwargs = {
            "temperature": self._settings.LLM_TEMPERATURE,
            "http_options": types.HttpOptions(
                timeout=int(self._settings.LLM_TIMEOUT_SECONDS * 1000)
            ),
        }
        if system:
            kwargs["system_instruction"] = system
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        if schema is not None:
            kwargs["response_schema"] = schema
        return types.GenerateContentConfig(**kwargs)

    # -- LLMProvider --------------------------------------------------------

    def generate_text(self, prompt: str, *, system: Optional[str] = None) -> str:
        client = self._get_client()

        def _run() -> str:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._config(system=system, json_mode=False),
            )
            return response.text or ""

        return self._call_with_retry(_run, op="generate_text")

    def stream_text(self, prompt: str, *, system: Optional[str] = None) -> Iterator[str]:
        client = self._get_client()
        # The stream itself is not retried: once deltas have been sent to the
        # client, replaying from scratch would duplicate visible output.
        try:
            stream = client.models.generate_content_stream(
                model=self._model,
                contents=prompt,
                config=self._config(system=system, json_mode=False),
            )
            for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise self._classify(exc) from exc

    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        *,
        system: Optional[str] = None,
    ) -> BaseModel:
        client = self._get_client()

        def _run() -> BaseModel:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._config(system=system, json_mode=True, schema=schema),
            )

            # Prefer the SDK's own parsed object; fall back to tolerant parsing
            # when the model returns fenced or prefixed JSON.
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                return parsed

            data = parse_json_response(getattr(response, "text", None))
            try:
                return schema.model_validate(data)
            except ValidationError as exc:
                raise LLMInvalidResponse(
                    f"Model response did not match {schema.__name__}: {exc}"
                ) from exc

        return self._call_with_retry(_run, op="generate_structured")
