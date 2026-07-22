import enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

class ConfidenceBand(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class Entity(BaseModel):
    id: str = Field(..., description="Unique UUID for the entity")
    type: str = Field(..., description="E.g. Equipment, Component, Document, SOP, Incident, FailureMode, etc.")
    name: str = Field(..., description="Raw extracted name")
    canonical_name: str = Field(..., description="Normalized unique real-world name")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata properties")
    
    # Provenance & Explainability
    source_document_id: str = Field(..., description="The document this was extracted from")
    page_number: Optional[int] = Field(None, description="Page number of the extraction")
    evidence_snippet: Optional[str] = Field(None, description="Exact text proving this entity exists")
    extraction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    confidence: float = Field(..., description="Numeric confidence score")
    confidence_label: ConfidenceBand = Field(..., description="Categorical confidence band")
    
    version: int = Field(1, description="Extraction model version")

class Relationship(BaseModel):
    source_entity_id: str = Field(..., description="UUID of the source entity")
    target_entity_id: str = Field(..., description="UUID of the target entity")
    type: str = Field(..., description="E.g. USES, HAS_FAILURE_MODE, REFERENCES, INVOLVES, etc.")
    
    # Provenance & Explainability
    source_document_id: str = Field(..., description="The document this was extracted from")
    page_number: Optional[int] = Field(None, description="Page number of the extraction")
    evidence: str = Field(..., description="Text chunk or snippet acting as evidence for this relationship")
    extraction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    confidence: float = Field(..., description="Numeric confidence score")
    confidence_label: ConfidenceBand = Field(..., description="Categorical confidence band")
    
    version: int = Field(1, description="Extraction model version")

class KnowledgeGraphExtraction(BaseModel):
    entities: List[Entity] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    version: int = Field(1, description="Extraction version for the entire document payload")
