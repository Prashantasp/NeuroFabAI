import time
from app.schemas.agents import AgentState, ReasoningTimelineEvent

def maintenance_agent(state: AgentState) -> AgentState:
    """Analyzes the accumulated evidence to produce maintenance insights."""
    start_time = time.time()
    
    # Mock analysis based on query and evidence
    query_lower = state.query.lower()
    
    # Default Insights
    insights = {
        "root_cause": "Unknown",
        "recommended_action": "Monitor system closely.",
        "business_impact": "Negligible",
        "risk_level": "Low"
    }
    

    
    # If the semantic chunks or graph edges mention overheating/lubrication, act on it
    if "overheating" in query_lower:
        insights = {
            "root_cause": "Skipped lubrication on Outboard Bearing.",
            "recommended_action": "Dispatch maintenance technician to inspect and lubricate immediately.",
            "business_impact": "$15,000/hr downtime if total failure occurs.",
            "risk_level": "High"
        }
    elif "failure" in query_lower:
        insights = {
            "root_cause": "Wear and tear on internal components.",
            "recommended_action": "Schedule preventative maintenance within 7 days.",
            "business_impact": "Moderate efficiency drop.",
            "risk_level": "Medium"
        }
        
    state.maintenance_insights = insights
    
    state.timeline.append(ReasoningTimelineEvent(
        agent_name="MaintenanceAgent",
        action="Maintenance & Risk Analysis",
        duration_ms=(time.time() - start_time) * 1000,
        summary=f"Calculated Risk Level: {insights['risk_level']}. Recommended: {insights['recommended_action']}",
        evidence_generated=1
    ))
    return state

def maintenance_router(state: AgentState) -> str:
    # Always goes to synthesis next
    return "coordinator_synthesis"
