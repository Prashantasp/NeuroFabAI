"""Opt-in local container tests; never use SQLite or in-memory graph fallbacks."""
import os
import uuid
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


@pytest.fixture(scope='session')
def live(tmp_path_factory):
    if os.environ.get('NEUROFAB_LIVE_TESTS') != '1':
        pytest.skip('Set NEUROFAB_LIVE_TESTS=1 and start docker compose first')
    from app.core.config import get_settings
    settings = get_settings()
    base_url = make_url(settings.DATABASE_URL)
    assert base_url.host in {'localhost', '127.0.0.1'}, 'Live tests require local PostgreSQL'
    assert urlsplit(settings.NEO4J_URI).hostname in {'localhost', '127.0.0.1'}
    assert urlsplit(settings.QDRANT_URL).hostname in {'localhost', '127.0.0.1'}
    name = 'neurofab_test_' + uuid.uuid4().hex
    admin = create_engine(base_url.set(database='postgres'), isolation_level='AUTOCOMMIT', poolclass=NullPool)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    patch = pytest.MonkeyPatch()
    graph = vector = None
    workspace_ids = []
    try:
        for key, value in {
            'DATABASE_URL': base_url.set(database=name).render_as_string(hide_password=False),
            'ENVIRONMENT': 'test', 'LLM_PROVIDER': 'null', 'GOOGLE_API_KEY': '', 'GEMINI_API_KEY': '',
            'GRAPH_BACKEND': 'neo4j', 'EMBEDDING_DIMENSION': '256', 'RATE_LIMIT_ENABLED': 'false',
            'QDRANT_COLLECTION': name, 'QDRANT_API_KEY': '', 'COOKIE_SECURE': 'false',
            'STORAGE_DIR': str(tmp_path_factory.mktemp('live-files')),
        }.items():
            patch.setenv(key, value)
        get_settings.cache_clear()
        from alembic.config import Config
        from alembic import command
        command.upgrade(Config('alembic.ini'), 'head')
        from app.db.session import engine, SessionLocal
        from app.services.graph.neo4j_backend import Neo4jBackend
        from app.services import graph_service
        graph = Neo4jBackend()
        assert graph.health_check()
        patch.setattr(graph_service, '_backend', graph)
        from app.services.vectorstore.qdrant import get_qdrant_client
        vector = get_qdrant_client()
        # Assert a live HTTP client, not QdrantLocal.
        assert type(vector._client).__name__ == 'QdrantRemote'
        yield SimpleNamespace(engine=engine, sessions=SessionLocal, graph=graph,
            vector=vector, collection=name, workspace_ids=workspace_ids)
    finally:
        if graph:
            with graph._get_session() as session:
                session.run('MATCH (n:Entity) WHERE n.workspace_id IN $ids DETACH DELETE n', ids=workspace_ids).consume()
            graph._driver.close()
        if vector:
            if vector.collection_exists(name):
                vector.delete_collection(name)
            vector.close()
        from app.db import session as db_module
        db_module.engine.dispose()
        with admin.connect() as conn:
            # Only the unique database created by this fixture is removed.
            assert name.startswith('neurofab_test_') and len(name) == 46
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
        patch.undo()
        get_settings.cache_clear()


@pytest.fixture
def client(live, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.task_service import task_service
    monkeypatch.setattr(task_service, 'enqueue_document_processing', lambda **kw: None)
    # Avoid startup replay of unrelated workspaces; tests invoke recovery explicitly.
    client = TestClient(app)
    yield client
    client.close()


@pytest.fixture
def account(client, live):
    email = uuid.uuid4().hex + '@example.com'
    password = 'Correct-Horse-9'
    response = client.post('/api/v1/auth/register', json={'email': email, 'password': password})
    assert response.status_code == 201, response.text
    response = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.text
    token = response.json()['data']['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    workspace = client.get('/api/v1/workspaces', headers=headers).json()['data'][0]['id']
    headers['X-Workspace-ID'] = workspace
    live.workspace_ids.append(workspace)
    return SimpleNamespace(headers=headers, workspace_id=workspace)
