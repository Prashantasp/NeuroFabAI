import time
from app.schemas.agents import AgentState, ReasoningTimelineEvent
from app.services.retrieval.graph import GraphRetrieval
from app.schemas.rag import QueryPlan

def graph_agent(state: AgentState) -> AgentState:
    """Retrieves relationship edges from the knowledge graph."""
    start_time = time.time()
    
    mock_plan = QueryPlan(
        detected_intent=state.intent,
        confidence=1.0,
        selected_strategy="Graph",
        reasoning="Delegated by Coordinator",
        extracted_entities=state.entities,
        extracted_filters={}
    )
    
    retriever = GraphRetrieval()
    evidence = retriever.retrieve(state.query, mock_plan, semantic_chunks=state.semantic_chunks)
    
    state.graph_nodes.extend(evidence.retrieved_nodes)
    state.graph_edges.extend(evidence.retrieved_relationships)
    
    # Deduplicate nodes
    unique_nodes = []
    seen = set()
    for n in state.graph_nodes:
        nid = n.get("id")
        if nid not in seen:
            seen.add(nid)
            unique_nodes.append(n)
    state.graph_nodes = unique_nodes
    
    # Deduplicate edges
    unique_edges = []
    seen_e = set()
    for e in state.graph_edges:
        eid = f"{e.get('source')}->{e.get('target')} ({e.get('type')})"
        if eid not in seen_e:
            seen_e.add(eid)
            unique_edges.append(e)
    state.graph_edges = unique_edges
    
    state.timeline.append(ReasoningTimelineEvent(
        agent_name="GraphAgent",
        action="Retrieve Graph Evidence",
        duration_ms=(time.time() - start_time) * 1000,
        summary=f"Retrieved {len(evidence.retrieved_relationships)} relationships from Knowledge Graph.",
        evidence_generated=len(evidence.retrieved_relationships)
    ))
    return state

def graph_router(state: AgentState) -> str:
    if "maintenance_agent" in state.target_agents:
        return "maintenance_agent"
    return "coordinator_synthesis"
