"""Application configuration.

All runtime configuration is resolved here from environment variables (or a local
`.env` file). Nothing else in the codebase should read `os.environ` directly --
that was the source of the split-brain API key bug where the embedding service
read GOOGLE_API_KEY while the reasoning agent read GEMINI_API_KEY and silently
degraded to canned responses.
"""

from functools import lru_cache
from typing import Annotated, List, Literal, Optional
import json

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

# Placeholder secrets that ship in .env.example. Booting production with any of
# these means anyone can forge a session token, so we refuse to start.
INSECURE_SECRETS = {
    "supersecretkey_change_me_in_production",
    "supersecretjwt_change_me_in_production",
    "changeme",
    "secret",
    "CHANGE_ME_access_token_signing_key_min_32_chars",
    "CHANGE_ME_refresh_token_signing_key_min_32_chars",
}


class Settings(BaseSettings):
    # --- General -----------------------------------------------------------
    PROJECT_NAME: str = "NeuroFab AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # --- Database ----------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg2://neurofab:neurofab_password@localhost:5432/neurofab_ai"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- Security ----------------------------------------------------------
    SECRET_KEY: str = "supersecretkey_change_me_in_production"
    JWT_SECRET: str = "supersecretjwt_change_me_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: Optional[str] = None

    PASSWORD_MIN_LENGTH: int = 10
    PASSWORD_MAX_LENGTH: int = 128

    # --- Rate limiting -----------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    # Auth endpoints are brute-force targets; chat endpoints cost real money.
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_CHAT_PER_MINUTE: int = 20
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120

    # --- AI provider -------------------------------------------------------
    # Either name works; GOOGLE_API_KEY is what the google-genai SDK itself uses.
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    LLM_PROVIDER: Literal["gemini", "null"] = "gemini"
    # Explicit, live-tested default; override when evaluating a different model.
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_MAX_RETRIES: int = 2
    LLM_TEMPERATURE: float = 0.2

    EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSION: int = 3072
    EMBEDDING_BATCH_SIZE: int = 32

    # --- Vector store ------------------------------------------------------
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "neurofab_documents"
    QDRANT_LOCAL_PATH: str = "./qdrant_data"

    # --- Graph store -------------------------------------------------------
    GRAPH_BACKEND: Literal["neo4j", "networkx"] = "neo4j"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neurofab_password"

    # --- Ingestion ---------------------------------------------------------
    STORAGE_DIR: str = "data/documents"
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024
    CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 200
    EXTRACTION_MAX_CHUNKS: int = 24

    # --- CORS --------------------------------------------------------------
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

    # --- Derived -----------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in ("production", "staging")

    @property
    def llm_api_key(self) -> str:
        """The single source of truth for the Gemini credential."""
        return (self.GOOGLE_API_KEY or self.GEMINI_API_KEY).strip()

    @property
    def ai_enabled(self) -> bool:
        return self.LLM_PROVIDER != "null" and bool(self.llm_api_key)

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        # Accept both a JSON array and a plain comma-separated list.
        if isinstance(v, str):
            if v.strip().startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def _enforce_production_hardening(self) -> "Settings":
        if not self.is_production:
            return self

        problems: List[str] = []
        if self.SECRET_KEY in INSECURE_SECRETS or len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be a unique value of at least 32 characters")
        if self.JWT_SECRET in INSECURE_SECRETS or len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be a unique value of at least 32 characters")
        if self.SECRET_KEY == self.JWT_SECRET:
            problems.append("SECRET_KEY and JWT_SECRET must differ")
        if not self.COOKIE_SECURE:
            problems.append("COOKIE_SECURE must be true so refresh cookies are HTTPS-only")
        if not self.DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
            problems.append("DATABASE_URL must use PostgreSQL for shared job ownership")
        if not self.QDRANT_URL:
            problems.append("QDRANT_URL must point to a shared vector server")
        if self.GRAPH_BACKEND != "neo4j":
            problems.append("GRAPH_BACKEND must be neo4j in production")
        if any(o.startswith("http://") for o in self.BACKEND_CORS_ORIGINS):
            problems.append("BACKEND_CORS_ORIGINS must not contain http:// origins")
        if "*" in self.BACKEND_CORS_ORIGINS:
            problems.append("BACKEND_CORS_ORIGINS must not be a wildcard when credentials are allowed")

        if problems:
            raise ValueError(
                "Refusing to start in "
                f"{self.ENVIRONMENT}. Fix the following configuration problems:\n  - "
                + "\n  - ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
