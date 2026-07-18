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
    vllm_user_agent: str = ""
    vllm_fallback_base_url: str = ""
    vllm_fallback_model_name: str = ""
    vllm_fallback_api_key: str = ""
    # Model chính fail-fast: chờ tối đa ngần này (giây) rồi chuyển fallback ngay,
    # không retry, để giảm thời gian chờ khi model chính timeout/quá tải.
    vllm_primary_timeout: float = 240.0
    vllm_fallback_timeout: float = 600.0
    # (B) Tự nối tiếp khi model bị cắt vì hết token (finish_reason=length).
    llm_auto_continue: bool = True
    llm_max_continuations: int = 3
    # (D) Map-reduce cho tổng hợp góp ý: kích thước mỗi batch văn bản góp ý.
    summary_batch_max_docs: int = 8
    summary_batch_max_chars: int = 60000
    ocr_vllm_base_url: str = "http://host.docker.internal:8686/v1"
    ocr_vllm_model_name: str = "your-vision-model"
    ocr_vllm_api_key: str = ""
    embedding_base_url: str = "https://api-inference.huggingface.co/models/dangvantuan/vietnamese-embedding"
    embedding_model_name: str = "dangvantuan/vietnamese-embedding"
    embedding_api_key: str = ""
    embedding_dimensions: int = 768
    embedding_batch_size: int = 16
    # 800 để khớp giới hạn 256 token của model PhoBERT (dangvantuan/
    # vietnamese-embedding) — thực nghiệm: 800 ký tự OK, 1000 trở lên HF trả 400.
    embedding_chunk_size: int = 800
    # Lưới an toàn: cắt mỗi text về tối đa ngần này ký tự trước khi gọi API
    # embedding (tránh 400 "index out of range" với text dài bất thường).
    embedding_max_chars: int = 800
    ocr_service_url: str = "http://ocr:7100"
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
