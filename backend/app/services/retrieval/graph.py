from app.schemas.rag import QueryPlan, EvidencePackage
from app.services.retrieval.base import RetrievalStrategy
from app.services.graph_service import graph_service
from app.services.entity_resolver import entity_resolver

class GraphRetrieval(RetrievalStrategy):
    def retrieve(self, query: str, plan: QueryPlan, semantic_chunks: list = None) -> EvidencePackage:
        nodes = []
        edges = []
        
        # 1. Gather text to scan
        text_to_scan = query + " "
        if semantic_chunks:
            text_to_scan += " ".join([chunk.get("text", "") for chunk in semantic_chunks])
            
        # 2. Get the full graph topology to extract entities dynamically
        topology = graph_service.get_topology()
        
        # 3. Resolve entities present in the text
        resolved_entities = entity_resolver.extract_and_resolve(text_to_scan, topology)
        
        # Determine traversal depth
        depth = 2
        
        # 4. Traverse the graph
        for canonical in resolved_entities:
            subgraph = graph_service.get_subgraph(canonical, depth=depth)
            nodes.extend(subgraph.get("nodes", []))
            edges.extend(subgraph.get("edges", []))
            
        # Optional: Deduplicate
        unique_nodes = {n["id"]: n for n in nodes}.values()
        unique_edges = {(e["source"], e["target"], e.get("type")): e for e in edges}.values()
            
        return EvidencePackage(
            retrieved_chunks=[],
            retrieved_nodes=list(unique_nodes),
            retrieved_relationships=list(unique_edges),
            provenance_links=[],
            overall_confidence=0.85
        )
