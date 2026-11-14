"""Deterministic hash-based embedding provider.

This is a *test* provider, not a product feature. It exists so the ingestion
pipeline and retrieval layer can be exercised in CI without network access or
API spend. It is never selected unless `LLM_PROVIDER=null` or `ENVIRONMENT=test`.

Unlike a random-vector mock, it is deterministic and similarity-preserving for
identical text, so `retrieve(x)` reliably finds the chunk containing `x`. A
random mock cannot verify retrieval at all.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import List

from app.services.embeddings.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class DeterministicEmbeddingProvider(EmbeddingProvider):
    name = "deterministic"

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    @property
    def available(self) -> bool:
        return True

    def get_dimension(self) -> int:
        return self.dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> List[float]:
        """Hash tokens into buckets, then L2-normalise (a hashing bag-of-words)."""
        vector = [0.0] * self.dimension
        for token in _TOKEN_RE.findall((text or "").lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            # An empty or symbol-only chunk still needs a valid unit vector.
            vector[0] = 1.0
            return vector
        return [v / norm for v in vector]
