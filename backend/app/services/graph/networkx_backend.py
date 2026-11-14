"""In-memory NetworkX graph backend.

Used when Neo4j is unreachable, and for tests. Nodes are keyed by
`(workspace_id, document_id, canonical_name)` so two workspaces never share an entity, and
every read filters on workspace exactly.

This backend does not persist. `hydrate_graph_from_db()` rebuilds it from
PostgreSQL on startup, which is why `documents.extracted_knowledge` is the
source of truth rather than the graph itself.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from app.schemas.knowledge import KnowledgeGraphExtraction
from app.services.graph.base import GraphBackend
from app.services.graph.view import GraphReads, merge_topology

logger = logging.getLogger(__name__)

NodeKey = Tuple[str, str, str]  # (workspace_id, document_id, canonical_name)
_MAX_DEPTH = 3


class NetworkXBackend(GraphReads, GraphBackend):
    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()
        self._lock = threading.RLock()

    def health_check(self) -> bool:
        return True

    # -- writes -------------------------------------------------------------

    def ingest_extraction(
        self, extraction: KnowledgeGraphExtraction, workspace_id: str
    ) -> None:
        if not workspace_id:
            raise ValueError("workspace_id is required to ingest into the knowledge graph")

        with self._lock:
            documents = {entity.source_document_id for entity in extraction.entities}
            for document_id in documents:
                self.delete_document_subgraph(document_id, workspace_id)
            for entity in extraction.entities:
                self.graph.add_node(
                    (workspace_id, entity.source_document_id, entity.canonical_name),
                    id=entity.canonical_name,
                    name=entity.canonical_name,
                    canonical_name=entity.canonical_name,
                    raw_name=entity.name,
                    uuid=entity.id,
                    type=entity.type or "Entity",
                    group=(entity.type or "entity").lower(),
                    properties=entity.properties or {},
                    confidence=float(entity.confidence),
                    confidence_label=_enum_value(entity.confidence_label),
                    source_document_id=entity.source_document_id,
                    workspace_id=workspace_id,
                    page_number=entity.page_number,
                    evidence_snippet=entity.evidence_snippet,
                    extraction_timestamp=entity.extraction_timestamp.isoformat(),
                    version=entity.version,
                )

            id_to_canonical = {e.id: e.canonical_name for e in extraction.entities}
            for rel in extraction.relationships:
                source = id_to_canonical.get(rel.source_entity_id)
                target = id_to_canonical.get(rel.target_entity_id)
                if not source or not target:
                    continue
                self.graph.add_edge(
                    (workspace_id, rel.source_document_id, source),
                    (workspace_id, rel.source_document_id, target),
                    key=rel.type,
                    type=rel.type,
                    label=rel.type,
                    confidence=float(rel.confidence),
                    confidence_label=_enum_value(rel.confidence_label),
                    evidence=rel.evidence,
                    source_document_id=rel.source_document_id,
                    workspace_id=workspace_id,
                    page_number=rel.page_number,
                    extraction_timestamp=rel.extraction_timestamp.isoformat(),
                    version=rel.version,
                )

    def delete_document_subgraph(self, document_id: str, workspace_id: str) -> int:
        if not (document_id and workspace_id):
            return 0
        with self._lock:
            doomed = [
                key
                for key, data in self.graph.nodes(data=True)
                if key[0] == workspace_id and data.get("source_document_id") == document_id
            ]
            self.graph.remove_nodes_from(doomed)
        return len(doomed)

    def get_topology(self, workspace_id: str) -> Dict[str, Any]:
        with self._lock:
            return merge_topology({
                "nodes": [dict(data) for key, data in self.graph.nodes(data=True) if key[0] == workspace_id],
                "edges": [
                    {"source": u[2], "target": v[2], **data}
                    for u, v, data in self.graph.edges(data=True)
                    if u[0] == workspace_id and v[0] == workspace_id
                ],
            })


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))
