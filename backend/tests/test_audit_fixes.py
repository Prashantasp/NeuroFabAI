"""Regressions for the production-readiness audit."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from tests.test_config import production
from tests.test_documents import upload
from tests.test_pipeline import _extraction


@pytest.mark.parametrize('field,value', [
    ('SECRET_KEY', 'CHANGE_ME_access_token_signing_key_min_32_chars'),
    ('JWT_SECRET', 'CHANGE_ME_refresh_token_signing_key_min_32_chars'),
    ('QDRANT_URL', ''), ('GRAPH_BACKEND', 'networkx'), ('DATABASE_URL', 'sqlite://'),
])
def test_production_rejects_unsafe_templates(field, value):
    with pytest.raises(ValidationError):
        production(**{field: value})


@pytest.mark.parametrize('value', ['https://a.example, https://b.example', '["https://a.example", "https://b.example"]'])
def test_cors_is_parsed_from_environment(monkeypatch, value):
    from app.core.config import Settings
    monkeypatch.setenv('BACKEND_CORS_ORIGINS', value)
    assert Settings(_env_file=None).BACKEND_CORS_ORIGINS == ['https://a.example', 'https://b.example']


@pytest.mark.parametrize('token', ['', 'expired.invalid.token'])
def test_failed_refresh_clears_cookies_on_actual_response(client, token):
    client.cookies.set('nf_session', '1')
    if token:
        client.cookies.set('refresh_token', token)
    response = client.post('/api/v1/auth/refresh')
    assert response.status_code == 401
    cookies = response.headers.get_list('set-cookie')
    assert any('refresh_token=' in c and 'Max-Age=0' in c for c in cookies)
    assert any('nf_session=' in c and 'Max-Age=0' in c for c in cookies)


def extraction(document_id):
    result = _extraction([('1', 'Pump'), ('2', 'Bearing')], [('1', '2')])
    for item in [*result.entities, *result.relationships]:
        item.source_document_id = document_id
    result.relationships.append(result.relationships[0].model_copy(update={'type': 'HAS_COMPONENT'}))
    return result


def test_graph_preserves_shared_sources_and_multiple_relationship_types():
    from app.services.graph.networkx_backend import NetworkXBackend
    graph = NetworkXBackend()
    for doc in ('a', 'b'):
        graph.ingest_extraction(extraction(doc), 'ws')
    node = graph.get_node('Pump', 'ws')
    assert {s['source_document_id'] for s in node['sources']} == {'a', 'b'}
    assert {e['type'] for e in graph.get_topology('ws')['edges']} == {'CAUSES', 'HAS_COMPONENT'}
    graph.delete_document_subgraph('b', 'ws')
    assert len(graph.get_topology('ws')['edges']) == 2
    assert graph.get_node('Pump', 'ws')['source_document_id'] == 'a'
    assert graph.get_topology('other') == {'nodes': [], 'edges': []}
    replacement = extraction('a')
    replacement.relationships = []
    graph.ingest_extraction(replacement, 'ws')
    assert graph.get_topology('ws')['edges'] == []


def test_recovery_includes_recent_jobs_and_more_than_fifty(client, db_session, monkeypatch):
    from app.models.document import Document, DocumentStatus
    from app.services.task_service import TaskService
    for i in range(65):
        db_session.add(Document(id=str(i), workspace_id='ws', owner_id='owner', title='test',
            filename='a.pdf', file_path='a.pdf', file_size=1, mime_type='application/pdf',
            checksum=str(i), status=DocumentStatus.EMBEDDING, started_at=datetime.now(timezone.utc)))
    db_session.commit()
    service = TaskService()
    queued = []
    monkeypatch.setattr(service, 'enqueue_document_processing', lambda **kw: queued.append(kw) or True)
    assert service.recover_stuck_documents() == 65
    assert len({job['document_id'] for job in queued}) == 65


def test_workspace_lock_excludes_duplicate_processing(client, db_engine, monkeypatch):
    from app.services.workspace_lock import workspace_lock
    import app.tasks.document_tasks as tasks
    calls = []
    monkeypatch.setattr(tasks, '_process_document_pipeline', lambda *args: calls.append(args))
    with workspace_lock(db_engine, 'ws') as acquired:
        assert acquired
        tasks.process_document_pipeline('doc', 'ws')
    assert calls == []
    tasks.process_document_pipeline('doc', 'ws')
    assert len(calls) == 1


def test_index_retry_uses_same_point_ids(client, monkeypatch):
    from app.tasks.document_tasks import embed_and_index
    from app.services.vectorstore.qdrant import QdrantStore
    calls = []
    monkeypatch.setattr(QdrantStore, 'insert_vectors', lambda self, collection, ids, vectors, payloads: calls.append(ids))
    doc = SimpleNamespace(id='doc', workspace_id='ws', filename='a.pdf', title='manual')
    embed_and_index(doc, ['Pump contains a bearing.'], 1)
    embed_and_index(doc, ['Pump contains a bearing.'], 1)
    assert calls[0] == calls[1]


def test_failed_cleanup_is_hidden_and_retried(client, alice, db_session, monkeypatch):
    from app.models.document import Document
    from app.models.document_cleanup import DocumentCleanup
    from app.services.task_service import task_service
    from app.services.vectorstore.qdrant import QdrantStore
    from app.services.graph_service import get_graph_backend
    from app.services.storage import get_storage_provider
    from app.services.cleanup_service import cleanup_workspace
    from tests.test_retrieval import index_chunks
    monkeypatch.setattr(task_service, 'enqueue_document_processing', lambda **kw: None)
    doc_id = upload(client, alice).json()['data']['id']
    path = db_session.get(Document, doc_id).file_path
    index_chunks(alice.workspace_id, doc_id, ['Pump contains a bearing.'])
    graph = get_graph_backend()
    graph.ingest_extraction(extraction(doc_id), alice.workspace_id)
    original = QdrantStore.delete_by_document
    def fail(*args):
        raise ConnectionError('offline')
    monkeypatch.setattr(QdrantStore, 'delete_by_document', fail)
    assert client.delete(f'/api/v1/documents/{doc_id}', headers=alice.headers()).status_code == 200
    assert db_session.get(DocumentCleanup, doc_id) is not None
    assert graph.get_topology(alice.workspace_id)['nodes'] == []
    results = client.post('/api/v1/search', json={'query': 'Pump bearing', 'strategy': 'semantic'}, headers=alice.headers())
    assert results.json()['data'] == []
    assert get_storage_provider().exists(path)
    monkeypatch.setattr(QdrantStore, 'delete_by_document', original)
    assert cleanup_workspace(db_session, alice.workspace_id) == 1
    assert not get_storage_provider().exists(path)
    assert db_session.get(DocumentCleanup, doc_id) is None


def test_delete_is_rejected_during_ingestion(client, alice, db_engine, monkeypatch):
    from app.services.workspace_lock import workspace_lock
    from app.services.task_service import task_service
    monkeypatch.setattr(task_service, 'enqueue_document_processing', lambda **kw: None)
    doc_id = upload(client, alice).json()['data']['id']
    with workspace_lock(db_engine, alice.workspace_id):
        assert client.delete(f'/api/v1/documents/{doc_id}', headers=alice.headers()).status_code == 409
    assert client.get(f'/api/v1/documents/{doc_id}', headers=alice.headers()).status_code == 200


def test_graph_server_outage_never_falls_back_in_production(monkeypatch):
    from app.core.config import get_settings
    import app.services.graph_service as module
    monkeypatch.setattr(get_settings(), 'ENVIRONMENT', 'production')
    monkeypatch.setattr(get_settings(), 'GRAPH_BACKEND', 'neo4j')
    monkeypatch.setattr(module, 'Neo4jBackend', lambda: SimpleNamespace(health_check=lambda: False))
    with pytest.raises(ConnectionError):
        module._build_backend()


def test_extraction_drops_invented_quotes(stub_llm):
    from app.services.knowledge_extractor import knowledge_extractor
    stub_llm.structured_response = {'entities': [
        {'name': 'Pump', 'type': 'Equipment', 'evidence_snippet': 'Pump contains a bearing.', 'confidence': .9},
        {'name': 'Reactor', 'type': 'Equipment', 'evidence_snippet': 'The reactor explodes.', 'confidence': .99},
    ], 'relationships': []}
    result = knowledge_extractor.extract_from_chunks('doc', ['Pump contains a bearing.'])
    assert [e.name for e in result.entities] == ['Pump']


@pytest.mark.parametrize('bad', [None, 'quote', 'source', 'uncovered'])
def test_citations_require_real_quotes_and_cover_every_claim(stub_llm, bad):
    from app.schemas.agents import AgentState
    from app.services.agents.coordinator import coordinator_synthesis
    quote = 'Pump contains a bearing.'
    state = AgentState(query='What does the pump contain?', workspace_id='ws',
        semantic_chunks=[{'text': quote, 'document_id': 'doc'}])
    stub_llm.structured_response = {'executive_summary': quote, 'root_cause': '',
        'recommended_action': '', 'business_impact': '', 'supporting_evidence': [],
        'risk_level': None, 'confidence': .99,
        'references': [{'claim': quote, 'quote': quote, 'source_id': 'C1'}]}
    if bad == 'quote':
        stub_llm.structured_response['references'][0]['quote'] = 'Pump pressure is 999 bar.'
    elif bad == 'source':
        stub_llm.structured_response['references'][0]['source_id'] = 'C99'
    elif bad == 'uncovered':
        stub_llm.structured_response['recommended_action'] = 'Replace everything.'
    decision = coordinator_synthesis(state).final_decision
    assert decision.grounded is False and decision.confidence is None
    assert decision.evidence_status == ('insufficient' if bad else 'references_checked')
    if bad:
        assert decision.risk_level is None
    if bad is None:
        assert len(decision.citations) == 1
        assert decision.citations[0].document_id == 'doc'


def test_vector_server_outage_never_falls_back_in_production(monkeypatch, isolated_storage):
    from app.core.config import get_settings
    from app.services.vectorstore.base import VectorStoreError
    import app.services.vectorstore.qdrant as module
    monkeypatch.setattr(get_settings(), 'ENVIRONMENT', 'production')
    monkeypatch.setattr(get_settings(), 'QDRANT_URL', 'https://vector.example.com')
    monkeypatch.setattr(module, '_client', None)
    calls = []
    def unavailable(**kwargs):
        calls.append(kwargs)
        raise ConnectionError('offline')
    monkeypatch.setattr(module, 'QdrantClient', unavailable)
    with pytest.raises(VectorStoreError):
        isolated_storage()
    assert len(calls) == 1 and 'path' not in calls[0]


def test_workspace_delete_removes_all_version_files(client, alice, db_session, monkeypatch):
    import io
    from app.models.document import Document, DocumentVersion
    from app.services.storage import get_storage_provider
    from app.services.task_service import task_service
    monkeypatch.setattr(task_service, 'enqueue_document_processing', lambda **kw: None)
    doc_id = upload(client, alice).json()['data']['id']
    original = db_session.get(Document, doc_id).file_path
    storage = get_storage_provider()
    historical = storage.save(io.BytesIO(b'older'), 'history/old.pdf')
    db_session.add(DocumentVersion(document_id=doc_id, version=2, file_path=historical,
        storage_path=historical, file_size=5, checksum='older'))
    db_session.commit()
    assert client.post('/api/v1/workspaces', json={'name': 'Keep'}, headers=alice.headers()).status_code == 201
    response = client.delete('/api/v1/workspaces/active', headers=alice.headers())
    assert response.status_code == 200, response.text
    assert not storage.exists(original)
    assert not storage.exists(historical)


def test_neo4j_replacement_and_writes_are_scoped_to_document():
    from app.services.graph.neo4j_backend import Neo4jBackend
    calls = []
    class Transaction:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def run(self, query, **params): calls.append((query, params))
        def begin_transaction(self): return self
    backend = object.__new__(Neo4jBackend)
    backend._get_session = lambda: Transaction()
    backend.ingest_extraction(extraction('a'), 'ws')
    assert 'DETACH DELETE' in calls[0][0]
    assert calls[0][1] == {'ws_id': 'ws', 'documents': ['a']}
    for query, params in calls[1:]:
        assert params['source_document_id'] == 'a'
        assert params['workspace_id'] == 'ws'
        assert 'source_document_id: $source_document_id' in query
    assert sum('MERGE (s)-[r:' in query for query, _ in calls) == 2


def test_interrupted_pipeline_recovers_without_duplicates(client, alice, db_session, monkeypatch):
    from app.models.document import Document, DocumentStatus
    from app.services.task_service import task_service
    from app.services.vectorstore.qdrant import get_qdrant_client
    from app.services.graph_service import get_graph_backend
    from app.core.config import get_settings
    import app.tasks.document_tasks as tasks
    monkeypatch.setattr(task_service, 'enqueue_document_processing', lambda **kw: None)
    doc_id = upload(client, alice).json()['data']['id']
    monkeypatch.setattr(tasks, 'extract_text', lambda doc: ('Pump contains a bearing.', 1))
    def crash(*args):
        raise SystemExit('worker lost after vector indexing')
    monkeypatch.setattr(tasks, 'build_knowledge_graph', crash)
    with pytest.raises(SystemExit):
        tasks.process_document_pipeline(doc_id, alice.workspace_id)
    db_session.expire_all()
    assert db_session.get(Document, doc_id).status == DocumentStatus.KNOWLEDGE_GRAPH
    calls = []
    def extract(doc, chunks):
        calls.append(doc.id)
        return extraction(doc.id)
    monkeypatch.setattr(tasks, 'build_knowledge_graph', extract)
    tasks.process_document_pipeline(doc_id, alice.workspace_id)
    tasks.process_document_pipeline(doc_id, alice.workspace_id)
    db_session.expire_all()
    doc = db_session.get(Document, doc_id)
    assert doc.status == DocumentStatus.READY
    assert doc.retry_count == 1
    assert doc.extracted_knowledge['entities']
    assert calls == [doc_id]
    assert get_qdrant_client().count(get_settings().QDRANT_COLLECTION).count == 1
    assert len(get_graph_backend().get_topology(alice.workspace_id)['edges']) == 2
