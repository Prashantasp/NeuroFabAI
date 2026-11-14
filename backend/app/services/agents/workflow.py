"""Minimal state-graph orchestrator for the agent pipeline.

A deliberately small, dependency-free state machine: nodes mutate an `AgentState`
and a router picks the next node. It is easier to reason about (and to test) than
pulling in a framework for five nodes and four edges.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional

from app.schemas.agents import AgentState, ReasoningTimelineEvent

logger = logging.getLogger(__name__)

END = "__END__"
MAX_STEPS = 12  # backstop against a router cycle

NodeFn = Callable[[AgentState], AgentState]
RouterFn = Callable[[AgentState], str]


class StateGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, NodeFn] = {}
        self.routers: Dict[str, RouterFn] = {}
        self.entry_point: Optional[str] = None

    def add_node(self, name: str, action: NodeFn) -> None:
        self.nodes[name] = action

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def add_conditional_edges(self, source: str, router: RouterFn) -> None:
        self.routers[source] = router

    def add_edge(self, source: str, target: str) -> None:
        self.routers[source] = lambda _state, _t=target: _t

    def run(self, initial_state: AgentState) -> AgentState:
        if not self.entry_point:
            raise ValueError("StateGraph entry point is not set")

        state = initial_state
        current = self.entry_point
        steps = 0

        while current != END:
            if steps >= MAX_STEPS:
                logger.error("Agent workflow exceeded %d steps; aborting.", MAX_STEPS)
                state.errors.append("The reasoning workflow did not converge.")
                break
            steps += 1

            node = self.nodes.get(current)
            if node is None:
                raise ValueError(f"Agent node '{current}' is not registered")

            started = time.perf_counter()
            try:
                state = node(state)
            except Exception as exc:  # noqa: BLE001 - one agent must not kill the run
                logger.exception("Agent node '%s' raised", current)
                state.errors.append(f"The {current} step failed unexpectedly.")
                state.timeline.append(
                    ReasoningTimelineEvent(
                        agent_name=current,
                        action="Execute",
                        duration_ms=(time.perf_counter() - started) * 1000,
                        summary=f"Unexpected failure: {type(exc).__name__}",
                        status="failed",
                    )
                )

            router = self.routers.get(current)
            current = router(state) if router else END

        return state


def build_workflow() -> StateGraph:
    from app.services.agents.coordinator import (
        coordinator_planning,
        coordinator_router,
        coordinator_synthesis,
    )
    from app.services.agents.graph_agent import graph_agent, graph_router
    from app.services.agents.maintenance_agent import maintenance_agent, maintenance_router
    from app.services.agents.search_agent import search_agent, search_router

    graph = StateGraph()
    graph.set_entry_point("coordinator_planning")

    graph.add_node("coordinator_planning", coordinator_planning)
    graph.add_node("search_agent", search_agent)
    graph.add_node("graph_agent", graph_agent)
    graph.add_node("maintenance_agent", maintenance_agent)
    graph.add_node("coordinator_synthesis", coordinator_synthesis)

    graph.add_conditional_edges("coordinator_planning", coordinator_router)
    graph.add_conditional_edges("search_agent", search_router)
    graph.add_conditional_edges("graph_agent", graph_router)
    graph.add_conditional_edges("maintenance_agent", maintenance_router)
    graph.add_edge("coordinator_synthesis", END)

    return graph


_workflow: Optional[StateGraph] = None


def get_agent_workflow() -> StateGraph:
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow
