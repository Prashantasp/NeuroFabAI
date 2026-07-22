from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.exceptions import global_exception_handler, custom_app_exception_handler, NeuroFabException
from app.api.v1.api import api_router
from app.db.session import engine, Base
from app.models.document import Document  # Ensure model is registered

# Create DB tables
Base.metadata.create_all(bind=engine)

# Initialize structured logging
setup_logging()

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NeuroFab AI Backend API",
)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(NeuroFabException, custom_app_exception_handler)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
