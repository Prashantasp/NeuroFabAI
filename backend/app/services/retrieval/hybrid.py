from app.schemas.rag import QueryPlan, EvidencePackage
from app.services.retrieval.base import RetrievalStrategy
from app.services.retrieval.vector import VectorRetrieval
from app.services.retrieval.graph import GraphRetrieval

class HybridRetrieval(RetrievalStrategy):
    def __init__(self):
        self.vector_strategy = VectorRetrieval()
        self.graph_strategy = GraphRetrieval()

    def retrieve(self, query: str, plan: QueryPlan) -> EvidencePackage:
        vec_evidence = self.vector_strategy.retrieve(query, plan)
        graph_evidence = self.graph_strategy.retrieve(query, plan)
        
        # We don't perform deep fusion here, the Orchestrator's EvidenceFusion step handles that.
        # Just combine the raw lists.
        return EvidencePackage(
            retrieved_chunks=vec_evidence.retrieved_chunks,
            retrieved_nodes=graph_evidence.retrieved_nodes,
            retrieved_relationships=graph_evidence.retrieved_relationships,
            provenance_links=vec_evidence.provenance_links + graph_evidence.provenance_links,
            overall_confidence=max(vec_evidence.overall_confidence, graph_evidence.overall_confidence)
        )
