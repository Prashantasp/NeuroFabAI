"""Extract a knowledge graph from document text using the configured LLM."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.knowledge import (
    ConfidenceBand,
    Entity,
    KnowledgeGraphExtraction,
    Relationship,
)
from app.services.entity_resolver import entity_resolver
from app.services.llm import LLMError, LLMNotConfigured, get_llm_provider

logger = logging.getLogger(__name__)

ENTITY_TYPES = (
    "Equipment", "Component", "FailureMode", "Process", "Material",
    "Measurement", "Standard", "Document", "Location", "Role",
)

SYSTEM_PROMPT = f"""You extract structured knowledge graphs from industrial and \
technical documentation (SOPs, maintenance manuals, inspection reports).

Extract only entities and relationships that are explicitly stated in the text. \
Do not infer plant equipment that is not mentioned. Do not invent tag numbers.

Use these entity types where they fit: {', '.join(ENTITY_TYPES)}.
Use SCREAMING_SNAKE_CASE relationship types such as HAS_COMPONENT, \
HAS_FAILURE_MODE, CAUSES, INDICATES, REQUIRES, PREVENTS, MEASURED_BY, \
GOVERNED_BY, LOCATED_IN, PERFORMED_BY.

Preserve explicit causal direction: when the text says X causes or produces Y,
emit X --CAUSES--> Y, not INDICATES. INDICATES is reserved for a symptom pointing
to a condition, not a condition producing a symptom. Include each explicitly
stated cause/effect pair. Preserve qualifiers such as "blocked" on the causal
entity so an equipment component is not inherently labelled as a failure.

Every relationship's source and target must exactly match an entity name you \
returned. Set confidence to how clearly the text supports each extraction.
"""


class ExtractedEntity(BaseModel):
    name: str = Field(description="Entity name exactly as written in the text.")
    type: str = Field(description="One of the allowed entity types.")
    properties_json: str = Field(
        default="{}",
        description='JSON object of attributes stated in the text, e.g. {"tag":"P-101"}.',
    )
    evidence_snippet: str = Field(description="Short verbatim quote supporting this entity.")
    confidence: float = Field(description="0.0-1.0 confidence.")


class ExtractedRelationship(BaseModel):
    source_entity_name: str
    target_entity_name: str
    type: str = Field(description="SCREAMING_SNAKE_CASE relationship type.")
    evidence: str = Field(description="Short verbatim quote supporting this relationship.")
    confidence: float = Field(description="0.0-1.0 confidence.")


class ExtractionResult(BaseModel):
    entities: List[ExtractedEntity] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)


def confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.90:
        return ConfidenceBand.HIGH
    if score >= 0.75:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def _parse_properties(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": raw[:500]}


class KnowledgeExtractor:
    def extract_from_chunks(
        self, document_id: str, chunks: List[str]
    ) -> KnowledgeGraphExtraction:
        """Extract entities and relationships. Raises on model failure.

        Callers are expected to mark the document's graph stage as FAILED rather
        than silently storing an empty graph -- an empty result is
        indistinguishable from "this document contains no knowledge", which
        previously made extraction failures invisible.
        """
        settings = get_settings()
        provider = get_llm_provider()

        if not provider.available:
            # Specific rather than the generic LLMError, so the document's
            # failure_reason tells the operator to set a key instead of
            # suggesting a transient outage they should wait out.
            raise LLMNotConfigured(
                "No language model configured; knowledge-graph extraction was skipped."
            )
        if not chunks:
            return KnowledgeGraphExtraction(entities=[], relationships=[], version=1)

        text = "\n\n".join(chunks[: settings.EXTRACTION_MAX_CHUNKS])
        prompt = f"Extract the knowledge graph from this document text.\n\nTEXT:\n{text}"

        result = provider.generate_structured(prompt, ExtractionResult, system=SYSTEM_PROMPT)
        return self._to_domain(document_id, result, text)

    @staticmethod
    def _to_domain(document_id: str, result: ExtractionResult, source_text: str) -> KnowledgeGraphExtraction:
        now = datetime.now(timezone.utc)
        normalized = " ".join(source_text.split())

        def supported(quote):
            quote = " ".join((quote or "").split())
            return bool(quote) and quote in normalized

        entities: List[Entity] = []
        # Canonical name -> id, so two mentions of the same entity in one
        # document collapse into a single node instead of duplicating it.
        canonical_to_id: Dict[str, str] = {}
        name_to_id: Dict[str, str] = {}

        for raw in result.entities:
            name = (raw.name or "").strip()
            if not name or not supported(raw.evidence_snippet):
                continue
            canonical = entity_resolver.resolve(name)

            if canonical in canonical_to_id:
                name_to_id[name] = canonical_to_id[canonical]
                continue

            entity_id = str(uuid.uuid4())
            canonical_to_id[canonical] = entity_id
            name_to_id[name] = entity_id

            score = max(0.0, min(1.0, float(raw.confidence or 0.0)))
            entities.append(
                Entity(
                    id=entity_id,
                    type=(raw.type or "Entity").strip(),
                    name=name,
                    canonical_name=canonical,
                    properties=_parse_properties(raw.properties_json),
                    source_document_id=document_id,
                    page_number=None,
                    evidence_snippet=(raw.evidence_snippet or "")[:1000],
                    extraction_timestamp=now,
                    confidence=score,
                    confidence_label=confidence_band(score),
                    version=1,
                )
            )

        relationships: List[Relationship] = []
        seen: set = set()
        for raw in result.relationships:
            if not supported(raw.evidence):
                continue
            source_id = name_to_id.get((raw.source_entity_name or "").strip())
            target_id = name_to_id.get((raw.target_entity_name or "").strip())
            # Drop dangling references and self-loops; the validator rejects both
            # and one bad edge should not fail the whole document.
            if not source_id or not target_id or source_id == target_id:
                continue

            rel_type = (raw.type or "RELATED_TO").strip().upper().replace(" ", "_")
            key = (source_id, target_id, rel_type)
            if key in seen:
                continue
            seen.add(key)

            score = max(0.0, min(1.0, float(raw.confidence or 0.0)))
            relationships.append(
                Relationship(
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    type=rel_type,
                    source_document_id=document_id,
                    page_number=None,
                    evidence=(raw.evidence or "")[:1000],
                    extraction_timestamp=now,
                    confidence=score,
                    confidence_label=confidence_band(score),
                    version=1,
                )
            )

        logger.info(
            "Extracted %d entities and %d relationships from document %s",
            len(entities), len(relationships), document_id,
        )
        return KnowledgeGraphExtraction(
            entities=entities, relationships=relationships, version=1
        )


knowledge_extractor = KnowledgeExtractor()
