import os
import asyncio
from google import genai
from app.services.knowledge_extractor import knowledge_extractor
from app.services.embeddings.gemini import GeminiEmbeddingProvider

async def run_test():
    print(f"GEMINI_API_KEY available: {'GEMINI_API_KEY' in os.environ}")
    
    # Test 1: Gemini Embeddings
    print("\n--- Test 1: Gemini Embeddings ---")
    embedder = GeminiEmbeddingProvider()
    try:
        embeddings = embedder.embed_texts(["This is a test of the Gemini embedding model."])
        print(f"Success! Generated embedding of dimension: {len(embeddings[0])}")
        print(f"First 5 values: {embeddings[0][:5]}")
    except Exception as e:
        print(f"Embedding failed: {e}")
        
    # Test 2: Gemini Knowledge Extraction
    print("\n--- Test 2: Knowledge Extraction ---")
    chunks = [
        "The heat exchanger H-202 has been showing signs of fouling since last month.",
        "Maintenance replaced the thermal pads, but the outlet temperature remains high.",
        "A common issue is scaling buildup inside the tubes."
    ]
    try:
        extraction = knowledge_extractor.extract_from_chunks("test-doc-123", chunks)
        print(f"Extracted {len(extraction.entities)} entities and {len(extraction.relationships)} relationships.")
        for e in extraction.entities:
            print(f"Entity: {e.name} ({e.type}) - {e.properties}")
        for r in extraction.relationships:
            print(f"Relationship: {r.source_entity_id} -> {r.target_entity_id} ({r.type})")
    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
