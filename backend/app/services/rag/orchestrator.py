from typing import Dict, Any
from app.services.rag.planner import query_planner
from app.services.rag.fusion import evidence_fusion
from app.services.rag.generator import explainable_generator
from app.services.retrieval.vector import VectorRetrieval
from app.services.retrieval.graph import GraphRetrieval
from app.services.retrieval.hybrid import HybridRetrieval

class GraphRAGOrchestrator:
    def __init__(self):
        self.strategies = {
            "Vector": VectorRetrieval(),
            "Graph": GraphRetrieval(),
            "Hybrid": HybridRetrieval()
        }

    def ask(self, query: str) -> Dict[str, Any]:
        """
        The main GraphRAG pipeline.
        1. Plan
        2. Retrieve
        3. Fuse
        4. Generate
        """
        
        # 1. Plan
        plan = query_planner.plan(query)
        
        # 2. Retrieve
        strategy = self.strategies.get(plan.selected_strategy, self.strategies["Vector"])
        raw_evidence = strategy.retrieve(query, plan)
        
        # 3. Fuse
        fused_evidence = evidence_fusion.fuse(raw_evidence)
        
        # 4. Generate
        answer = explainable_generator.generate(query, fused_evidence)
        
        # Return full payload as requested by API design
        return {
            "query_plan": plan.model_dump(),
            "retrieved_chunks": raw_evidence.retrieved_chunks,
            "retrieved_graph": {
                "nodes": raw_evidence.retrieved_nodes,
                "edges": raw_evidence.retrieved_relationships
            },
            "fused_evidence": fused_evidence.model_dump(),
            "explainable_answer": answer.model_dump()
        }

rag_orchestrator = GraphRAGOrchestrator()
