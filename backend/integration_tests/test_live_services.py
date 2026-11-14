"""Real PostgreSQL transactions/locks, Neo4j ownership, and cleanup across stores."""
import subprocess
import sys
import uuid

from sqlalchemy import text


def extraction(doc):
    from app.schemas.knowledge import Entity, Relationship, KnowledgeGraphExtraction
    common = {'source_document_id': doc, 'confidence': .9, 'confidence_label': 'High'}
    return KnowledgeGraphExtraction(entities=[
        Entity(id='pump', name='Pump', canonical_name='Pump', type='Equipment', evidence_snippet='Pump contains bearing.', **common),
        Entity(id='bearing', name='Bearing', canonical_name='Bearing', type='Component', evidence_snippet='Pump contains bearing.', **common),
    ], relationships=[
        Relationship(source_entity_id='pump', target_entity_id='bearing', type=kind,
            evidence='Pump contains bearing.', **common)
        for kind in ('HAS_COMPONENT', 'DRIVES')
    ])


def upload(client, account):
    # Real PDF extraction is covered separately; this fixture only needs valid upload magic.
    response = client.post('/api/v1/documents/upload', headers=account.headers,
        files={'file': ('manual.pdf', b'%PDF-1.4\n' + uuid.uuid4().hex.encode(), 'application/pdf')})
    assert response.status_code == 201, response.text
    return response.json()['data']['id']


def test_migration_and_jsonb_round_trip(live):
    from app.models.document_cleanup import DocumentCleanup
    with live.sessions() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version')) == 'cf3a1b6e9d02'
        assert db.scalar(text("SELECT data_type FROM information_schema.columns WHERE table_name='document_cleanup' AND column_name='file_paths'")) == 'jsonb'
        row = DocumentCleanup(document_id=str(uuid.uuid4()), workspace_id=str(uuid.uuid4()), file_paths=['a.pdf', 'old.pdf'])
        db.add(row)
        db.commit()
        db.expire_all()
        assert db.get(DocumentCleanup, row.document_id).file_paths == ['a.pdf', 'old.pdf']
        db.delete(row)
        db.commit()


def test_advisory_lock_excludes_other_process_and_releases(live):
    from app.services.workspace_lock import workspace_lock
    workspace = str(uuid.uuid4())
    code = '''
import sys
from app.db.session import engine
from app.services.workspace_lock import workspace_lock
with workspace_lock(engine, sys.argv[1]) as acquired:
    print(int(acquired), flush=True)
'''
    with workspace_lock(live.engine, workspace) as acquired:
        assert acquired
        result = subprocess.run([sys.executable, '-c', code, workspace], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == '0'
    result = subprocess.run([sys.executable, '-c', code, workspace], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '1'


def test_neo4j_preserves_sources_and_relationship_types(live):
    workspace = str(uuid.uuid4())
    live.workspace_ids.append(workspace)
    graph = live.graph
    graph.ingest_extraction(extraction('a'), workspace)
    graph.ingest_extraction(extraction('b'), workspace)
    topology = graph.get_topology(workspace)
    assert len(topology['nodes']) == 2 and len(topology['edges']) == 2
    assert {s['source_document_id'] for s in graph.get_node('Pump', workspace)['sources']} == {'a', 'b'}
    assert len(graph.get_subgraph('Pump', workspace, depth=2)['edges']) == 2
    assert graph.delete_document_subgraph('b', workspace) == 2
    assert graph.get_node('Pump', workspace)['source_document_id'] == 'a'
    assert len(graph.get_topology(workspace)['edges']) == 2
    replacement = extraction('a')
    replacement.relationships = replacement.relationships[:1]
    graph.ingest_extraction(replacement, workspace)
    assert len(graph.get_topology(workspace)['edges']) == 1
    assert graph.get_topology(str(uuid.uuid4())) == {'nodes': [], 'edges': []}


def test_refresh_rotation_uses_live_postgres(client, account):
    token = client.cookies.get('refresh_token')
    response = client.post('/api/v1/auth/refresh')
    assert response.status_code == 200, response.text
    assert client.cookies.get('refresh_token') != token
    client.cookies.clear()
    client.cookies.set('refresh_token', token)
    response = client.post('/api/v1/auth/refresh')
    assert response.status_code == 401
    assert any('Max-Age=0' in value for value in response.headers.get_list('set-cookie'))


def test_pipeline_replay_and_hydration(live, client, account, monkeypatch):
    from app.models.document import Document, DocumentStatus
    from app.tasks import document_tasks as tasks
    from app.services.graph_service import hydrate_graph_from_db
    doc_id = upload(client, account)
    monkeypatch.setattr(tasks, 'extract_text', lambda doc: ('Pump contains bearing.', 1))
    monkeypatch.setattr(tasks, 'build_knowledge_graph', lambda doc, chunks: extraction(doc.id))
    tasks.process_document_pipeline(doc_id, account.workspace_id)
    tasks.process_document_pipeline(doc_id, account.workspace_id)
    with live.sessions() as db:
        doc = db.get(Document, doc_id)
        assert doc.status == DocumentStatus.READY, doc.failure_reason
        assert doc.extracted_knowledge['entities']
        assert doc.entity_count == 2
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue
    count = live.vector.count(live.collection, count_filter=Filter(must=[FieldCondition(key='document_id', match=MatchValue(value=doc_id))]))
    assert count.count == 1
    live.graph.delete_document_subgraph(doc_id, account.workspace_id)
    assert hydrate_graph_from_db() >= 1
    assert len(live.graph.get_topology(account.workspace_id)['edges']) == 2


def test_delete_failure_is_durable_hidden_and_retried(live, client, account, monkeypatch):
    from app.models.document import Document
    from app.models.document_cleanup import DocumentCleanup
    from app.tasks.document_tasks import embed_and_index
    from app.services.graph_service import get_graph_backend
    from app.services.storage import get_storage_provider
    from app.services.task_service import TaskService
    doc_id = upload(client, account)
    with live.sessions() as db:
        doc = db.get(Document, doc_id)
        path = doc.file_path
        embed_and_index(doc, ['Pump contains bearing.'], 1)
    live.graph.ingest_extraction(extraction(doc_id), account.workspace_id)
    original = live.graph.delete_document_subgraph
    def offline(*args):
        raise ConnectionError('simulated graph outage')
    monkeypatch.setattr(live.graph, 'delete_document_subgraph', offline)
    response = client.delete(f'/api/v1/documents/{doc_id}', headers=account.headers)
    assert response.status_code == 200, response.text
    with live.sessions() as db:
        assert db.get(Document, doc_id) is None
        assert db.get(DocumentCleanup, doc_id) is not None
    assert get_graph_backend().get_topology(account.workspace_id)['nodes'] == []
    assert get_storage_provider().exists(path)
    monkeypatch.setattr(live.graph, 'delete_document_subgraph', original)
    TaskService().recover_cleanup()
    with live.sessions() as db:
        assert db.get(DocumentCleanup, doc_id) is None
    assert not get_storage_provider().exists(path)
    assert live.graph.get_topology(account.workspace_id)['nodes'] == []


def test_workspace_deletion_cascades_and_removes_versions(live, client, account):
    import io
    from app.models.document import Document, DocumentVersion
    from app.services.storage import get_storage_provider
    doc_id = upload(client, account)
    storage = get_storage_provider()
    old_path = storage.save(io.BytesIO(b'old'), f'{account.workspace_id}/old.pdf')
    with live.sessions() as db:
        path = db.get(Document, doc_id).file_path
        db.add(DocumentVersion(document_id=doc_id, version=2, file_path=old_path, storage_path=old_path, file_size=3, checksum='old'))
        db.commit()
    live.graph.ingest_extraction(extraction(doc_id), account.workspace_id)
    assert client.post('/api/v1/workspaces', json={'name': 'Keep'}, headers=account.headers).status_code == 201
    response = client.delete('/api/v1/workspaces/active', headers=account.headers)
    assert response.status_code == 200, response.text
    with live.sessions() as db:
        assert db.get(Document, doc_id) is None
        assert db.scalar(text('SELECT count(*) FROM document_versions WHERE document_id=:id'), {'id': doc_id}) == 0
    assert not storage.exists(path) and not storage.exists(old_path)
    assert live.graph.get_topology(account.workspace_id)['nodes'] == []


def test_worker_crash_releases_postgres_lock(live):
    import time
    from app.services.workspace_lock import workspace_lock
    workspace = str(uuid.uuid4())
    code = '''
import sys
from app.db.session import engine
from app.services.workspace_lock import workspace_lock
with workspace_lock(engine, sys.argv[1]) as acquired:
    print(int(acquired), flush=True)
    sys.stdin.readline()
'''
    worker = subprocess.Popen([sys.executable, '-c', code, workspace], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert worker.stdout.readline().strip() == '1'
        with workspace_lock(live.engine, workspace) as acquired:
            assert not acquired
        worker.kill()
        worker.wait(timeout=10)
        for _ in range(30):
            with workspace_lock(live.engine, workspace) as acquired:
                if acquired:
                    break
            time.sleep(.1)
        assert acquired
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.communicate(timeout=10)


def test_failed_graph_replacement_rolls_back_atomically(live):
    import pytest
    workspace = str(uuid.uuid4())
    live.workspace_ids.append(workspace)
    live.graph.ingest_extraction(extraction('atomic'), workspace)
    before = live.graph.get_topology(workspace)
    broken = extraction('atomic')
    broken.entities[1].properties = {'unserializable': object()}
    with pytest.raises(TypeError):
        live.graph.ingest_extraction(broken, workspace)
    assert live.graph.get_topology(workspace) == before
