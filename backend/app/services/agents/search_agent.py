import time
from app.schemas.agents import AgentState, ReasoningTimelineEvent
from app.services.retrieval.vector import VectorRetrieval
from app.schemas.rag import QueryPlan

def search_agent(state: AgentState) -> AgentState:
    """Retrieves semantic chunks from the vector store."""
    start_time = time.time()
    
    # We map AgentState to the QueryPlan expected by the underlying retrieval engine
    mock_plan = QueryPlan(
        detected_intent=state.intent,
        confidence=1.0,
        selected_strategy="Vector",
        reasoning="Delegated by Coordinator",
        extracted_entities=state.entities,
        extracted_filters={}
    )
    
    retriever = VectorRetrieval()
    evidence = retriever.retrieve(state.query, mock_plan)
    
    state.semantic_chunks.extend(evidence.retrieved_chunks)
    
    # Deduplicate just in case
    unique_chunks = []
    seen = set()
    for chunk in state.semantic_chunks:
        cid = chunk.get("chunk_id")
        if cid not in seen:
            seen.add(cid)
            unique_chunks.append(chunk)
    state.semantic_chunks = unique_chunks
    
    state.timeline.append(ReasoningTimelineEvent(
        agent_name="SearchAgent",
        action="Retrieve Semantic Evidence",
        duration_ms=(time.time() - start_time) * 1000,
        summary=f"Retrieved {len(evidence.retrieved_chunks)} semantic chunks from Vector Store.",
        evidence_generated=len(evidence.retrieved_chunks)
    ))
    return state

def search_router(state: AgentState) -> str:
    # After search, check if we need to run graph or maintenance, else synthesize
    if "graph_agent" in state.target_agents:
        return "graph_agent"
    if "maintenance_agent" in state.target_agents:
        return "maintenance_agent"
    return "coordinator_synthesis"
