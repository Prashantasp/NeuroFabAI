from typing import Any, Dict, List

from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    detected_intent: str = Field(
        ..., description="semantic lookup | relationship reasoning | troubleshooting"
    )
    confidence: float = Field(..., description="Planner confidence in this interpretation")
    selected_strategy: str = Field(..., description="Vector | Graph | Hybrid")
    reasoning: str = Field(..., description="Why this strategy was chosen")
    extracted_entities: List[str] = Field(default_factory=list)
    extracted_filters: Dict[str, Any] = Field(default_factory=dict)


class EvidencePackage(BaseModel):
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    provenance_links: List[str] = Field(
        default_factory=list, description="Source document IDs backing this evidence"
    )
    overall_confidence: float = Field(
        0.0, description="Best retrieval score, used as an upper bound on answer confidence"
    )
