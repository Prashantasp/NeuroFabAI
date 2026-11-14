"""Document upload, validation, listing, and deletion."""

import io

import pytest

MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def upload(client, account, *, name="manual.pdf", content=MINIMAL_PDF, content_type="application/pdf"):
    return client.post(
        "/api/v1/documents/upload",
        files={"file": (name, io.BytesIO(content), content_type)},
        headers=account.headers(),
    )


@pytest.fixture(autouse=True)
def _no_background_jobs(monkeypatch):
    """Upload tests assert on the API contract, not on ingestion side effects."""
    from app.services.task_service import task_service

    monkeypatch.setattr(
        task_service, "enqueue_document_processing", lambda **kwargs: None
    )


def test_upload_accepts_a_pdf(client, alice):
    response = upload(client, alice)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["filename"] == "manual.pdf"
    assert data["status"] == "QUEUED"
    # Fields the Knowledge Hub renders must be present in the schema.
    for field in ("current_stage", "progress_percentage", "failure_reason", "retryable"):
        assert field in data


def test_upload_rejects_a_non_pdf_extension(client, alice):
    response = upload(client, alice, name="payload.exe", content_type="application/pdf")
    assert response.status_code == 400


def test_upload_rejects_a_renamed_non_pdf(client, alice):
    """Extension and Content-Type are client-controlled; magic bytes are checked."""
    response = upload(client, alice, name="evil.pdf", content=b"MZ\x90\x00 not a pdf at all")
    assert response.status_code == 400
    assert "valid pdf" in response.json()["error"]["message"].lower()


def test_upload_rejects_an_empty_file(client, alice):
    response = upload(client, alice, content=b"")
    assert response.status_code == 400


def test_upload_rejects_a_file_over_the_size_limit(client, alice, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 100)
    response = upload(client, alice, content=MINIMAL_PDF + b"0" * 500)
    assert response.status_code == 413


def test_duplicate_content_is_rejected(client, alice):
    assert upload(client, alice).status_code == 201
    duplicate = upload(client, alice, name="copy.pdf")
    assert duplicate.status_code == 409


def test_the_same_document_may_exist_in_two_workspaces(client, alice, bob):
    """Dedupe is per workspace: two tenants may hold the same standards PDF."""
    assert upload(client, alice).status_code == 201
    assert upload(client, bob).status_code == 201


def test_path_traversal_in_the_filename_is_neutralised(client, alice):
    response = upload(client, alice, name="../../../../etc/passwd.pdf")
    assert response.status_code == 201
    stored = response.json()["data"]["filename"]
    assert ".." not in stored and "/" not in stored and "\\" not in stored


def test_listing_reports_a_real_total(client, alice):
    """`total_items` used to be len(page), making has_next permanently false."""
    for index in range(3):
        upload(client, alice, name=f"doc{index}.pdf", content=MINIMAL_PDF + bytes([index]))

    page = client.get(
        "/api/v1/documents?page=1&page_size=2", headers=alice.headers()
    ).json()["data"]

    assert len(page["items"]) == 2
    assert page["total_items"] == 3
    assert page["total_pages"] == 2
    assert page["has_next"] is True
    assert page["has_previous"] is False

    page_two = client.get(
        "/api/v1/documents?page=2&page_size=2", headers=alice.headers()
    ).json()["data"]
    assert len(page_two["items"]) == 1
    assert page_two["has_next"] is False
    assert page_two["has_previous"] is True


def test_search_filters_the_listing(client, alice):
    upload(client, alice, name="pump-manual.pdf", content=MINIMAL_PDF + b"a")
    upload(client, alice, name="valve-sop.pdf", content=MINIMAL_PDF + b"b")

    results = client.get(
        "/api/v1/documents?search=pump", headers=alice.headers()
    ).json()["data"]
    assert results["total_items"] == 1
    assert results["items"][0]["filename"] == "pump-manual.pdf"


def test_stats_aggregate_the_workspace(client, alice):
    upload(client, alice)
    stats = client.get("/api/v1/documents/stats", headers=alice.headers()).json()["data"]
    assert stats["total"] == 1
    assert "by_status" in stats


def test_a_document_cannot_be_read_from_another_workspace(client, alice, bob):
    document_id = upload(client, alice).json()["data"]["id"]
    response = client.get(f"/api/v1/documents/{document_id}", headers=bob.headers())
    assert response.status_code == 404


def test_a_document_cannot_be_downloaded_from_another_workspace(client, alice, bob):
    document_id = upload(client, alice).json()["data"]["id"]
    response = client.get(f"/api/v1/documents/{document_id}/download", headers=bob.headers())
    assert response.status_code == 404


def test_a_document_cannot_be_deleted_from_another_workspace(client, alice, bob):
    document_id = upload(client, alice).json()["data"]["id"]
    assert client.delete(
        f"/api/v1/documents/{document_id}", headers=bob.headers()
    ).status_code == 404
    # And it is still there for its owner.
    assert client.get(
        f"/api/v1/documents/{document_id}", headers=alice.headers()
    ).status_code == 200


def test_download_returns_the_original_bytes(client, alice):
    document_id = upload(client, alice).json()["data"]["id"]
    response = client.get(f"/api/v1/documents/{document_id}/download", headers=alice.headers())
    assert response.status_code == 200
    assert response.content == MINIMAL_PDF
    assert "attachment" in response.headers["content-disposition"]


def test_delete_removes_the_document(client, alice):
    document_id = upload(client, alice).json()["data"]["id"]
    assert client.delete(
        f"/api/v1/documents/{document_id}", headers=alice.headers()
    ).status_code == 200
    assert client.get(
        f"/api/v1/documents/{document_id}", headers=alice.headers()
    ).status_code == 404


def test_delete_purges_vectors_and_graph_nodes(client, alice, monkeypatch):
    """Deleting a document must not leave its content searchable."""
    purged = {}

    from app.services.vectorstore.qdrant import QdrantStore
    from app.services.graph_service import get_graph_backend
    monkeypatch.setattr(QdrantStore, "delete_by_document",
        lambda self, collection, document_id, workspace_id: purged.update(vector=document_id))
    monkeypatch.setattr(get_graph_backend().backend, "delete_document_subgraph",
        lambda document_id, workspace_id: purged.update(graph=document_id))

    document_id = upload(client, alice).json()["data"]["id"]
    client.delete(f"/api/v1/documents/{document_id}", headers=alice.headers())
    assert purged == {"vector": document_id, "graph": document_id}


def test_reprocess_requeues_a_ready_document(client, alice, db_session):
    from app.models.document import Document, DocumentStatus

    document_id = upload(client, alice).json()["data"]["id"]

    document = db_session.get(Document, document_id)
    document.status = DocumentStatus.READY
    db_session.commit()

    response = client.post(
        f"/api/v1/documents/{document_id}/reprocess", headers=alice.headers()
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "QUEUED"
    assert response.json()["data"]["retry_count"] == 1


def test_reprocess_is_refused_while_still_processing(client, alice, db_session):
    from app.models.document import Document, DocumentStatus

    document_id = upload(client, alice).json()["data"]["id"]
    document = db_session.get(Document, document_id)
    document.status = DocumentStatus.EMBEDDING
    db_session.commit()

    response = client.post(
        f"/api/v1/documents/{document_id}/reprocess", headers=alice.headers()
    )
    assert response.status_code == 409
