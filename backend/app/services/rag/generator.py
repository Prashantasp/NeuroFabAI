from typing import List, Dict, Any
from app.schemas.rag import EvidencePackage, ExplainableAnswer

class ExplainableGenerator:
    def generate(self, query: str, evidence: EvidencePackage) -> ExplainableAnswer:
        """
        Mocked generator for Phase 7.
        In production, this would inject the `EvidencePackage` into a Gemini/OpenAI prompt.
        """
        
        # Build reasoning based on fused evidence
        reasoning = f"Analyzed {len(evidence.retrieved_chunks)} document chunks and {len(evidence.retrieved_relationships)} graph relationships. "
        
        supporting_docs = [f"doc_{doc_id}" for doc_id in evidence.provenance_links]
        
        rel_snippets = []
        for edge in evidence.retrieved_relationships:
            if "evidence" in edge:
                rel_snippets.append(edge["evidence"])
        
        conf_label = "High"
        if evidence.overall_confidence < 0.8:
            conf_label = "Medium"
        if evidence.overall_confidence < 0.5:
            conf_label = "Low"

        # Mocked answer based on query
        answer_text = "Based on the retrieved industrial knowledge, the components are operating normally."
        action = "Continue standard operations."
        risk = "Low"
        
        if "overheating" in query.lower():
            answer_text = "The Outboard Bearing on Centrifugal Pump P-101 is likely overheating due to skipped lubrication."
            action = "Dispatch maintenance technician to inspect and lubricate P-101 Outboard Bearing immediately."
            risk = "High"
        elif "sop" in query.lower():
            answer_text = "The Maintenance SOP discusses bearing maintenance procedures."
            action = "Review the SOP before beginning maintenance."
            risk = "Low"
            
        return ExplainableAnswer(
            answer=answer_text,
            executive_summary=answer_text[:50] + "...",
            reasoning=reasoning,
            supporting_documents=supporting_docs,
            supporting_graph_relationships=rel_snippets,
            confidence=evidence.overall_confidence,
            confidence_label=conf_label,
            recommended_action=action,
            risk_level=risk,
            assumptions=["Assuming retrieved logs and relationships are up to date."],
            citations=[] # Detailed citations can be added later
        )

explainable_generator = ExplainableGenerator()
