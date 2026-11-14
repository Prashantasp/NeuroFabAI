"""Semantic retrieval agent: pulls document evidence from the vector store."""

from __future__ import annotations

import logging
import time

from app.schemas.agents import AgentState, ReasoningTimelineEvent
from app.schemas.rag import QueryPlan
from app.services.embeddings import EmbeddingError
from app.services.retrieval.vector import VectorRetrieval
from app.services.vectorstore.base import VectorStoreError

logger = logging.getLogger(__name__)


def _dedupe_chunks(chunks: list[dict]) -> list[dict]:
    seen: set = set()
    unique = []
    for chunk in chunks:
        key = chunk.get("chunk_id") or (chunk.get("text") or "")[:120]
        if key and key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique


def search_agent(state: AgentState) -> AgentState:
    started = time.perf_counter()

    plan = QueryPlan(
        detected_intent=state.intent,
        confidence=1.0,
        selected_strategy="Vector",
        reasoning="Delegated by Coordinator",
        extracted_entities=state.entities,
        extracted_filters={},
    )

    try:
        evidence = VectorRetrieval().retrieve(state.query, plan, workspace_id=state.workspace_id)
    except (VectorStoreError, EmbeddingError) as exc:
        logger.warning("Semantic retrieval failed: %s", exc)
        state.errors.append(getattr(exc, "user_message", str(exc)))
        state.timeline.append(
            ReasoningTimelineEvent(
                agent_name="SearchAgent",
                action="Retrieve document evidence",
                duration_ms=(time.perf_counter() - started) * 1000,
                summary=f"Failed: {getattr(exc, 'user_message', str(exc))}",
                status="failed",
            )
        )
        return state

    state.semantic_chunks = _dedupe_chunks(state.semantic_chunks + evidence.retrieved_chunks)

    state.timeline.append(
        ReasoningTimelineEvent(
            agent_name="SearchAgent",
            action="Retrieve document evidence",
            duration_ms=(time.perf_counter() - started) * 1000,
            summary=(
                f"Retrieved {len(evidence.retrieved_chunks)} excerpt(s) from "
                f"{len(evidence.provenance_links)} document(s)."
                if evidence.retrieved_chunks
                else "No matching document excerpts in this workspace."
            ),
            evidence_generated=len(evidence.retrieved_chunks),
        )
    )
    return state


def search_router(state: AgentState) -> str:
    if "graph_agent" in state.target_agents:
        return "graph_agent"
    if "maintenance_agent" in state.target_agents:
        return "maintenance_agent"
    return "coordinator_synthesis"
