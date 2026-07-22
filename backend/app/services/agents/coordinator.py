import time
from app.schemas.agents import AgentState, ReasoningTimelineEvent, DecisionResponse

def coordinator_planning(state: AgentState) -> AgentState:
    """Analyzes query and sets the initial execution plan."""
    start_time = time.time()
    
    query = state.query.lower()
    
    # Simple Mock NLP Planning
    state.entities = []
    if "p-101" in query or "pump" in query:
        state.entities.append("Pump P-101")
    if "bearing" in query:
        state.entities.append("Outboard Bearing")
        
    is_troubleshooting = any(kw in query for kw in ["why", "fix", "overheating", "failure", "broken"])
    is_graph_heavy = any(kw in query for kw in ["related", "components", "connected"])
    
    if is_troubleshooting:
        state.intent = "troubleshooting"
        state.target_agents = ["search_agent", "graph_agent", "maintenance_agent"]
    elif is_graph_heavy:
        state.intent = "relationship reasoning"
        state.target_agents = ["graph_agent"]
    else:
        state.intent = "semantic lookup"
        state.target_agents = ["search_agent"]
        
    state.timeline.append(ReasoningTimelineEvent(
        agent_name="CoordinatorAgent",
        action="Plan Workflow",
        duration_ms=(time.time() - start_time) * 1000,
        summary=f"Detected intent '{state.intent}'. Delegating to: {', '.join(state.target_agents)}.",
        evidence_generated=0
    ))
    return state

def coordinator_synthesis(state: AgentState) -> AgentState:
    """Assembles the final decision response based on gathered evidence."""
    start_time = time.time()
    
    chunks_count = len(state.semantic_chunks)
    nodes_count = len(state.graph_nodes)
    edges_count = len(state.graph_edges)
    
    # 1. Synthesize Executive Summary
    summary = f"Analyzed {chunks_count} semantic chunks and {edges_count} graph relationships."
    
    # 2. Extract Citations & Supporting Evidence
    citations = []
    supporting_evidence = []
    for chunk in state.semantic_chunks:
        doc_id = chunk.get("document_id", "Unknown")
        citations.append({"document_id": doc_id, "type": "semantic"})
        
    for edge in state.graph_edges:
        if "evidence" in edge:
            supporting_evidence.append(edge["evidence"])
            
    # 3. Incorporate Maintenance Insights if available
    m_insights = state.maintenance_insights
    root_cause = m_insights.get("root_cause", "No specific root cause identified in retrieved context.")
    rec_action = m_insights.get("recommended_action", "No action required. System operating normally.")
    impact = m_insights.get("business_impact", "Negligible")
    risk = m_insights.get("risk_level", "Low")
    
    # 4. Confidence calculation
    confidence = 0.5
    if chunks_count > 0: confidence += 0.2
    if edges_count > 0: confidence += 0.2
    if m_insights: confidence += 0.09
    
    state.final_decision = DecisionResponse(
        executive_summary=summary,
        root_cause=root_cause,
        supporting_evidence=supporting_evidence,
        recommended_action=rec_action,
        business_impact=impact,
        risk_level=risk,
        confidence=min(1.0, confidence),
        citations=citations
    )
    
    state.timeline.append(ReasoningTimelineEvent(
        agent_name="CoordinatorAgent",
        action="Synthesize Decision",
        duration_ms=(time.time() - start_time) * 1000,
        summary="Successfully assembled structured DecisionResponse.",
        evidence_generated=1
    ))
    return state

# Routing logic
def coordinator_router(state: AgentState) -> str:
    # After planning, route to the first target agent
    if "search_agent" in state.target_agents:
        return "search_agent"
    if "graph_agent" in state.target_agents:
        return "graph_agent"
    if "maintenance_agent" in state.target_agents:
        return "maintenance_agent"
    return "coordinator_synthesis"
