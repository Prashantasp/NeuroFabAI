import random
from typing import List
from app.services.embeddings.base import EmbeddingProvider

class MockEmbeddingProvider(EmbeddingProvider):
    """A mock embedding provider for robust testing without API dependencies."""
    
    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # Generate random normalized vectors
        embeddings = []
        for _ in texts:
            vec = [random.uniform(-1, 1) for _ in range(self.dimension)]
            norm = sum(x**2 for x in vec) ** 0.5
            embeddings.append([x/norm for x in vec])
        return embeddings
        
    def get_dimension(self) -> int:
        return self.dimension
