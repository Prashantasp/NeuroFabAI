"""Production configuration hardening.

The app must refuse to start in production with the placeholder secrets that
ship in `.env.example`; booting with them lets anyone forge a session token.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_A = "a-unique-secret-of-at-least-32-characters-long"
STRONG_B = "b-different-secret-of-at-least-32-characters"


def production(**overrides) -> Settings:
    base = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "QDRANT_URL": "http://localhost:6333",
        "GRAPH_BACKEND": "neo4j",
        "SECRET_KEY": STRONG_A,
        "JWT_SECRET": STRONG_B,
        "COOKIE_SECURE": True,
        "BACKEND_CORS_ORIGINS": ["https://app.example.com"],
    }
    base.update(overrides)
    return Settings(**base)


def test_valid_production_config_starts():
    settings = production()
    assert settings.is_production is True


def test_placeholder_secret_key_is_refused():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production(SECRET_KEY="supersecretkey_change_me_in_production")


def test_placeholder_jwt_secret_is_refused():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        production(JWT_SECRET="supersecretjwt_change_me_in_production")


def test_short_secret_is_refused():
    with pytest.raises(ValidationError, match="32 characters"):
        production(SECRET_KEY="too-short")


def test_identical_secrets_are_refused():
    """Sharing one key means a refresh token is accepted as an access token."""
    with pytest.raises(ValidationError, match="must differ"):
        production(JWT_SECRET=STRONG_A)


def test_insecure_cookie_is_refused_in_production():
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        production(COOKIE_SECURE=False)


def test_plaintext_cors_origin_is_refused_in_production():
    with pytest.raises(ValidationError, match="http://"):
        production(BACKEND_CORS_ORIGINS=["http://app.example.com"])


def test_wildcard_cors_origin_is_refused_in_production():
    with pytest.raises(ValidationError, match="wildcard"):
        production(BACKEND_CORS_ORIGINS=["*"])


def test_development_tolerates_defaults():
    """Local development must stay frictionless; only production is strict."""
    settings = Settings(ENVIRONMENT="development")
    assert settings.is_production is False
    assert settings.COOKIE_SECURE is False


def test_cors_origins_accept_a_comma_separated_list():
    settings = Settings(
        ENVIRONMENT="development",
        BACKEND_CORS_ORIGINS="http://localhost:3000, http://127.0.0.1:3000",
    )
    assert settings.BACKEND_CORS_ORIGINS == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_ai_is_disabled_without_a_key():
    # LLM_PROVIDER is passed explicitly: the test suite exports LLM_PROVIDER=null
    # into the environment, which Settings would otherwise inherit.
    def settings(**kwargs) -> Settings:
        return Settings(ENVIRONMENT="test", LLM_PROVIDER="gemini", **kwargs)

    assert settings(GOOGLE_API_KEY="", GEMINI_API_KEY="").ai_enabled is False
    assert settings(GOOGLE_API_KEY="k").ai_enabled is True
    # An explicit "null" provider disables AI even when a key is present.
    assert (
        Settings(ENVIRONMENT="test", LLM_PROVIDER="null", GOOGLE_API_KEY="k").ai_enabled
        is False
    )
