"""
STTNB Configuration — Settings loaded from .env
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # File upload
    max_upload_mb: int = 100
    max_doc_upload_mb: int = 50
    max_user_upload_gb: float = 5

    # Directory paths
    upload_dir: str = str(BASE_DIR / "uploads")
    output_dir: str = str(BASE_DIR / "outputs")
    template_dir: str = str(BASE_DIR / "app" / "templates")
    repo_files_dir: str = str(BASE_DIR / "repo_files")
    data_dir: str = str(BASE_DIR / "data")
    user_templates_dir: str = str(BASE_DIR / "user_templates")

    # AI Engine
    ai_engine: str = "self_hosted"
    server1_max_repositories: int = 450

    # PostgreSQL (owned exclusively by BE)
    database_url: str = "postgresql+asyncpg://officeai:officeai@postgres:5432/officeai"
    admin_username: str = "admin"
    admin_password: str = ""
    admin_full_name: str = "System Administrator"

    # Internal AI service
    ai_service_url: str = "http://ai:7000"
    ai_internal_token: str = ""
    embedding_dimensions: int = 768
    rag_top_k: int = 8
    rag_vector_candidates: int = 30
    rag_text_candidates: int = 30
    rag_vector_weight: float = 0.6
    rag_text_weight: float = 1.4

    # JWT Authentication
    jwt_secret: str = "change-me-in-production-sttnb-2026"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Legacy setting kept only so existing .env files remain compatible.
    # Repository creation is no longer limited by this value.
    max_repos_per_user: int = 0

    # Allowed audio formats (for legacy audio upload)
    allowed_extensions: List[str] = [
        ".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".aac", ".wma"
    ]

    # Allowed document formats (for repository documents)
    allowed_doc_extensions: List[str] = [
        ".pdf", ".docx", ".doc", ".txt", ".rtf",
        ".xlsx", ".xls", ".csv",
        ".pptx", ".ppt",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
        ".html", ".htm", ".md",
        ".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac",
        ".mp4", ".avi", ".mkv", ".mov",
    ]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_doc_upload_bytes(self) -> int:
        return self.max_doc_upload_mb * 1024 * 1024

    @property
    def max_user_upload_bytes(self) -> int:
        return int(self.max_user_upload_gb * 1024 * 1024 * 1024)

    @property
    def template_path(self) -> Path:
        return Path(self.template_dir) / "bien_ban_hop.docx"

    @property
    def is_self_hosted(self) -> bool:
        """Check if the system is configured to use self-hosted AI engine."""
        return self.ai_engine == "self_hosted"

    def ensure_dirs(self):
        """Create all required directories if they don't exist."""
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.repo_files_dir).mkdir(parents=True, exist_ok=True)
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.user_templates_dir).mkdir(parents=True, exist_ok=True)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton settings instance
settings = Settings()
settings.ensure_dirs()
