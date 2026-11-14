"""Provider error classification and retry policy.

Regression cover for a failure found during live verification: the configured
model had been retired by the provider, the resulting 404 was not classified,
and it surfaced to the user as "The coordinator_synthesis step failed
unexpectedly" -- an unhelpful message that also leaked an internal step name.
"""

import pytest

from app.core.config import Settings
from app.services.llm.base import (
    LLMError,
    LLMModelUnavailable,
    LLMNotConfigured,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMTimeout,
)
from app.services.llm.gemini import GeminiProvider


def make_provider(**overrides) -> GeminiProvider:
    settings = Settings(
        ENVIRONMENT="test",
        GOOGLE_API_KEY="test-key",
        LLM_MAX_RETRIES=overrides.pop("retries", 0),
        **overrides,
    )
    return GeminiProvider(settings)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "404 NOT_FOUND. This model models/gemini-2.5-flash is no longer available "
            "to new users.",
            LLMModelUnavailable,
        ),
        ("429 RESOURCE_EXHAUSTED: rate limit exceeded", LLMRateLimited),
        ("You exceeded your current quota, please check billing", LLMQuotaExceeded),
        ("Deadline exceeded while awaiting response", LLMTimeout),
        (
            "503 UNAVAILABLE. This model is currently experiencing high demand.",
            LLMRateLimited,
        ),
        ("Connection reset by peer", LLMError),
        ("something entirely unexpected", LLMError),
    ],
)
def test_provider_errors_are_classified(message, expected):
    classified = GeminiProvider._classify(RuntimeError(message))
    assert isinstance(classified, expected)


def test_every_classification_is_an_llm_error():
    """No provider exception may escape untyped."""

    class Weird(Exception):
        pass

    assert isinstance(GeminiProvider._classify(Weird("???")), LLMError)


def test_classified_errors_carry_a_user_safe_message():
    error = GeminiProvider._classify(RuntimeError("404 NOT_FOUND models/x retired"))
    assert "models/" not in error.user_message
    assert "LLM_MODEL" in error.user_message  # actionable for an operator


def test_already_typed_errors_pass_through():
    original = LLMTimeout("slow")
    assert GeminiProvider._classify(original) is original


def test_transient_failures_are_retried():
    provider = make_provider(retries=2)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("Connection reset by peer")
        return "ok"

    assert provider._call_with_retry(flaky, op="test") == "ok"
    assert attempts["n"] == 3


def test_overload_is_retried_not_treated_as_a_missing_model():
    """503 is transient. Misreading it as a retired model would stop retries."""
    provider = make_provider(retries=2)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("503 UNAVAILABLE. This model is experiencing high demand.")
        return "ok"

    assert provider._call_with_retry(flaky, op="test") == "ok"
    assert attempts["n"] == 3


def test_model_unavailable_is_not_retried():
    """A retired model will never succeed on retry; retrying just adds latency."""
    provider = make_provider(retries=3)
    attempts = {"n": 0}

    def always_404():
        attempts["n"] += 1
        raise RuntimeError("404 NOT_FOUND: model no longer available")

    with pytest.raises(LLMModelUnavailable):
        provider._call_with_retry(always_404, op="test")
    assert attempts["n"] == 1


def test_quota_exhaustion_is_not_retried():
    provider = make_provider(retries=3)
    attempts = {"n": 0}

    def always_quota():
        attempts["n"] += 1
        raise RuntimeError("You exceeded your current quota")

    with pytest.raises(LLMQuotaExceeded):
        provider._call_with_retry(always_quota, op="test")
    assert attempts["n"] == 1


def test_retries_are_bounded():
    provider = make_provider(retries=1)
    attempts = {"n": 0}

    def always_fails():
        attempts["n"] += 1
        raise RuntimeError("Connection reset by peer")

    with pytest.raises(LLMError):
        provider._call_with_retry(always_fails, op="test")
    assert attempts["n"] == 2  # initial attempt + one retry


def test_provider_without_credentials_is_unavailable():
    provider = GeminiProvider(Settings(ENVIRONMENT="test", GOOGLE_API_KEY="", GEMINI_API_KEY=""))
    assert provider.available is False
    with pytest.raises(LLMNotConfigured):
        provider._get_client()


def test_configured_model_is_used_for_provider_requests():
    from types import SimpleNamespace
    seen = []
    provider = make_provider(LLM_MODEL="configured-model")
    def generate(**kwargs):
        seen.append(kwargs["model"])
        return SimpleNamespace(text="OK")
    provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    assert provider.generate_text("Reply OK") == "OK"
    assert seen == ["configured-model"]


def test_either_api_key_variable_works():
    assert Settings(ENVIRONMENT="test", GOOGLE_API_KEY="a", GEMINI_API_KEY="").llm_api_key == "a"
    assert Settings(ENVIRONMENT="test", GOOGLE_API_KEY="", GEMINI_API_KEY="b").llm_api_key == "b"
    # GOOGLE_API_KEY wins when both are set, matching the SDK's own precedence.
    assert Settings(ENVIRONMENT="test", GOOGLE_API_KEY="a", GEMINI_API_KEY="b").llm_api_key == "a"
