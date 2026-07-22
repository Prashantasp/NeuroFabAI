from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class QueryPlan(BaseModel):
    detected_intent: str = Field(..., description="e.g. semantic lookup, relationship reasoning, troubleshooting, etc.")
    confidence: float = Field(..., description="Planner confidence in this interpretation")
    selected_strategy: str = Field(..., description="Vector, Graph, Hybrid, Metadata")
    reasoning: str = Field(..., description="Why this strategy was chosen")
    extracted_entities: List[str] = Field(default_factory=list, description="Entities extracted from the user query")
    extracted_filters: Dict[str, Any] = Field(default_factory=dict, description="Metadata filters like document_type")

class EvidencePackage(BaseModel):
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list, description="Raw chunks from vector DB")
    retrieved_nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Graph nodes")
    retrieved_relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Graph edges")
    provenance_links: List[str] = Field(default_factory=list, description="List of source document IDs")
    overall_confidence: float = Field(0.0, description="Calculated confidence of the fused evidence")

class ExplainableAnswer(BaseModel):
    answer: str = Field(..., description="The main answer text")
    executive_summary: str = Field(..., description="Short summary for quick reading")
    reasoning: str = Field(..., description="How the AI arrived at this conclusion")
    supporting_documents: List[str] = Field(default_factory=list, description="Source filenames/titles")
    supporting_graph_relationships: List[str] = Field(default_factory=list, description="Key evidence snippets from relationships")
    confidence: float = Field(..., description="Final numeric confidence")
    confidence_label: str = Field(..., description="High, Medium, Low")
    recommended_action: str = Field(..., description="Actionable next step for the user")
    risk_level: str = Field(..., description="High, Medium, Low, None")
    assumptions: List[str] = Field(default_factory=list, description="Any assumptions made during reasoning")
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed citations (document, page, snippet)")
