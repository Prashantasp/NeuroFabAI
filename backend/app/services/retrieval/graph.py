"""Graph retrieval: resolve entities from text, then traverse the workspace graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.rag import EvidencePackage, QueryPlan
from app.services.entity_resolver import entity_resolver
from app.services.graph_service import get_graph_backend
from app.services.retrieval.base import RetrievalStrategy

DEFAULT_DEPTH = 2
MAX_SEED_ENTITIES = 6


class GraphRetrieval(RetrievalStrategy):
    def retrieve(
        self,
        query: str,
        plan: QueryPlan,
        workspace_id: str,
        semantic_chunks: Optional[List[Dict[str, Any]]] = None,
        depth: int = DEFAULT_DEPTH,
    ) -> EvidencePackage:
        if not workspace_id:
            raise ValueError("workspace_id is required for graph retrieval")

        backend = get_graph_backend()

        # Scan the query plus any retrieved text: an entity named only inside a
        # document chunk still deserves graph expansion.
        text_to_scan = query
        if semantic_chunks:
            text_to_scan += " " + " ".join(
                chunk.get("text", "") for chunk in semantic_chunks
            )

        topology = backend.get_topology(workspace_id)
        resolved = entity_resolver.extract_and_resolve(text_to_scan, topology)

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        for canonical in resolved[:MAX_SEED_ENTITIES]:
            subgraph = backend.get_subgraph(canonical, workspace_id, depth=depth)
            nodes.extend(subgraph.get("nodes", []))
            edges.extend(subgraph.get("edges", []))

        # Fall back to treating the raw query as a node name (handles a user
        # pasting an exact equipment tag that the resolver did not match).
        if not nodes and query.strip():
            subgraph = backend.get_subgraph(query.strip(), workspace_id, depth=depth)
            nodes.extend(subgraph.get("nodes", []))
            edges.extend(subgraph.get("edges", []))

        unique_nodes = list(
            {n.get("canonical_name") or n.get("id"): n for n in nodes if n}.values()
        )
        unique_edges = list(
            {
                (e.get("source"), e.get("target"), e.get("type")): e
                for e in edges
                if e
            }.values()
        )
        provenance = sorted(
            {e["source_document_id"] for e in unique_edges if e.get("source_document_id")}
        )

        return EvidencePackage(
            retrieved_chunks=[],
            retrieved_nodes=unique_nodes,
            retrieved_relationships=unique_edges,
            provenance_links=provenance,
            overall_confidence=0.85 if unique_nodes else 0.0,
        )
