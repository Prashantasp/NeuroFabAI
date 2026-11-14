from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, documents, graph, search, system, users, workspaces

api_router = APIRouter()

api_router.include_router(system.router, prefix="/health", tags=["System"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(graph.router, prefix="/graph", tags=["Knowledge Graph"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(chat.router, prefix="/chat", tags=["Copilot"])
