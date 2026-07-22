from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import datetime

class ReasoningTimelineEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    agent_name: str
    action: str
    duration_ms: float
    summary: str
    evidence_generated: int

class DecisionResponse(BaseModel):
    executive_summary: str
    root_cause: str
    supporting_evidence: List[str]
    recommended_action: str
    business_impact: str
    risk_level: str
    confidence: float
    citations: List[Dict[str, Any]]
    
class AgentState(BaseModel):
    # Inputs
    query: str
    
    # Coordinator Planning
    intent: str = ""
    target_agents: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    
    # Evidence gathered
    semantic_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    graph_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    graph_edges: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Maintenance Insights
    maintenance_insights: Dict[str, Any] = Field(default_factory=dict)
    
    # Global tracking
    errors: List[str] = Field(default_factory=list)
    timeline: List[ReasoningTimelineEvent] = Field(default_factory=list)
    
    # Final Output
    final_decision: Optional[DecisionResponse] = None
