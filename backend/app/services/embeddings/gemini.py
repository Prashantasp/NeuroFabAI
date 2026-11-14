"""Gemini embedding provider.

Reads its credential from `Settings.llm_api_key`, the same place the reasoning
model does. Previously this read `os.environ["GOOGLE_API_KEY"]` directly while
the agent read `GEMINI_API_KEY`, so it was possible (and in practice was the
case) for embeddings to work while reasoning silently degraded.
"""

from __future__ import annotations

import logging
import random
import time
from typing import List

from app.core.config import Settings, get_settings
from app.services.embeddings.base import EmbeddingProvider, EmbeddingError

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._api_key = self._settings.llm_api_key
        self.model_name = self._settings.EMBEDDING_MODEL
        self.dimension = self._settings.EMBEDDING_DIMENSION
        self.batch_size = max(1, self._settings.EMBEDDING_BATCH_SIZE)
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if not self._api_key:
            raise EmbeddingError(
                "No embedding credential configured. Set GOOGLE_API_KEY (or GEMINI_API_KEY)."
            )
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                api_key=self._api_key,
                http_options={"timeout": int(self._settings.LLM_TIMEOUT_SECONDS * 1000)},
            )
        return self._client

    def get_dimension(self) -> int:
        return self.dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_client()
        vectors: List[List[float]] = []

        # Batched so a large document does not exceed the per-request payload
        # limit, and so a single failure retries a bounded amount of work.
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(client, batch))

        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"Embedding provider returned {len(vectors)} vectors for {len(texts)} inputs"
            )
        return vectors

    def _embed_batch(self, client, batch: List[str]) -> List[List[float]]:
        attempts = max(1, self._settings.LLM_MAX_RETRIES + 1)
        last: Exception | None = None

        for attempt in range(attempts):
            try:
                result = client.models.embed_content(model=self.model_name, contents=batch)
                embeddings = getattr(result, "embeddings", None)
                if not embeddings:
                    raise EmbeddingError("Embedding response contained no vectors")
                return [list(e.values) for e in embeddings]
            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt == attempts - 1:
                    break
                delay = (2**attempt) * 0.5 + random.uniform(0, 0.4)
                logger.warning(
                    "Embedding batch failed (attempt %d/%d): %s -- retrying in %.1fs",
                    attempt + 1, attempts, exc, delay,
                )
                time.sleep(delay)

        raise EmbeddingError(f"Failed to embed batch after {attempts} attempts: {last}") from last
