from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from app.services.embeddings.gemini import GeminiEmbeddingProvider
from app.services.vectorstore.qdrant import QdrantStore
from app.services.embedding_service import EmbeddingService

router = APIRouter()

provider = GeminiEmbeddingProvider()
store = QdrantStore()

class SearchQuery(BaseModel):
    query: str
    limit: int = 5

class SearchResult(BaseModel):
    id: str
    score: float
    payload: Dict[str, Any]

@router.post("/", response_model=List[SearchResult])
def semantic_search(search_query: SearchQuery):
    # 1. Embed the query
    query_vector = provider.embed_texts([search_query.query])[0]
    
    # 2. Search the vector store
    results = store.search(
        collection_name="neurofab_documents",
        query_vector=query_vector,
        limit=search_query.limit
    )
    
    return results
