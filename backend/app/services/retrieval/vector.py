from app.schemas.rag import QueryPlan, EvidencePackage
from app.services.retrieval.base import RetrievalStrategy
from app.services.vectorstore.qdrant import QdrantStore
from app.services.embeddings.gemini import GeminiEmbeddingProvider

class VectorRetrieval(RetrievalStrategy):
    def __init__(self):
        self.vector_store = QdrantStore()
        self.embedder = GeminiEmbeddingProvider()

    def retrieve(self, query: str, plan: QueryPlan) -> EvidencePackage:
        query_vector = self.embedder.embed_texts([query])[0]
        results = self.vector_store.search(
            collection_name="neurofab_documents",
            query_vector=query_vector,
            limit=5
        )
        
        return EvidencePackage(
            retrieved_chunks=[r.get("payload", {}) for r in results],
            retrieved_nodes=[],
            retrieved_relationships=[],
            provenance_links=[],
            overall_confidence=0.8
        )
