import os
from typing import List
from google import genai
from app.services.embeddings.base import EmbeddingProvider

class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Google's Gemini models."""
    
    def __init__(self, model_name: str = "gemini-embedding-2", dimension: int = 3072):
        self.model_name = model_name
        self.dimension = dimension
        
        import os
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # The Gemini API expects either a single string or a list of strings
        # We process them in one batch. 
        if not texts:
            return []
            
        result = self.client.models.embed_content(
            model=self.model_name,
            contents=texts,
        )
        # result.embeddings is a list of objects with a 'values' attribute
        return [embedding.values for embedding in result.embeddings]
        
    def get_dimension(self) -> int:
        return self.dimension
