from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from app.services.agents.workflow import agent_workflow
from app.schemas.agents import AgentState

router = APIRouter()

class ChatRequest(BaseModel):
    query: str

@router.post("/ask")
def ask_question(request: ChatRequest) -> Dict[str, Any]:
    """
    Accepts a user query, runs it through the Multi-Agent LangGraph workflow,
    and returns a structured Decision Response with a full Reasoning Timeline.
    """
    initial_state = AgentState(query=request.query)
    final_state = agent_workflow.run(initial_state)
    
    return {
        "decision": final_state.final_decision.model_dump() if final_state.final_decision else None,
        "reasoning_timeline": [event.model_dump() for event in final_state.timeline],
        "errors": final_state.errors
    }
