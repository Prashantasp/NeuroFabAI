import os
import json
import logging
from typing import Dict, Any, Optional
from app.schemas.knowledge import KnowledgeGraphExtraction
from app.services.graph.base import GraphBackend
from app.services.graph.networkx_backend import NetworkXBackend
from app.services.graph.neo4j_backend import Neo4jBackend

logger = logging.getLogger(__name__)

# Factory pattern to allow easy switching to Neo4j
def get_graph_backend() -> GraphBackend:
    backend_type = os.getenv("GRAPH_BACKEND", "networkx")
    if backend_type == "neo4j":
        return Neo4jBackend()
    return NetworkXBackend()

# Singleton instance of the GraphBackend
graph_service = get_graph_backend()

def hydrate_graph_from_db():
    try:
        from app.db.session import SessionLocal
        from app.models.document import Document
        
        db = SessionLocal()
        docs = db.query(Document).filter(Document.extracted_knowledge.isnot(None)).all()
        for doc in docs:
            ek = doc.extracted_knowledge
            if ek:
                if isinstance(ek, str):
                    ek = json.loads(ek)
                # Parse it back into KnowledgeGraphExtraction
                if "entities" in ek and "relationships" in ek:
                    extraction = KnowledgeGraphExtraction.model_validate(ek)
                    graph_service.ingest_extraction(extraction)
        logger.info(f"Hydrated graph with {len(docs)} documents from DB.")
        db.close()
    except Exception as e:
        logger.error(f"Failed to hydrate graph: {e}")

# Hydrate on startup
hydrate_graph_from_db()
