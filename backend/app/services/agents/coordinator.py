"""Coordinator agent: plans retrieval, then synthesises the final answer.

Synthesis is genuinely model-driven. When the model is unavailable the workflow
records an error and returns no decision -- it does not fabricate one. The UI
surfaces that as a retryable error state, which is honest; a templated
"executive summary" that looks like analysis is not.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

from app.schemas.agents import (
    Citation,
    DecisionResponse,
    LLMDecision,
    ReasoningTimelineEvent,
    AgentState,
)
from app.services.agents.prompts import synthesis_prompt, system_prompt, evidence_sources
from app.services.entity_resolver import entity_resolver
from app.services.graph_service import get_graph_backend
from app.services.llm import LLMError, coerce_str_list, get_llm_provider

logger = logging.getLogger(__name__)

TROUBLESHOOTING_KEYWORDS = (
    "why", "fix", "overheat", "failure", "fail", "broken", "vibration", "leak",
    "troubleshoot", "repair", "issue", "alarm", "trip", "temperature", "fault",
    "degrad", "root cause", "not working", "abnormal",
)
GRAPH_KEYWORDS = (
    "related", "component", "connected", "subgraph", "topology", "relationship",
    "depend", "where", "contains", "hierarchy", "part of", "linked", "upstream",
    "downstream",
)


def coordinator_planning(state: AgentState) -> AgentState:
    """Resolve query entities against the graph and choose which agents to run."""
    started = time.perf_counter()

    query_lower = state.query.lower()
    topology = get_graph_backend().get_topology(workspace_id=state.workspace_id)
    state.entities = entity_resolver.extract_and_resolve(state.query, topology)

    is_troubleshooting = any(kw in query_lower for kw in TROUBLESHOOTING_KEYWORDS)
    is_graph_heavy = any(kw in query_lower for kw in GRAPH_KEYWORDS)

    if is_troubleshooting:
        state.intent = "troubleshooting"
        state.target_agents = ["search_agent", "graph_agent", "maintenance_agent"]
    elif is_graph_heavy or state.entities:
        state.intent = "relationship reasoning"
        state.target_agents = ["graph_agent", "search_agent", "maintenance_agent"]
    else:
        state.intent = "semantic lookup"
        state.target_agents = ["search_agent", "graph_agent"]

    entity_desc = ", ".join(state.entities) if state.entities else "none matched in graph"
    state.timeline.append(
        ReasoningTimelineEvent(
            agent_name="Coordinator",
            action="Plan retrieval",
            duration_ms=(time.perf_counter() - started) * 1000,
            summary=(
                f"Intent '{state.intent}'. Entities: {entity_desc}. "
                f"Delegating to {', '.join(state.target_agents)}."
            ),
            evidence_generated=len(state.entities),
        )
    )
    return state


def _checked_citations(raw, state):
    sources = evidence_sources(state.semantic_chunks, state.graph_edges)
    claims = {value.strip() for value in [raw.executive_summary, raw.root_cause,
        raw.recommended_action, raw.business_impact, *raw.supporting_evidence] if value.strip()}
    if raw.risk_level:
        claims.add(raw.risk_level)
    citations = []
    seen_references = set()
    supported = set()
    for reference in raw.references:
        source = sources.get(reference.source_id)
        quote = " ".join(reference.quote.split())
        claim = reference.claim.strip()
        if not source or claim not in claims or len(quote) < 12 or quote not in source["text"]:
            return []
        if claim == raw.risk_level and not re.search(r"\b" + re.escape(raw.risk_level) + r"\b", quote, re.IGNORECASE):
            return []
        supported.add(claim)
        key = (reference.source_id, claim, quote)
        if key in seen_references:
            continue
        seen_references.add(key)
        citations.append(Citation(source_id=reference.source_id, claim=claim, snippet=quote,
            **{key: value for key, value in source.items() if key != "text"}))
    return citations if claims and supported == claims else []


def coordinator_synthesis(state: AgentState) -> AgentState:
    """Turn retrieved evidence into a structured decision using the LLM."""
    started = time.perf_counter()
    provider = get_llm_provider()

    if not provider.available:
        state.errors.append(
            "AI synthesis is unavailable: no language model is configured on this server."
        )
        state.timeline.append(
            ReasoningTimelineEvent(
                agent_name="Coordinator",
                action="Synthesise answer",
                duration_ms=(time.perf_counter() - started) * 1000,
                summary="Skipped: no language model configured (set GOOGLE_API_KEY).",
                status="skipped",
            )
        )
        return state

    prompt = synthesis_prompt(
        query=state.query,
        chunks=state.semantic_chunks,
        nodes=state.graph_nodes,
        edges=state.graph_edges,
        signals=state.signals,
        history=state.history,
    )

    try:
        raw = provider.generate_structured(
            prompt,
            LLMDecision,
            system=system_prompt(state.mode),
        )
    except LLMError as exc:
        logger.warning("LLM synthesis failed: %s", exc)
        state.errors.append(exc.user_message)
        state.timeline.append(
            ReasoningTimelineEvent(
                agent_name="Coordinator",
                action="Synthesise answer",
                duration_ms=(time.perf_counter() - started) * 1000,
                summary=f"Failed: {exc.user_message}",
                status="failed",
            )
        )
        return state

    citations = _checked_citations(raw, state)
    if citations:
        decision = DecisionResponse(
            executive_summary=raw.executive_summary.strip(),
            root_cause=raw.root_cause.strip(),
            supporting_evidence=coerce_str_list(raw.supporting_evidence),
            recommended_action=raw.recommended_action.strip(),
            business_impact=raw.business_impact.strip(),
            risk_level=raw.risk_level,
            confidence=None,
            citations=citations,
            grounded=False,
            evidence_status="references_checked",
        )
    else:
        decision = DecisionResponse(
            executive_summary="The available sources do not establish a supported answer to this question.",
            root_cause="Not established by the cited sources.",
            supporting_evidence=[], recommended_action="Review the original documents or add relevant evidence.",
            business_impact="Not established by the cited sources.",
            confidence=None, grounded=False, evidence_status="insufficient",
        )
    state.final_decision = decision

    state.timeline.append(
        ReasoningTimelineEvent(
            agent_name="Coordinator",
            action="Synthesise answer",
            duration_ms=(time.perf_counter() - started) * 1000,
            summary=(
                f"Produced an AI draft with {len(decision.citations)} checked source references; "
                "claim accuracy requires review."
            ),
            evidence_generated=len(decision.supporting_evidence),
        )
    )
    return state


def coordinator_router(state: AgentState) -> str:
    for agent in ("search_agent", "graph_agent", "maintenance_agent"):
        if agent in state.target_agents:
            return agent
    return "coordinator_synthesis"
