from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_settings
from app.core.config import Settings

router = APIRouter()

@router.get("/")
def check_health(settings: Settings = Depends(get_current_settings)):
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "project": settings.PROJECT_NAME
    }
