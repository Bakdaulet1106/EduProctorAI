"""
EduProctorAI - Application Configuration
"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "EduProctorAI"
    VERSION: str = "2.0.0"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./database/eduproctor.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-32-chars-minimum")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".txt"}
    UPLOAD_PATH: str = "uploads"

    PROCTOR_FRAME_RATE: int = 15
    PROCTOR_MOVEMENT_THRESHOLD: float = 0.03
    PROCTOR_PENALTY_PER_MOVEMENT: float = 1.0
    PROCTOR_MAX_PENALTY: float = 30.0

    RK1_TIME_LIMIT: int = 35
    RK2_TIME_LIMIT: int = 35
    EXAM_TIME_LIMIT: int = 80
    WRITTEN_TIME_LIMIT: int = 60

    RK1_QUESTIONS_COUNT: int = 20
    RK2_QUESTIONS_COUNT: int = 20
    EXAM_QUESTIONS_COUNT: int = 50
    
    WRITTEN_RK1_COUNT: int = 3
    WRITTEN_RK2_COUNT: int = 3
    WRITTEN_EXAM_COUNT: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()