from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "NeuroFab AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # DB config (Using SQLite for demo stability without Docker)
    DATABASE_URL: str = "sqlite:///./neurofab_os.db"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()
