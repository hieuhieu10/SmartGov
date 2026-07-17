"""Configuration for the internal AI service."""

from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 7000
    ai_internal_token: str = ""
    ai_engine: str = "notebooklm"
    upload_dir: str = str(BASE_DIR / "uploads")
    output_dir: str = str(BASE_DIR / "outputs")
    repo_files_dir: str = str(BASE_DIR / "repo_files")
    user_templates_dir: str = str(BASE_DIR / "user_templates")
    vllm_base_url: str = "http://host.docker.internal:8000/v1"
    vllm_model_name: str = "your-model"
    vllm_api_key: str = ""
    ocr_vllm_base_url: str = "http://host.docker.internal:8686/v1"
    ocr_vllm_model_name: str = "your-vision-model"
    ocr_vllm_api_key: str = ""
    doc_chunk_size: int = 80000
    scanner_max_tokens: int = 8192
    context_max_chars: int = 400000

    @property
    def is_self_hosted(self) -> bool:
        return self.ai_engine == "self_hosted"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
