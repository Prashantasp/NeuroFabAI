import re
from typing import List
from app.schemas.rag import QueryPlan

class QueryPlanner:
    def plan(self, query: str) -> QueryPlan:
        """
        Analyzes the user's intent and selects the optimal retrieval strategy.
        Uses heuristics for this demo, but would use an LLM in production.
        """
        query_lower = query.lower()
        
        # Simple heuristics for Phase 7
        is_troubleshooting = any(kw in query_lower for kw in ["why", "how", "fix", "error", "overheating", "failure"])
        is_graph_heavy = any(kw in query_lower for kw in ["related", "components", "connected to", "who", "which sop"])
        
        extracted_entities = self._mock_extract_entities(query_lower)
        
        if is_troubleshooting:
            return QueryPlan(
                detected_intent="troubleshooting",
                confidence=0.92,
                selected_strategy="Hybrid",
                reasoning="Troubleshooting queries require both semantic document chunks and related failure graph nodes.",
                extracted_entities=extracted_entities
            )
        elif is_graph_heavy:
            return QueryPlan(
                detected_intent="relationship reasoning",
                confidence=0.88,
                selected_strategy="Graph",
                reasoning="Query asks for relationships between entities.",
                extracted_entities=extracted_entities
            )
        else:
            return QueryPlan(
                detected_intent="semantic lookup",
                confidence=0.85,
                selected_strategy="Vector",
                reasoning="General information query, vector search is most appropriate.",
                extracted_entities=extracted_entities
            )
            
    def _mock_extract_entities(self, query: str) -> List[str]:
        # A simple mock entity extractor for the planner
        entities = []
        if "p-101" in query or "pump" in query:
            entities.append("Pump P-101")
        if "bearing" in query:
            entities.append("Outboard Bearing")
        if "lubrication" in query:
            entities.append("Lubrication")
        return entities

query_planner = QueryPlanner()
