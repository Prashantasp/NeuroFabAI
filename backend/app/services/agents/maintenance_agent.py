"""Reliability analysis over the retrieved subgraph.

This agent produces *measurements*, not narrative. It classifies retrieved nodes,
walks causal edges, and detects condition indicators in retrieved text. The
language model in the Coordinator turns those facts into an answer.

The previous implementation wrote sentences like "Risk of unplanned downtime and
degraded plant throughput" from an `if/elif` chain and presented them as AI
analysis. Nothing here writes prose about the plant.
"""

from __future__ import annotations

import time
from typing import Dict, Iterable, List, Set

from app.schemas.agents import AgentState, ReasoningTimelineEvent, ReliabilitySignals

# Node type -> bucket. Extraction is LLM-driven so types vary in spelling.
_EQUIPMENT_TYPES = {"equipment", "asset", "machine", "system", "unit"}
_COMPONENT_TYPES = {"component", "part", "subassembly", "assembly"}
_FAILURE_TYPES = {"failuremode", "failure_mode", "failure", "incident", "fault", "defect"}
_PROCESS_TYPES = {"process", "procedure", "operation", "activity"}

# Edge types that express causation, used to build readable causal chains.
_CAUSAL_EDGE_TYPES = {
    "CAUSES", "LEADS_TO", "RESULTS_IN", "TRIGGERS", "INDICATES",
    "CONTRIBUTES_TO", "PRECEDES",
}

_CONDITION_TERMS = {
    "vibration": "abnormal vibration",
    "overheat": "overheating",
    "temperature": "temperature deviation",
    "pressure": "pressure deviation",
    "leak": "leakage",
    "corrosion": "corrosion",
    "crack": "cracking",
    "wear": "wear",
    "noise": "abnormal noise",
    "misalign": "misalignment",
    "lubricat": "lubrication condition",
    "contaminat": "contamination",
    "cavitation": "cavitation",
    "fatigue": "fatigue",
}


def _node_label(node: Dict) -> str:
    return node.get("name") or node.get("canonical_name") or node.get("id") or ""


def _bucket(nodes: Iterable[Dict], types: Set[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for node in nodes:
        node_type = str(node.get("type") or "").strip().lower().replace(" ", "_")
        if node_type in types:
            label = _node_label(node)
            if label and label not in seen:
                seen.add(label)
                out.append(label)
    return out


def _causal_chains(edges: List[Dict]) -> List[str]:
    chains: List[str] = []
    seen: Set[str] = set()
    for edge in edges:
        edge_type = str(edge.get("type") or "").strip().upper()
        if edge_type not in _CAUSAL_EDGE_TYPES:
            continue
        chain = f"{edge.get('source')} -> {edge_type} -> {edge.get('target')}"
        if chain not in seen:
            seen.add(chain)
            chains.append(chain)
    return chains[:12]


def _condition_indicators(state: AgentState) -> List[str]:
    corpus_parts: List[str] = []
    for chunk in state.semantic_chunks:
        text = chunk.get("text")
        if text:
            corpus_parts.append(text)
    for edge in state.graph_edges:
        evidence = edge.get("evidence")
        if evidence:
            corpus_parts.append(evidence)
    for node in state.graph_nodes:
        label = _node_label(node)
        if label:
            corpus_parts.append(label)

    corpus = " ".join(corpus_parts).lower()
    return [label for term, label in _CONDITION_TERMS.items() if term in corpus]


def _severity(signals: ReliabilitySignals) -> str:
    """Graded from graph structure only. The model may override in its answer."""
    if signals.failure_modes and signals.causal_chains:
        return "High"
    if signals.failure_modes:
        return "Medium"
    if signals.condition_indicators:
        return "Medium"
    return "Low"


def maintenance_agent(state: AgentState) -> AgentState:
    started = time.perf_counter()

    signals = ReliabilitySignals(
        failure_modes=_bucket(state.graph_nodes, _FAILURE_TYPES),
        equipment=_bucket(state.graph_nodes, _EQUIPMENT_TYPES),
        components=_bucket(state.graph_nodes, _COMPONENT_TYPES),
        processes=_bucket(state.graph_nodes, _PROCESS_TYPES),
        condition_indicators=_condition_indicators(state),
        causal_chains=_causal_chains(state.graph_edges),
    )
    signals.severity_hint = _severity(signals)  # type: ignore[assignment]
    state.signals = signals

    if signals.is_empty and not signals.condition_indicators:
        summary = "No failure modes, equipment, or condition indicators found in the retrieved subgraph."
    else:
        summary = (
            f"Classified {len(signals.equipment)} equipment, "
            f"{len(signals.components)} components, "
            f"{len(signals.failure_modes)} failure modes; "
            f"traced {len(signals.causal_chains)} causal links. "
            f"Severity hint: {signals.severity_hint}."
        )

    state.timeline.append(
        ReasoningTimelineEvent(
            agent_name="ReliabilityAgent",
            action="Analyse reliability signals",
            duration_ms=(time.perf_counter() - started) * 1000,
            summary=summary,
            evidence_generated=len(signals.causal_chains) + len(signals.failure_modes),
        )
    )
    return state


def maintenance_router(state: AgentState) -> str:
    return "coordinator_synthesis"
