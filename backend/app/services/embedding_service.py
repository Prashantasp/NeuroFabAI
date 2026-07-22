import time
import uuid
import logging
from typing import List, Dict, Any
from app.services.embeddings.base import EmbeddingProvider
from app.services.vectorstore.base import VectorStore

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider, vector_store: VectorStore, collection_name: str = "neurofab_documents"):
        self.provider = provider
        self.vector_store = vector_store
        self.collection_name = collection_name
        
    def process_chunks(self, chunks: List[str], base_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Embeds a list of chunks in batch and inserts them into the vector store.
        Returns performance metrics.
        """
        if not chunks:
            return {}
            
        start_time = time.time()
        
        # 1. Generate Embeddings (batch)
        embeddings = self.provider.embed_texts(chunks)
        embedding_time = time.time() - start_time
        
        # 2. Prepare Rich Chunk Metadata
        ids = []
        payloads = []
        total_chunks = len(chunks)
        
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = str(uuid.uuid4())
            ids.append(chunk_id)
            
            # Combine base metadata with chunk-specific metadata
            payload = {
                **base_metadata,
                "chunk_id": chunk_id,
                "chunk_index": i,
                "total_chunks": total_chunks,
                "text": chunk_text,
                "vector_dimension": self.provider.get_dimension()
            }
            payloads.append(payload)
            
        # 3. Insert into Vector Store
        index_start_time = time.time()
        self.vector_store.insert_vectors(
            collection_name=self.collection_name,
            ids=ids,
            vectors=embeddings,
            payloads=payloads
        )
        indexing_time = time.time() - index_start_time
        
        # 4. Calculate Metrics
        avg_chunk_size = sum(len(c) for c in chunks) / total_chunks if total_chunks > 0 else 0
        
        metrics = {
            "embedding_time": round(embedding_time, 3),
            "indexing_time": round(indexing_time, 3),
            "vector_count": total_chunks,
            "average_chunk_size": round(avg_chunk_size, 1)
        }
        
        logger.info(f"Embedded and indexed {total_chunks} chunks in {round(embedding_time + indexing_time, 3)}s")
        return metrics
