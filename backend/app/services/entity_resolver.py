import re
from typing import List, Dict, Any

class EntityResolver:
    """
    Normalizes entities and extracts them based on the actual graph knowledge.
    """
    
    def extract_and_resolve(self, text: str, graph_topology: Dict[str, Any]) -> List[str]:
        """
        Scans text for entities present in the graph topology and returns their canonical names.
        """
        resolved_entities = set()
        if not text:
            return []
            
        text_lower = text.lower()
        
        for node in graph_topology.get("nodes", []):
            canonical = node.get("canonical_name", "")
            raw = node.get("raw_name", "")
            
            # 1. Exact substring match
            if canonical and len(canonical) > 3 and canonical.lower() in text_lower:
                resolved_entities.add(canonical)
                continue
            if raw and len(raw) > 3 and raw.lower() in text_lower:
                resolved_entities.add(canonical)
                continue
                
            # 2. Check property values (e.g. tag "P-500")
            matched = False
            for key, val in node.get("properties", {}).items():
                if isinstance(val, str) and len(val) > 3 and val.lower() in text_lower:
                    resolved_entities.add(canonical)
                    matched = True
                    break
            
            if matched:
                continue
                
            # 3. Check for specific alphanumeric tags in the canonical name (e.g. "P-500")
            if canonical:
                words = canonical.split()
                for word in words:
                    # If it's a tag-like word (has letters and numbers, or hyphens)
                    if len(word) > 3 and any(c.isdigit() for c in word) and word.lower() in text_lower:
                        resolved_entities.add(canonical)
                        break
                
        return list(resolved_entities)
        
    def resolve(self, raw_name: str) -> str:
        # Fallback for old behaviour if needed
        return " ".join([word.capitalize() for word in raw_name.split()])

entity_resolver = EntityResolver()
