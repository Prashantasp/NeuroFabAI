"""Shared pytest fixtures.

Tests run against a per-test SQLite database and a stub LLM provider, so the
suite needs no Postgres, no Qdrant, no Neo4j, and makes no billed API calls.
"""

from __future__ import annotations

import os
from typing import Dict, Iterator, List, Optional, Type

# Must be set before any app module reads settings.
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL="sqlite://",
    LLM_PROVIDER="null",
    GOOGLE_API_KEY="",
    GEMINI_API_KEY="",
    GRAPH_BACKEND="networkx",
    RATE_LIMIT_ENABLED="false",
    EMBEDDING_DIMENSION="256",
    QDRANT_URL="",
    SECRET_KEY="test-secret-key-for-access-tokens-0123456789",
    JWT_SECRET="test-secret-key-for-refresh-tokens-9876543210",
)

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session", autouse=True)
def _reset_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_engine():
    """One in-memory SQLite database shared across connections for one test."""
    from app.models import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


# -- stub AI provider -------------------------------------------------------


class StubLLMProvider:
    """Records prompts and returns scripted responses.

    Lets the tests assert on real behaviour -- retries, malformed output,
    grounding -- without network access or API spend.
    """

    name = "stub"

    def __init__(self) -> None:
        self.available = True
        self.prompts: List[str] = []
        self.systems: List[Optional[str]] = []
        self.structured_response: Optional[Dict] = None
        self.raise_error: Optional[Exception] = None
        self.call_count = 0

    def generate_text(self, prompt: str, *, system: Optional[str] = None) -> str:
        self.prompts.append(prompt)
        return "stub response"

    def stream_text(self, prompt: str, *, system: Optional[str] = None):
        yield "stub"

    def generate_structured(
        self, prompt: str, schema: Type[BaseModel], *, system: Optional[str] = None
    ) -> BaseModel:
        self.call_count += 1
        self.prompts.append(prompt)
        self.systems.append(system)
        if self.raise_error is not None:
            raise self.raise_error
        payload = self.structured_response or {
            "executive_summary": "Bearing wear on Pump P-101 is indicated by the retrieved evidence.",
            "root_cause": "Skipped lubrication led to elevated bearing temperature.",
            "supporting_evidence": ["Maintenance log records a missed lubrication interval."],
            "recommended_action": "Inspect the outboard bearing and restore the lubrication schedule.",
            "business_impact": "Unplanned downtime risk on the primary transfer line.",
            "risk_level": "High",
            "confidence": 0.92,
        }
        return schema.model_validate(payload)


@pytest.fixture
def stub_llm(monkeypatch) -> StubLLMProvider:
    provider = StubLLMProvider()

    import app.services.agents.coordinator as coordinator
    import app.services.chat_service as chat_service
    import app.services.knowledge_extractor as extractor

    monkeypatch.setattr(coordinator, "get_llm_provider", lambda: provider)
    monkeypatch.setattr(chat_service, "get_llm_provider", lambda: provider)
    monkeypatch.setattr(extractor, "get_llm_provider", lambda: provider)
    return provider


# -- application client -----------------------------------------------------


@pytest.fixture
def client(db_engine, monkeypatch) -> Iterator[TestClient]:
    from app.api import deps
    from app.db import session as db_module
    from app.main import app
    from app.services.graph_service import reset_graph_backend

    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_module, "SessionLocal", factory)
    monkeypatch.setattr(deps, "SessionLocal", factory)

    # A fresh in-memory graph per test, so entities never leak between tests.
    reset_graph_backend()

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_get_db
    from app.db.session import get_db as session_get_db

    app.dependency_overrides[session_get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    reset_graph_backend()


# -- account helpers --------------------------------------------------------

VALID_PASSWORD = "Correct-Horse-9"


class Account:
    def __init__(self, client: TestClient, email: str, token: str, workspace_id: str):
        self.client = client
        self.email = email
        self.token = token
        self.workspace_id = workspace_id

    def headers(self, workspace_id: Optional[str] = None) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Workspace-ID": workspace_id or self.workspace_id,
        }


def register_and_login(client: TestClient, email: str, password: str = VALID_PASSWORD) -> Account:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test Engineer"},
    )
    assert response.status_code == 201, response.text

    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["access_token"]

    workspaces = client.get(
        "/api/v1/workspaces", headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]
    return Account(client, email, token, workspaces[0]["id"])


@pytest.fixture
def alice(client) -> Account:
    return register_and_login(client, "alice@example.com")


@pytest.fixture
def bob(client) -> Account:
    return register_and_login(client, "bob@example.com")


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch, tmp_path):
    from app.core.config import get_settings
    from app.services.storage import get_storage_provider
    import app.services.vectorstore.qdrant as module
    settings = get_settings()
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "documents"))
    get_storage_provider.cache_clear()
    local = None
    def client():
        nonlocal local
        if local is None:
            from qdrant_client import QdrantClient
            local = QdrantClient(path=str(tmp_path / "vectors"))
        return local
    original_client_factory = module.get_qdrant_client
    monkeypatch.setattr(module, "get_qdrant_client", client)
    yield original_client_factory
    if local is not None:
        local.close()
    get_storage_provider.cache_clear()
