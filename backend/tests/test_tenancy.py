"""Cross-tenant isolation.

These cover the most serious defects found in the audit: `/chat/ask`,
`/graph/stats` and `/graph/topology` were entirely unauthenticated, and every
workspace-scoped endpoint trusted the client-supplied `X-Workspace-ID` header
without checking membership.
"""

import pytest

PROTECTED_GET = [
    "/api/v1/graph/stats",
    "/api/v1/graph/topology",
    "/api/v1/documents",
    "/api/v1/documents/stats",
    "/api/v1/chat/conversations",
    "/api/v1/workspaces",
    "/api/v1/health/status",
]


@pytest.mark.parametrize("path", PROTECTED_GET)
def test_endpoints_reject_anonymous_requests(client, path):
    response = client.get(path, headers={"X-Workspace-ID": "any-workspace"})
    assert response.status_code == 401, f"{path} served an anonymous request"


def test_chat_ask_rejects_anonymous_requests(client):
    """Unauthenticated access here also meant unmetered, billable model calls."""
    response = client.post(
        "/api/v1/chat/ask",
        json={"query": "Why is the pump overheating?"},
        headers={"X-Workspace-ID": "any-workspace"},
    )
    assert response.status_code == 401


def test_chat_stream_rejects_anonymous_requests(client):
    response = client.post(
        "/api/v1/chat/stream",
        json={"query": "Why is the pump overheating?"},
        headers={"X-Workspace-ID": "any-workspace"},
    )
    assert response.status_code == 401


def test_search_rejects_anonymous_requests(client):
    response = client.post(
        "/api/v1/search",
        json={"query": "pump"},
        headers={"X-Workspace-ID": "any-workspace"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path", ["/api/v1/graph/stats", "/api/v1/graph/topology", "/api/v1/documents"]
)
def test_user_cannot_read_another_users_workspace(client, alice, bob, path):
    """Alice presents a valid token with Bob's workspace id in the header."""
    response = client.get(path, headers=alice.headers(workspace_id=bob.workspace_id))
    assert response.status_code == 404, f"{path} leaked another tenant's workspace"


def test_user_cannot_query_the_copilot_against_another_workspace(client, alice, bob, stub_llm):
    response = client.post(
        "/api/v1/chat/ask",
        json={"query": "What equipment is here?"},
        headers=alice.headers(workspace_id=bob.workspace_id),
    )
    assert response.status_code == 404
    # The model must never be reached for an unauthorised workspace.
    assert stub_llm.call_count == 0


def test_user_cannot_list_members_of_another_workspace(client, alice, bob):
    response = client.get(
        "/api/v1/workspaces/active/members", headers=alice.headers(workspace_id=bob.workspace_id)
    )
    assert response.status_code == 404


def test_workspace_list_only_contains_own_workspaces(client, alice, bob):
    alice_ids = {
        w["id"] for w in client.get("/api/v1/workspaces", headers=alice.headers()).json()["data"]
    }
    assert bob.workspace_id not in alice_ids


def test_unknown_workspace_id_is_rejected(client, alice):
    response = client.get(
        "/api/v1/documents", headers=alice.headers(workspace_id="00000000-0000-0000-0000-000000000000")
    )
    assert response.status_code == 404


def test_graph_stats_are_scoped_per_workspace(client, alice, bob, db_session):
    """Ingesting into Alice's workspace must not be visible from Bob's."""
    from datetime import datetime, timezone

    from app.schemas.knowledge import ConfidenceBand, Entity, KnowledgeGraphExtraction
    from app.services.graph_service import get_graph_backend

    extraction = KnowledgeGraphExtraction(
        entities=[
            Entity(
                id="e1",
                type="Equipment",
                name="Pump P-101",
                canonical_name="Pump P-101",
                properties={},
                source_document_id="doc-1",
                evidence_snippet="Pump P-101 is on the transfer line.",
                extraction_timestamp=datetime.now(timezone.utc),
                confidence=0.95,
                confidence_label=ConfidenceBand.HIGH,
                version=1,
            )
        ],
        relationships=[],
        version=1,
    )
    get_graph_backend().ingest_extraction(extraction, workspace_id=alice.workspace_id)

    alice_stats = client.get("/api/v1/graph/stats", headers=alice.headers()).json()["data"]
    bob_stats = client.get("/api/v1/graph/stats", headers=bob.headers()).json()["data"]

    assert alice_stats["total_nodes"] == 1
    assert bob_stats["total_nodes"] == 0


def test_same_entity_name_in_two_workspaces_stays_separate(client, alice, bob):
    """Node identity is (workspace_id, canonical_name).

    The previous Neo4j schema merged on canonical_name alone, so two tenants
    documenting 'Pump P-101' shared one node and its relationships.
    """
    from datetime import datetime, timezone

    from app.schemas.knowledge import ConfidenceBand, Entity, KnowledgeGraphExtraction
    from app.services.graph_service import get_graph_backend

    backend = get_graph_backend()

    def extraction(document_id: str, snippet: str) -> KnowledgeGraphExtraction:
        return KnowledgeGraphExtraction(
            entities=[
                Entity(
                    id=f"e-{document_id}",
                    type="Equipment",
                    name="Pump P-101",
                    canonical_name="Pump P-101",
                    properties={},
                    source_document_id=document_id,
                    evidence_snippet=snippet,
                    extraction_timestamp=datetime.now(timezone.utc),
                    confidence=0.9,
                    confidence_label=ConfidenceBand.HIGH,
                    version=1,
                )
            ],
            relationships=[],
            version=1,
        )

    backend.ingest_extraction(extraction("alice-doc", "Alice secret"), alice.workspace_id)
    backend.ingest_extraction(extraction("bob-doc", "Bob secret"), bob.workspace_id)

    alice_node = backend.get_node("Pump P-101", alice.workspace_id)
    bob_node = backend.get_node("Pump P-101", bob.workspace_id)

    assert alice_node["evidence_snippet"] == "Alice secret"
    assert bob_node["evidence_snippet"] == "Bob secret"
    assert alice_node["source_document_id"] != bob_node["source_document_id"]


def test_missing_workspace_header_falls_back_to_the_users_own_workspace(client, alice):
    response = client.get(
        "/api/v1/documents", headers={"Authorization": f"Bearer {alice.token}"}
    )
    assert response.status_code == 200
