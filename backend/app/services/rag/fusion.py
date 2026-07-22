from app.schemas.rag import EvidencePackage

class EvidenceFusion:
    def fuse(self, raw_evidence: EvidencePackage) -> EvidencePackage:
        """
        Merges graph and vector evidence.
        Responsibilities:
        - Remove duplicate chunks
        - Remove duplicate graph nodes
        - Rank evidence
        - Derive confidence from corroborating sources
        """
        # 1. Deduplicate Chunks
        unique_chunks = []
        seen_chunk_ids = set()
        for chunk in raw_evidence.retrieved_chunks:
            chunk_id = chunk.get("chunk_id")
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                unique_chunks.append(chunk)

        # 2. Deduplicate Nodes
        unique_nodes = []
        seen_node_ids = set()
        for node in raw_evidence.retrieved_nodes:
            node_id = node.get("id")
            if node_id not in seen_node_ids:
                seen_node_ids.add(node_id)
                unique_nodes.append(node)
                
        # 3. Deduplicate Relationships
        unique_edges = []
        seen_edges = set()
        for edge in raw_evidence.retrieved_relationships:
            edge_id = f"{edge.get('source')}->{edge.get('target')} ({edge.get('type')})"
            if edge_id not in seen_edges:
                seen_edges.add(edge_id)
                unique_edges.append(edge)
                
        # 4. Consolidate Provenance
        provenance = set()
        for chunk in unique_chunks:
            if "document_id" in chunk:
                provenance.add(chunk["document_id"])
        for node in unique_nodes:
            if "source_document_id" in node:
                provenance.add(node["source_document_id"])
        for edge in unique_edges:
            if "source_document_id" in edge:
                provenance.add(edge["source_document_id"])

        # 5. Derive Confidence
        # E.g. If we have both semantic chunks and graph relationships supporting it, confidence is higher.
        confidence = 0.5
        if len(unique_chunks) > 0:
            confidence += 0.2
        if len(unique_edges) > 0:
            confidence += 0.2
        if len(provenance) > 1:
            confidence += 0.1 # Corroborated by multiple documents
            
        confidence = min(1.0, confidence)
        
        return EvidencePackage(
            retrieved_chunks=unique_chunks,
            retrieved_nodes=unique_nodes,
            retrieved_relationships=unique_edges,
            provenance_links=list(provenance),
            overall_confidence=confidence
        )

evidence_fusion = EvidenceFusion()
