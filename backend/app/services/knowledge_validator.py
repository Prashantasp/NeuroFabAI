"""Validate an extraction before it reaches the knowledge graph.

Returns a list of problems rather than a bool so a failure can tell the operator
what was wrong instead of just "validation failed".
"""

from __future__ import annotations

import logging
from typing import List

from app.schemas.knowledge import KnowledgeGraphExtraction

logger = logging.getLogger(__name__)

MAX_ENTITIES = 500
MAX_RELATIONSHIPS = 1500


class KnowledgeValidator:
    def validate(self, extraction: KnowledgeGraphExtraction) -> List[str]:
        issues: List[str] = []

        entity_ids = {e.id for e in extraction.entities}
        if len(entity_ids) != len(extraction.entities):
            issues.append("duplicate entity IDs")

        canonical_names = [e.canonical_name for e in extraction.entities]
        if len(set(canonical_names)) != len(canonical_names):
            issues.append("duplicate canonical entity names")

        if any(not e.canonical_name.strip() for e in extraction.entities):
            issues.append("an entity has an empty canonical name")

        if len(extraction.entities) > MAX_ENTITIES:
            issues.append(f"too many entities ({len(extraction.entities)} > {MAX_ENTITIES})")
        if len(extraction.relationships) > MAX_RELATIONSHIPS:
            issues.append(
                f"too many relationships ({len(extraction.relationships)} > {MAX_RELATIONSHIPS})"
            )

        dangling = 0
        self_links = 0
        for rel in extraction.relationships:
            if rel.source_entity_id not in entity_ids or rel.target_entity_id not in entity_ids:
                dangling += 1
            elif rel.source_entity_id == rel.target_entity_id:
                self_links += 1

        if dangling:
            issues.append(f"{dangling} relationship(s) reference an unknown entity")
        if self_links:
            issues.append(f"{self_links} self-referencing relationship(s)")

        if issues:
            logger.warning("Knowledge validation failed: %s", "; ".join(issues))
        else:
            logger.info(
                "Knowledge validation passed (%d entities, %d relationships)",
                len(extraction.entities), len(extraction.relationships),
            )
        return issues


knowledge_validator = KnowledgeValidator()
