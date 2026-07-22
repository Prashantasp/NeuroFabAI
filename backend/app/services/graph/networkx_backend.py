import logging
import networkx as nx
from typing import Dict, Any, List, Optional
from app.schemas.knowledge import KnowledgeGraphExtraction
from app.services.graph.base import GraphBackend

logger = logging.getLogger(__name__)

class NetworkXBackend(GraphBackend):
    def __init__(self):
        self.graph = nx.DiGraph()

    def ingest_extraction(self, extraction: KnowledgeGraphExtraction) -> None:
        logger.info(f"Ingesting {len(extraction.entities)} entities and {len(extraction.relationships)} relationships into NetworkX Graph.")
        
        for entity in extraction.entities:
            node_id = entity.canonical_name
            self.graph.add_node(
                node_id,
                uuid=entity.id,
                type=entity.type,
                canonical_name=entity.canonical_name,
                raw_name=entity.name,
                properties=entity.properties,
                confidence=entity.confidence,
                confidence_label=entity.confidence_label,
                source_document_id=entity.source_document_id,
                page_number=entity.page_number,
                evidence_snippet=entity.evidence_snippet,
                extraction_timestamp=entity.extraction_timestamp.isoformat(),
                version=entity.version
            )
            
        uuid_to_canonical = {entity.id: entity.canonical_name for entity in extraction.entities}
        
        for rel in extraction.relationships:
            source_node = uuid_to_canonical.get(rel.source_entity_id)
            target_node = uuid_to_canonical.get(rel.target_entity_id)
            
            if not source_node or not target_node:
                continue
                
            self.graph.add_edge(
                source_node,
                target_node,
                type=rel.type,
                confidence=rel.confidence,
                confidence_label=rel.confidence_label,
                evidence=rel.evidence,
                source_document_id=rel.source_document_id,
                page_number=rel.page_number,
                extraction_timestamp=rel.extraction_timestamp.isoformat(),
                version=rel.version
            )
        logger.info("Ingestion complete.")

    def get_stats(self) -> Dict[str, Any]:
        nodes = self.graph.nodes(data=True)
        edges = self.graph.edges(data=True)
        
        entity_types = {}
        for _, data in nodes:
            t = data.get("type", "Unknown")
            entity_types[t] = entity_types.get(t, 0) + 1
            
        rel_types = {}
        for _, _, data in edges:
            t = data.get("type", "Unknown")
            rel_types[t] = rel_types.get(t, 0) + 1
            
        return {
            "total_nodes": len(nodes),
            "total_relationships": len(edges),
            "entity_type_counts": entity_types,
            "relationship_type_counts": rel_types
        }

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if self.graph.has_node(node_id):
            return dict(self.graph.nodes[node_id])
        return None

    def get_subgraph(self, root_node_id: str, depth: int = 1) -> Dict[str, Any]:
        """Traverses the graph up to `depth` edges away from the root node."""
        if not self.graph.has_node(root_node_id):
            return {"nodes": [], "edges": []}
            
        # Extract ego graph
        subgraph = nx.ego_graph(self.graph, root_node_id, radius=depth, undirected=True)
        
        nodes = [{"id": n, **data} for n, data in subgraph.nodes(data=True)]
        edges = [{"source": u, "target": v, **data} for u, v, data in subgraph.edges(data=True)]
        
        return {"nodes": nodes, "edges": edges}

    def get_topology(self) -> Dict[str, Any]:
        """Returns all nodes and edges in the graph."""
        nodes = [{"id": n, **data} for n, data in self.graph.nodes(data=True)]
        edges = [{"source": u, "target": v, **data} for u, v, data in self.graph.edges(data=True)]
        
        return {"nodes": nodes, "edges": edges}
