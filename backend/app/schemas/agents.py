from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

RiskLevel = Literal["Low", "Medium", "High", "Critical"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReasoningTimelineEvent(BaseModel):
    timestamp: str = Field(default_factory=_utc_now_iso)
    agent_name: str
    action: str
    duration_ms: float
    summary: str
    evidence_generated: int = 0
    status: Literal["ok", "failed", "skipped"] = "ok"


class Citation(BaseModel):
    source_id: Optional[str] = None
    claim: Optional[str] = None
    document_id: Optional[str] = None
    document_title: Optional[str] = None
    kind: Literal["semantic", "graph"] = "semantic"
    snippet: Optional[str] = None
    relation: Optional[str] = None
    page_number: Optional[int] = None


class ClaimReference(BaseModel):
    claim: str = Field(description="Exact answer field or supporting-evidence bullet being supported.")
    source_id: str = Field(description="Supplied source ID, such as C1 or R1.")
    quote: str = Field(description="Verbatim quote from that source supporting the claim.")


class LLMDecision(BaseModel):
    """Schema the model is constrained to when synthesising an answer.

    Kept separate from `DecisionResponse` so the API contract can evolve without
    changing what the model is asked to produce.
    """

    executive_summary: str = Field(
        description="A direct, specific answer to the user's question, grounded only in the supplied evidence."
    )
    root_cause: str = Field(
        default="",
        description="A cause explicitly supported by a cited passage, only for a causal question. Otherwise return an empty string; do not add 'not applicable' filler."
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Short factual bullets, each traceable to a supplied document chunk or graph relationship.",
    )
    recommended_action: str = Field(
        default="",
        description="An action explicitly stated in a cited passage and relevant to the question. Otherwise return an empty string, not an invented recommendation or 'no action needed'."
    )
    business_impact: str = Field(
        default="",
        description="An operational consequence explicitly stated in a cited passage and relevant to the question. Otherwise return an empty string, not 'none identified'."
    )
    risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Only report a risk level explicitly classified in a supplied source, with a reference whose claim exactly matches the level. Otherwise null; a factual lookup is not a risk assessment."
    )
    confidence: float = Field(
        description="0.0-1.0 confidence that the evidence supports this answer."
    )
    references: List[ClaimReference] = Field(default_factory=list)


class DecisionResponse(BaseModel):
    executive_summary: str
    root_cause: str
    supporting_evidence: List[str] = Field(default_factory=list)
    recommended_action: str
    business_impact: str
    risk_level: Optional[RiskLevel] = None
    confidence: Optional[float] = None
    citations: List[Citation] = Field(default_factory=list)
    grounded: bool = Field(
        default=False,
        description="Reserved for independently verified answers; AI drafts are always false.",
    )
    evidence_status: Literal["references_checked", "insufficient"] = "insufficient"

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: Optional[float]) -> Optional[float]:
        return None if v is None else max(0.0, min(1.0, float(v)))

    @field_validator("risk_level", mode="before")
    @classmethod
    def _normalise_risk(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        allowed = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
        return allowed.get(str(v).strip().lower(), "Medium")


class ReliabilitySignals(BaseModel):
    """Deterministic facts computed from the knowledge graph.

    These are measurements, not prose. The language model turns them into an
    answer; nothing here invents narrative text.
    """

    failure_modes: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    processes: List[str] = Field(default_factory=list)
    condition_indicators: List[str] = Field(default_factory=list)
    causal_chains: List[str] = Field(default_factory=list)
    severity_hint: RiskLevel = "Low"

    @property
    def is_empty(self) -> bool:
        return not (self.failure_modes or self.equipment or self.components)


CopilotMode = Literal["general", "maintenance", "compliance"]


class AgentState(BaseModel):
    # Inputs
    query: str
    workspace_id: str
    mode: CopilotMode = "general"
    history: List[Dict[str, str]] = Field(default_factory=list)

    # Planning
    intent: str = ""
    target_agents: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)

    # Retrieved evidence
    semantic_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    graph_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    graph_edges: List[Dict[str, Any]] = Field(default_factory=list)

    signals: ReliabilitySignals = Field(default_factory=ReliabilitySignals)

    # Tracking
    errors: List[str] = Field(default_factory=list)
    timeline: List[ReasoningTimelineEvent] = Field(default_factory=list)

    final_decision: Optional[DecisionResponse] = None

    @property
    def has_evidence(self) -> bool:
        return bool(self.semantic_chunks or self.graph_edges or self.graph_nodes)
