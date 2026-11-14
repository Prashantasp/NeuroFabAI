"""End-to-end retrieval: ingest text, then prove the Copilot actually reads it.

These use the deterministic embedding provider and an in-memory Qdrant, so no
network calls or API spend are involved, but the code path exercised is the real
one: chunk -> embed -> index -> vector search -> graph traversal -> prompt.
"""

from datetime import datetime, timezone

import pytest

from app.schemas.knowledge import (
    ConfidenceBand,
    Entity,
    KnowledgeGraphExtraction,
    Relationship,
)


@pytest.fixture
def qdrant(monkeypatch, tmp_path):
    """A throwaway on-disk Qdrant instance scoped to one test."""
    from qdrant_client import QdrantClient

    import app.services.vectorstore.qdrant as qdrant_module

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    monkeypatch.setattr(qdrant_module, "get_qdrant_client", lambda: client)
    yield client
    client.close()


def index_chunks(workspace_id: str, document_id: str, chunks: list[str]) -> None:
    import uuid

    from app.core.config import get_settings
    from app.services.embeddings import get_embedding_provider
    from app.services.vectorstore.qdrant import QdrantStore

    settings = get_settings()
    provider = get_embedding_provider()
    store = QdrantStore(dimension=provider.get_dimension())

    vectors = provider.embed_texts(chunks)
    store.insert_vectors(
        settings.QDRANT_COLLECTION,
        [str(uuid.uuid4()) for _ in chunks],
        vectors,
        [
            {
                "text": chunk,
                "chunk_index": index,
                "document_id": document_id,
                "workspace_id": workspace_id,
                "source_filename": "pump-manual.pdf",
                "document_title": "Pump Manual",
            }
            for index, chunk in enumerate(chunks)
        ],
    )


def ingest_graph(workspace_id: str) -> None:
    from app.services.graph_service import get_graph_backend

    now = datetime.now(timezone.utc)

    def entity(entity_id: str, name: str, entity_type: str) -> Entity:
        return Entity(
            id=entity_id,
            type=entity_type,
            name=name,
            canonical_name=name,
            properties={},
            source_document_id="doc-1",
            evidence_snippet=f"{name} appears in the manual.",
            extraction_timestamp=now,
            confidence=0.95,
            confidence_label=ConfidenceBand.HIGH,
            version=1,
        )

    extraction = KnowledgeGraphExtraction(
        entities=[
            entity("e1", "Pump P-101", "Equipment"),
            entity("e2", "Outboard Bearing", "Component"),
            entity("e3", "Overheating", "FailureMode"),
        ],
        relationships=[
            Relationship(
                source_entity_id="e1",
                target_entity_id="e2",
                type="HAS_COMPONENT",
                source_document_id="doc-1",
                evidence="Pump P-101 contains an outboard bearing.",
                extraction_timestamp=now,
                confidence=0.9,
                confidence_label=ConfidenceBand.HIGH,
                version=1,
            ),
            Relationship(
                source_entity_id="e2",
                target_entity_id="e3",
                type="CAUSES",
                source_document_id="doc-1",
                evidence="Bearing wear causes overheating.",
                extraction_timestamp=now,
                confidence=0.88,
                confidence_label=ConfidenceBand.HIGH,
                version=1,
            ),
        ],
        version=1,
    )
    get_graph_backend().ingest_extraction(extraction, workspace_id=workspace_id)


def test_indexed_text_reaches_the_model_prompt(client, alice, stub_llm, qdrant):
    """The retrieved document text must actually appear in what the model sees."""
    index_chunks(
        alice.workspace_id,
        "doc-1",
        [
            "Pump P-101 outboard bearing temperature exceeded 95 degrees celsius on 14 March.",
            "Unrelated appendix about warehouse inventory codes and shipping labels.",
        ],
    )

    response = client.post(
        "/api/v1/chat/ask",
        json={"query": "What was the Pump P-101 bearing temperature?"},
        headers=alice.headers(),
    )
    assert response.status_code == 200

    prompt = stub_llm.prompts[-1]
    assert "95 degrees celsius" in prompt
    assert response.json()["data"]["decision"]["grounded"] is False
    assert response.json()["data"]["decision"]["evidence_status"] == "insufficient"


def test_graph_relationships_reach_the_model_prompt(client, alice, stub_llm, qdrant):
    ingest_graph(alice.workspace_id)

    client.post(
        "/api/v1/chat/ask",
        json={"query": "Why is Pump P-101 overheating?"},
        headers=alice.headers(),
    )

    prompt = stub_llm.prompts[-1]
    assert "Pump P-101" in prompt
    assert "HAS_COMPONENT" in prompt or "CAUSES" in prompt


def test_reliability_signals_are_computed_from_the_graph(client, alice, stub_llm, qdrant):
    """The maintenance agent reports classified facts, not invented prose."""
    ingest_graph(alice.workspace_id)

    client.post(
        "/api/v1/chat/ask",
        json={"query": "Why is Pump P-101 overheating?"},
        headers=alice.headers(),
    )

    prompt = stub_llm.prompts[-1]
    assert "Overheating" in prompt
    assert "severity_hint" in prompt


def test_another_workspace_sees_none_of_the_indexed_text(client, alice, bob, stub_llm, qdrant):
    index_chunks(alice.workspace_id, "doc-1", ["Alice's confidential turbine specification."])

    client.post(
        "/api/v1/chat/ask",
        json={"query": "turbine specification"},
        headers=bob.headers(),
    )

    assert "confidential" not in stub_llm.prompts[-1]


def test_semantic_search_finds_indexed_content(client, alice, qdrant):
    index_chunks(
        alice.workspace_id,
        "doc-1",
        [
            "The lubrication schedule for Pump P-101 requires grease every 500 hours.",
            "Warehouse inventory codes for shipping labels and pallet identifiers.",
        ],
    )

    response = client.post(
        "/api/v1/search",
        json={"query": "lubrication schedule pump", "strategy": "semantic", "limit": 5},
        headers=alice.headers(),
    )
    assert response.status_code == 200
    results = response.json()["data"]
    assert results
    assert "lubrication" in results[0]["snippet"].lower()


def test_search_does_not_cross_workspaces(client, alice, bob, qdrant):
    index_chunks(alice.workspace_id, "doc-1", ["Alice's confidential turbine specification."])

    results = client.post(
        "/api/v1/search",
        json={"query": "turbine specification", "strategy": "semantic"},
        headers=bob.headers(),
    ).json()["data"]
    assert results == []


def test_keyword_search_works(client, alice, qdrant, db_session):
    """Regression: this raised AttributeError on `doc.summary`, which did not exist."""
    from app.models.document import Document, DocumentStatus

    from app.models.user import User

    owner_id = db_session.query(User).filter(User.email == alice.email).one().id

    db_session.add(
        Document(
            title="Pump Maintenance Manual",
            filename="pump-manual.pdf",
            file_path="ws/doc/pump.pdf",
            workspace_id=alice.workspace_id,
            owner_id=owner_id,
            file_size=1024,
            mime_type="application/pdf",
            checksum="abc123",
            status=DocumentStatus.READY,
            summary="Covers lubrication and bearing inspection.",
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/search",
        json={"query": "Pump", "strategy": "keyword"},
        headers=alice.headers(),
    )
    assert response.status_code == 200
    results = response.json()["data"]
    assert results
    assert results[0]["title"] == "Pump Maintenance Manual"
    assert "lubrication" in results[0]["snippet"]


def test_graph_search_returns_entities(client, alice, qdrant):
    ingest_graph(alice.workspace_id)

    results = client.post(
        "/api/v1/search",
        json={"query": "Pump P-101", "strategy": "graph"},
        headers=alice.headers(),
    ).json()["data"]

    assert results
    assert results[0]["title"] == "Pump P-101"
    assert results[0]["payload"]["connected_count"] >= 1


def test_graph_node_endpoint_returns_a_neighbourhood(client, alice):
    ingest_graph(alice.workspace_id)

    response = client.get("/api/v1/graph/nodes/Pump P-101?depth=2", headers=alice.headers())
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["node"]["canonical_name"] == "Pump P-101"
    names = {n["canonical_name"] for n in data["subgraph"]["nodes"]}
    assert "Outboard Bearing" in names


def test_graph_node_from_another_workspace_is_not_found(client, alice, bob):
    ingest_graph(alice.workspace_id)
    response = client.get("/api/v1/graph/nodes/Pump P-101", headers=bob.headers())
    assert response.status_code == 404


def test_deleting_a_document_removes_its_vectors(client, alice, qdrant):
    from app.core.config import get_settings
    from app.services.embeddings import get_embedding_provider
    from app.services.vectorstore.qdrant import QdrantStore

    settings = get_settings()
    index_chunks(alice.workspace_id, "doc-1", ["Distinctive turbine calibration procedure."])

    provider = get_embedding_provider()
    store = QdrantStore(dimension=provider.get_dimension())

    before = store.search(
        settings.QDRANT_COLLECTION,
        provider.embed_texts(["turbine calibration"])[0],
        alice.workspace_id,
        limit=5,
    )
    assert before

    store.delete_by_document(settings.QDRANT_COLLECTION, "doc-1", alice.workspace_id)

    after = store.search(
        settings.QDRANT_COLLECTION,
        provider.embed_texts(["turbine calibration"])[0],
        alice.workspace_id,
        limit=5,
    )
    assert after == []
