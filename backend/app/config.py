import os
from pathlib import Path
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

# Explicitly locate backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    root_env = BASE_DIR.parent / ".env"
    if root_env.exists():
        load_dotenv(dotenv_path=root_env)
    else:
        load_dotenv()

def _get_cors_origins() -> List[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    custom = os.getenv("ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL")
    if custom:
        for item in custom.split(","):
            cleaned = item.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
    return origins

class Settings(BaseModel):
    APP_NAME: str = "EventSnap API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # Cloudinary Credentials (loaded from backend/.env or environment)
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    
    # AI Matching Threshold
    FACE_SIMILARITY_THRESHOLD: float = 0.50
    MAX_UPLOAD_SIZE_MB: int = 15

    # Google Drive Import
    MAX_IMPORT_FILES: int = int(os.getenv("MAX_IMPORT_FILES", "500"))
    GOOGLE_DRIVE_API_KEY: str = os.getenv("GOOGLE_DRIVE_API_KEY", "")
    GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "")
    GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
    
    # Server Binding
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS (Configurable via ALLOWED_ORIGINS or FRONTEND_URL env var, no wildcard)
    CORS_ORIGINS: List[str] = _get_cors_origins()

settings = Settings()
