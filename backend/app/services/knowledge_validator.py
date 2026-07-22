import logging
from app.schemas.knowledge import KnowledgeGraphExtraction

logger = logging.getLogger(__name__)

class KnowledgeValidator:
    """
    Validates extracted knowledge before insertion into the graph.
    Checks for orphans, missing references, and duplicate IDs within the payload.
    """
    
    def validate(self, extraction: KnowledgeGraphExtraction) -> bool:
        entity_ids = {e.id for e in extraction.entities}
        
        # Check duplicates
        if len(entity_ids) != len(extraction.entities):
            logger.error("Validation Failed: Duplicate Entity IDs found.")
            return False
            
        # Check missing references
        for rel in extraction.relationships:
            if rel.source_entity_id not in entity_ids:
                logger.error(f"Validation Failed: Source entity {rel.source_entity_id} missing for relationship.")
                return False
            if rel.target_entity_id not in entity_ids:
                logger.error(f"Validation Failed: Target entity {rel.target_entity_id} missing for relationship.")
                return False
                
            # Check circular self-links
            if rel.source_entity_id == rel.target_entity_id:
                logger.error(f"Validation Failed: Circular self-link on {rel.source_entity_id}.")
                return False
                
        logger.info(f"Knowledge extraction passed validation ({len(extraction.entities)} entities, {len(extraction.relationships)} relationships).")
        return True

knowledge_validator = KnowledgeValidator()
