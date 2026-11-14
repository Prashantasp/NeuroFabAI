"""Provider used when no AI credentials are configured.

It fails loudly rather than fabricating an answer. Silently degrading to canned
text is exactly what made the previous Copilot look functional while producing
no real reasoning.
"""

from __future__ import annotations

from typing import Iterator, Optional, Type

from pydantic import BaseModel

from app.services.llm.base import LLMNotConfigured, LLMProvider


class NullProvider(LLMProvider):
    name = "null"

    @property
    def available(self) -> bool:
        return False

    def _fail(self):
        raise LLMNotConfigured(
            "No AI provider is configured. Set GOOGLE_API_KEY (or GEMINI_API_KEY)."
        )

    def generate_text(self, prompt: str, *, system: Optional[str] = None) -> str:
        self._fail()

    def stream_text(self, prompt: str, *, system: Optional[str] = None) -> Iterator[str]:
        self._fail()
        yield ""  # pragma: no cover - unreachable, keeps the signature a generator

    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        *,
        system: Optional[str] = None,
    ) -> BaseModel:
        self._fail()
