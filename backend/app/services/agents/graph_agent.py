"""Knowledge graph agent: expands entities into a relationship subgraph."""

from __future__ import annotations

import logging
import time

from app.schemas.agents import AgentState, ReasoningTimelineEvent
from app.schemas.rag import QueryPlan
from app.services.retrieval.graph import GraphRetrieval

logger = logging.getLogger(__name__)


def graph_agent(state: AgentState) -> AgentState:
    started = time.perf_counter()

    plan = QueryPlan(
        detected_intent=state.intent,
        confidence=1.0,
        selected_strategy="Graph",
        reasoning="Delegated by Coordinator",
        extracted_entities=state.entities,
        extracted_filters={},
    )

    try:
        evidence = GraphRetrieval().retrieve(
            state.query,
            plan,
            workspace_id=state.workspace_id,
            semantic_chunks=state.semantic_chunks,
        )
    except Exception as exc:  # noqa: BLE001 - graph store may be unreachable
        logger.warning("Graph retrieval failed: %s", exc)
        state.errors.append("The knowledge graph could not be queried for this request.")
        state.timeline.append(
            ReasoningTimelineEvent(
                agent_name="GraphAgent",
                action="Traverse knowledge graph",
                duration_ms=(time.perf_counter() - started) * 1000,
                summary="Failed: the knowledge graph is unavailable.",
                status="failed",
            )
        )
        return state

    state.graph_nodes = list(
        {
            (n.get("canonical_name") or n.get("id")): n
            for n in state.graph_nodes + evidence.retrieved_nodes
            if n
        }.values()
    )
    state.graph_edges = list(
        {
            (e.get("source"), e.get("target"), e.get("type")): e
            for e in state.graph_edges + evidence.retrieved_relationships
            if e
        }.values()
    )

    state.timeline.append(
        ReasoningTimelineEvent(
            agent_name="GraphAgent",
            action="Traverse knowledge graph",
            duration_ms=(time.perf_counter() - started) * 1000,
            summary=(
                f"Traversed {len(evidence.retrieved_nodes)} entities and "
                f"{len(evidence.retrieved_relationships)} relationships."
                if evidence.retrieved_nodes
                else "No matching entities in this workspace's knowledge graph."
            ),
            evidence_generated=len(evidence.retrieved_nodes)
            + len(evidence.retrieved_relationships),
        )
    )
    return state


def graph_router(state: AgentState) -> str:
    if "maintenance_agent" in state.target_agents:
        return "maintenance_agent"
    return "coordinator_synthesis"
