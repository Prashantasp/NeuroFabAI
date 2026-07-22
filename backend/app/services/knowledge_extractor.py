import json
import uuid
import logging
from typing import List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.schemas.knowledge import KnowledgeGraphExtraction, Entity, Relationship, ConfidenceBand
from app.services.entity_resolver import entity_resolver

logger = logging.getLogger(__name__)

def get_confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.90:
        return ConfidenceBand.HIGH
    elif score >= 0.75:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW

# We define Pydantic schemas that match the expected output format for Gemini
class GeminiEntity(BaseModel):
    name: str = Field(description="The name of the entity.")
    type: str = Field(description="The type of the entity (e.g., Equipment, Component, FailureMode, Document).")
    properties_json: str = Field(description="A JSON string representing key-value pairs of properties for this entity.")
    evidence_snippet: str = Field(description="A short snippet from the text supporting this extraction.")
    confidence: float = Field(description="A confidence score between 0.0 and 1.0.")

class GeminiRelationship(BaseModel):
    source_entity_name: str = Field(description="The name of the source entity (must match one of the extracted entities).")
    target_entity_name: str = Field(description="The name of the target entity (must match one of the extracted entities).")
    type: str = Field(description="The relationship type (e.g., USES_COMPONENT, HAS_FAILURE_MODE).")
    evidence: str = Field(description="A short snippet from the text supporting this relationship.")
    confidence: float = Field(description="A confidence score between 0.0 and 1.0.")

class GeminiExtraction(BaseModel):
    entities: List[GeminiEntity]
    relationships: List[GeminiRelationship]

class KnowledgeExtractor:
    """
    A service that extracts structured knowledge (entities and relationships)
    from unstructured text chunks using Google Gemini.
    """
    
    def __init__(self, model_name: str = "gemini-flash-latest"):
        self.model_name = model_name
        import os
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    
    def extract_from_chunks(self, document_id: str, chunks: List[str]) -> KnowledgeGraphExtraction:
        logger.info(f"Extracting knowledge from {len(chunks)} chunks for document {document_id}")
        
        now = datetime.now(timezone.utc)
        
        # We can extract from all chunks by concatenating or processing sequentially.
        # For MVP, we combine up to a safe limit.
        full_text = "\n\n".join(chunks[:10]) # Limit to 10 chunks for speed/context in demo
        
        prompt = f"""
        Analyze the following text from an industrial/technical document.
        Extract the key entities (Equipment, Component, FailureMode, Document, Process, Material) 
        and the relationships between them.
        
        TEXT:
        {full_text}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GeminiExtraction,
                    temperature=0.1,
                )
            )
            
            structured_data = response.parsed
            
            # Map Gemini objects back to our application domain models
            app_entities = []
            entity_name_to_id = {}
            
            for gen_e in structured_data.entities:
                e_id = str(uuid.uuid4())
                entity_name_to_id[gen_e.name] = e_id
                
                props = {}
                try:
                    props = json.loads(gen_e.properties_json) if gen_e.properties_json else {}
                except:
                    props = {"raw": gen_e.properties_json}
                
                app_entities.append(Entity(
                    id=e_id,
                    type=gen_e.type,
                    name=gen_e.name,
                    canonical_name=entity_resolver.resolve(gen_e.name),
                    properties=props,
                    source_document_id=document_id,
                    page_number=1, # Defaulting for MVP
                    evidence_snippet=gen_e.evidence_snippet,
                    extraction_timestamp=now,
                    confidence=gen_e.confidence,
                    confidence_label=get_confidence_band(gen_e.confidence),
                    version=1
                ))
                
            app_relationships = []
            for gen_r in structured_data.relationships:
                # Resolve source and target IDs
                s_id = entity_name_to_id.get(gen_r.source_entity_name)
                t_id = entity_name_to_id.get(gen_r.target_entity_name)
                
                if s_id and t_id:
                    app_relationships.append(Relationship(
                        source_entity_id=s_id,
                        target_entity_id=t_id,
                        type=gen_r.type.upper(),
                        source_document_id=document_id,
                        page_number=1,
                        evidence=gen_r.evidence,
                        extraction_timestamp=now,
                        confidence=gen_r.confidence,
                        confidence_label=get_confidence_band(gen_r.confidence),
                        version=1
                    ))
            
            extraction = KnowledgeGraphExtraction(entities=app_entities, relationships=app_relationships, version=1)
            logger.info(f"Extracted {len(app_entities)} entities and {len(app_relationships)} relationships.")
            return extraction
            
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            # Fallback for demo stability
            return KnowledgeGraphExtraction(entities=[], relationships=[], version=1)

knowledge_extractor = KnowledgeExtractor()
