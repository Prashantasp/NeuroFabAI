"""Ingestion pipeline and LLM response handling."""

import pytest

from app.services.llm.base import (
    LLMInvalidResponse,
    coerce_str_list,
    parse_json_response,
)
from app.tasks.document_tasks import PipelineError, chunk_text


# -- chunking ---------------------------------------------------------------


def test_chunking_covers_the_whole_document():
    text = " ".join(f"word{i}" for i in range(3000))
    chunks = chunk_text(text)

    assert chunks
    assert "word0" in chunks[0]
    assert "word2999" in chunks[-1]


def test_chunks_overlap_so_context_is_not_severed():
    text = ". ".join(f"Sentence number {i} about the pump" for i in range(400)) + "."
    chunks = chunk_text(text)

    assert len(chunks) > 1
    # Consecutive chunks must share text, or a fact spanning a boundary is lost.
    tail = chunks[0][-80:]
    assert any(fragment in chunks[1] for fragment in tail.split() if len(fragment) > 4)


def test_chunking_respects_the_configured_size():
    from app.core.config import get_settings

    settings = get_settings()
    chunks = chunk_text("x " * 5000)
    assert all(len(chunk) <= settings.CHUNK_SIZE + 50 for chunk in chunks)


def test_empty_text_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  \n ") == []


# -- text extraction --------------------------------------------------------


def test_a_scanned_pdf_fails_loudly(monkeypatch, tmp_path):
    """A PDF with no selectable text must fail, not silently substitute filler.

    The previous implementation replaced empty extractions with the literal
    string "Operational Manual for Industrial Assets." and carried on, producing
    a knowledge graph describing text that was never in the document.
    """
    import app.tasks.document_tasks as tasks

    class FakeStorage:
        def exists(self, key):
            return True

        def open(self, key):
            import io

            return io.BytesIO(b"%PDF-1.4 fake")

    class FakePage:
        def extract_text(self):
            return ""

    class FakeReader:
        is_encrypted = False
        pages = [FakePage(), FakePage()]

        def __init__(self, *args, **kwargs):
            pass

    # `extract_text` imports the provider inside the function, so the patch must
    # target the module it imports from.
    import app.services.storage as storage_module

    monkeypatch.setattr(storage_module, "get_storage_provider", lambda: FakeStorage())
    monkeypatch.setitem(
        __import__("sys").modules, "pypdf", type("m", (), {"PdfReader": FakeReader})
    )

    class Doc:
        id = "doc-1"
        file_path = "ws/doc-1/v1_scan.pdf"

    with pytest.raises(PipelineError) as exc:
        tasks.extract_text(Doc())

    assert "ocr" in str(exc.value).lower() or "scanned" in str(exc.value).lower()
    assert exc.value.retryable is False


def test_a_missing_file_is_not_retryable(monkeypatch):
    import app.tasks.document_tasks as tasks

    class FakeStorage:
        def exists(self, key):
            return False

    import app.services.storage as storage_module

    monkeypatch.setattr(storage_module, "get_storage_provider", lambda: FakeStorage())

    class Doc:
        id = "doc-1"
        file_path = "missing.pdf"

    with pytest.raises(PipelineError) as exc:
        tasks.extract_text(Doc())
    assert exc.value.retryable is False


# -- LLM response parsing ---------------------------------------------------


def test_plain_json_parses():
    assert parse_json_response('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json_parses():
    """Models wrap JSON in fences even when told not to."""
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('```\n{"a": 1}\n```') == {"a": 1}


def test_json_with_a_leading_sentence_parses():
    assert parse_json_response('Here is the result:\n{"a": 1}') == {"a": 1}


@pytest.mark.parametrize("raw", ["", "   ", None, "not json at all", "[1, 2, 3]", "{broken"])
def test_unparseable_output_raises_a_typed_error(raw):
    """Malformed model output must never surface as an unhandled 500."""
    with pytest.raises(LLMInvalidResponse):
        parse_json_response(raw)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        ("one", ["one"]),
        ("", []),
        (["a", "b"], ["a", "b"]),
        ([1, 2], ["1", "2"]),
        (["a", None, "  "], ["a"]),
    ],
)
def test_string_list_coercion(value, expected):
    assert coerce_str_list(value) == expected


# -- deterministic embeddings ----------------------------------------------


def test_deterministic_embeddings_are_stable_and_normalised():
    from app.services.embeddings.deterministic import DeterministicEmbeddingProvider

    provider = DeterministicEmbeddingProvider(dimension=64)
    first, second = provider.embed_texts(["pump bearing failure", "pump bearing failure"])

    assert first == second
    assert len(first) == 64
    assert abs(sum(v * v for v in first) ** 0.5 - 1.0) < 1e-6


def test_deterministic_embeddings_preserve_similarity():
    """Retrieval tests are only meaningful if similar text embeds similarly.

    A random-vector mock cannot verify retrieval at all.
    """
    from app.services.embeddings.deterministic import DeterministicEmbeddingProvider

    provider = DeterministicEmbeddingProvider(dimension=256)
    related, same, unrelated = provider.embed_texts(
        [
            "the pump bearing is overheating",
            "the pump bearing is overheating badly",
            "quarterly financial revenue projections",
        ]
    )

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    assert dot(related, same) > dot(related, unrelated)


def test_empty_text_still_produces_a_valid_unit_vector():
    from app.services.embeddings.deterministic import DeterministicEmbeddingProvider

    provider = DeterministicEmbeddingProvider(dimension=32)
    vector = provider.embed_texts(["!!!"])[0]
    assert len(vector) == 32
    assert abs(sum(v * v for v in vector) ** 0.5 - 1.0) < 1e-6


# -- knowledge validation ---------------------------------------------------


def _extraction(entities, relationships):
    from datetime import datetime, timezone

    from app.schemas.knowledge import (
        ConfidenceBand,
        Entity,
        KnowledgeGraphExtraction,
        Relationship,
    )

    now = datetime.now(timezone.utc)
    return KnowledgeGraphExtraction(
        entities=[
            Entity(
                id=e_id,
                type="Equipment",
                name=name,
                canonical_name=name,
                properties={},
                source_document_id="doc",
                evidence_snippet="",
                extraction_timestamp=now,
                confidence=0.9,
                confidence_label=ConfidenceBand.HIGH,
                version=1,
            )
            for e_id, name in entities
        ],
        relationships=[
            Relationship(
                source_entity_id=source,
                target_entity_id=target,
                type="CAUSES",
                source_document_id="doc",
                evidence="",
                extraction_timestamp=now,
                confidence=0.9,
                confidence_label=ConfidenceBand.HIGH,
                version=1,
            )
            for source, target in relationships
        ],
        version=1,
    )


def test_valid_extraction_reports_no_issues():
    from app.services.knowledge_validator import knowledge_validator

    extraction = _extraction([("1", "Pump"), ("2", "Bearing")], [("1", "2")])
    assert knowledge_validator.validate(extraction) == []


def test_dangling_relationship_is_reported():
    from app.services.knowledge_validator import knowledge_validator

    extraction = _extraction([("1", "Pump")], [("1", "missing")])
    issues = knowledge_validator.validate(extraction)
    assert any("unknown entity" in issue for issue in issues)


def test_self_referencing_relationship_is_reported():
    from app.services.knowledge_validator import knowledge_validator

    extraction = _extraction([("1", "Pump")], [("1", "1")])
    issues = knowledge_validator.validate(extraction)
    assert any("self-referencing" in issue for issue in issues)


def test_duplicate_canonical_names_are_reported():
    from app.services.knowledge_validator import knowledge_validator

    extraction = _extraction([("1", "Pump"), ("2", "Pump")], [])
    issues = knowledge_validator.validate(extraction)
    assert any("duplicate canonical" in issue for issue in issues)
