from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.services.vectorstore.base import VectorStore
import logging

logger = logging.getLogger(__name__)

# Singleton Qdrant Client to avoid file lock issues in local disk mode
_qdrant_client = QdrantClient(path="./qdrant_data")

class QdrantStore(VectorStore):
    """Qdrant implementation of the VectorStore using local disk mode for demo stability."""
    
    def __init__(self, dimension: int = 3072):
        # Use shared client instance
        self.client = _qdrant_client
        self.dimension = dimension
        
    def _ensure_collection(self, collection_name: str):
        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name not in collections:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
            
    def insert_vectors(self, collection_name: str, ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        self._ensure_collection(collection_name)
        
        points = [
            PointStruct(id=uid, vector=vec, payload=payload)
            for uid, vec, payload in zip(ids, vectors, payloads)
        ]
        
        self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        logger.info(f"Inserted {len(points)} vectors into {collection_name}")
        
    def search(self, collection_name: str, query_vector: List[float], limit: int = 5, filter_kwargs: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self._ensure_collection(collection_name)
        
        # We could build complex Qdrant Filter models here using filter_kwargs
        
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
        )
        
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload
            }
            for hit in results
        ]
