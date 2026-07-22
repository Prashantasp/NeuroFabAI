import time
from typing import Callable, Dict, Any, List
from app.schemas.agents import AgentState, ReasoningTimelineEvent

class StateGraph:
    """
    Lightweight, pure-Python state-based multi-agent orchestrator.
    Mimics LangGraph's architecture without the external dependencies.
    """
    def __init__(self):
        self.nodes: Dict[str, Callable[[AgentState], AgentState]] = {}
        self.edges: Dict[str, Callable[[AgentState], str]] = {}
        self.entry_point: str = None
        
    def add_node(self, name: str, action: Callable[[AgentState], AgentState]):
        self.nodes[name] = action
        
    def set_entry_point(self, name: str):
        self.entry_point = name
        
    def add_conditional_edges(self, source: str, router: Callable[[AgentState], str]):
        self.edges[source] = router
        
    def add_edge(self, source: str, target: str):
        self.edges[source] = lambda state: target
        
    def run(self, initial_state: AgentState) -> AgentState:
        if not self.entry_point:
            raise ValueError("Entry point not set")
            
        current_node = self.entry_point
        state = initial_state
        
        while current_node != "__END__":
            if current_node not in self.nodes:
                raise ValueError(f"Node {current_node} not found")
                
            start_time = time.time()
            try:
                # Agent is completely stateless. It receives the state and returns the mutated state.
                state = self.nodes[current_node](state)
            except Exception as e:
                # Failure handling: log error and continue if possible
                state.errors.append(f"{current_node} failed: {str(e)}")
                state.timeline.append(ReasoningTimelineEvent(
                    agent_name=current_node,
                    action="Execution Failed",
                    duration_ms=(time.time() - start_time) * 1000,
                    summary=f"Failed with error: {str(e)}",
                    evidence_generated=0
                ))
                
            # Routing logic
            if current_node in self.edges:
                current_node = self.edges[current_node](state)
            else:
                current_node = "__END__"
                
        return state

# Wire up the workflow
from app.services.agents.coordinator import coordinator_planning, coordinator_synthesis, coordinator_router
from app.services.agents.search_agent import search_agent, search_router
from app.services.agents.graph_agent import graph_agent, graph_router
from app.services.agents.maintenance_agent import maintenance_agent, maintenance_router

agent_workflow = StateGraph()
agent_workflow.set_entry_point("coordinator_planning")

agent_workflow.add_node("coordinator_planning", coordinator_planning)
agent_workflow.add_node("search_agent", search_agent)
agent_workflow.add_node("graph_agent", graph_agent)
agent_workflow.add_node("maintenance_agent", maintenance_agent)
agent_workflow.add_node("coordinator_synthesis", coordinator_synthesis)

agent_workflow.add_conditional_edges("coordinator_planning", coordinator_router)
agent_workflow.add_conditional_edges("search_agent", search_router)
agent_workflow.add_conditional_edges("graph_agent", graph_router)
agent_workflow.add_conditional_edges("maintenance_agent", maintenance_router)
agent_workflow.add_edge("coordinator_synthesis", "__END__")

