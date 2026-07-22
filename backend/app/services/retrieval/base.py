from abc import ABC, abstractmethod
from typing import Dict, Any
from app.schemas.rag import QueryPlan, EvidencePackage

class RetrievalStrategy(ABC):
    @abstractmethod
    def retrieve(self, query: str, plan: QueryPlan) -> EvidencePackage:
        """Execute the retrieval strategy based on the query and plan."""
        pass
