"""
Document Converter - convert documents to Markdown for BE.

Pipeline:
  1. MarkItDown converts PDF/DOCX/XLSX/... → Markdown
     - Image captioning via dedicated Vision LLM (Qwen3-VL-8B-Instruct)
  2. Return markdown content to BE for persistence
"""

import logging
import re
from pathlib import Path

from openai import OpenAI

from markitdown import MarkItDown

from app.config import settings
from app.services.embedding_service import embedding_service
from app.services.markdown_chunking import build_chunk_records, structure_ocr_markdown

logger = logging.getLogger(__name__)

# Vision LLM đôi khi vẫn chèn câu dẫn kiểu "Here is the extracted text..." dù
# đã bị cấm trong prompt. Cắt bỏ dòng dẫn này nếu có, để không lẫn vào markdown.
_PREAMBLE_PATTERN = re.compile(
    r"^\s*(here('|’)s|here is|sure[,!]?|certainly|below is|i (have|'ve) extracted)"
    r"[^\n]{0,200}:\s*\n+",
    re.IGNORECASE,
)


def _strip_preamble(text: str) -> str:
    return _PREAMBLE_PATTERN.sub("", text, count=1)


class DocumentConverter:
    """Convert document files to Markdown text using MarkItDown + Vision LLM."""

    def __init__(self):
        # Initialize MarkItDown with Vision LLM for image captioning/OCR
        # Uses dedicated Qwen3-VL-8B-Instruct server for processing images
        ocr_client = OpenAI(
            base_url=settings.ocr_vllm_base_url,
            api_key=settings.ocr_vllm_api_key or "no-key",
        )
        self._markitdown = MarkItDown(
            llm_client=ocr_client,
            llm_model=settings.ocr_vllm_model_name,
            enable_plugins=True,
            llm_prompt=(
                "Extract all text from this image exactly as it appears, "
                "preserving table structure. Output ONLY the extracted text — "
                "no preamble, no introduction, no explanation, no phrases like "
                "'Here is the extracted text'."
            ),
        )
        logger.info(
            f"MarkItDown initialized with Vision LLM: "
            f"{settings.ocr_vllm_base_url} model={settings.ocr_vllm_model_name} (Plugins enabled)"
        )

    def convert_to_markdown(self, file_path: str) -> str:
        return self.convert_document(file_path)["markdown_content"]

    def chunk_and_embed_markdown(self, markdown: str, filename: str = "") -> dict[str, object]:
        return self._finalize_markdown(markdown, filename or "document.md")

    def convert_document(self, file_path: str) -> dict[str, object]:
        """
        Convert a document file to Markdown text, then chunk + embed it.

        Supports: PDF, DOCX, XLSX, PPTX, HTML, TXT, images, etc.

        Args:
            file_path: Path to the source document.

        Returns:
            Dict with normalized markdown text and chunk count.
        """
        markdown = self._convert_to_raw_markdown(file_path)
        return self._finalize_markdown(markdown, file_path)

    def convert_to_markdown_only(self, file_path: str) -> str:
        """Convert a document to structured Markdown without chunking/embedding.

        Dùng cho các tác vụ đọc-một-lần (ví dụ trích xuất dataset từ file tạm)
        không cần lưu vector, để tránh tốn lệnh gọi embedding không cần thiết.
        """
        markdown = self._convert_to_raw_markdown(file_path)
        return structure_ocr_markdown(markdown)

    def _convert_to_raw_markdown(self, file_path: str) -> str:
        """Try MarkItDown (Vision LLM OCR), then plain-text fallback."""
        logger.info(f"Converting to Markdown: {file_path}")

        markitdown_error: Exception | None = None
        try:
            markdown = self._convert_with_markitdown(file_path)
            if markdown:
                logger.info(
                    "Converted to Markdown with markitdown_vision: %d chars from %s",
                    len(markdown),
                    file_path,
                )
                return markdown
            logger.warning("MarkItDown returned empty Markdown for %s", file_path)
        except Exception as exc:
            markitdown_error = exc
            logger.error("MarkItDown conversion failed for %s: %s", file_path, exc)

        plain_text = self._read_plain_text_fallback(file_path)
        if plain_text:
            logger.warning(
                "Converted to Markdown with plain_text_fallback: %d chars from %s",
                len(plain_text),
                file_path,
            )
            return plain_text

        if markitdown_error:
            raise ValueError(f"Cannot convert file to text: {file_path}") from markitdown_error
        raise ValueError(f"Cannot convert file to text: {file_path}")

    def _finalize_markdown(self, markdown: str, file_path: str) -> dict[str, object]:
        structured_markdown = structure_ocr_markdown(markdown)
        chunk_records = build_chunk_records(
            structured_markdown,
            settings.embedding_chunk_size,
            filename=Path(file_path).name,
        )
        embeddings = embedding_service.embed_texts(
            [chunk["chunk_text"] for chunk in chunk_records],
            input_type="document",
        )
        embedded_chunks: list[dict] | None = None
        if embeddings and len(embeddings) == len(chunk_records):
            embedded_chunks = []
            for chunk, vector in zip(chunk_records, embeddings):
                embedded_chunks.append(
                    {
                        **chunk,
                        "embedding_model": embedding_service.model_name,
                        "embedding": vector,
                    }
                )
        elif embeddings:
            logger.warning(
                "Embedding count mismatch for %s: chunks=%s embeddings=%s",
                file_path,
                len(chunk_records),
                len(embeddings),
            )

        return {
            "markdown_content": structured_markdown,
            "chunk_count": len(chunk_records),
            "embedding_model_name": embedding_service.model_name if embedded_chunks else "",
            "chunks": embedded_chunks,
        }

    def _convert_with_markitdown(self, file_path: str) -> str:
        result = self._markitdown.convert(file_path)
        raw_markdown = result.text_content

        # Regex tìm nội dung giữa *[Image OCR] ... [End OCR]* (Dành cho file scan PDF/Image)
        pattern = r"\*\[Image OCR\](.*?)\[End OCR\]\*"
        matches = re.findall(pattern, raw_markdown or "", re.DOTALL)

        if matches:
            # Nếu có nhiều block OCR → nối lại
            cleaned = [_strip_preamble(match).strip() for match in matches]
            return "\n".join(block for block in cleaned if block).strip()

        # Nếu không có → trả toàn bộ nội dung
        return raw_markdown.strip() if raw_markdown else ""

    def _read_plain_text_fallback(self, file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix not in (".txt", ".md", ".csv"):
            return ""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception as exc:
            logger.warning("Plain text fallback failed for %s: %s", file_path, exc)
            return ""

# Singleton
document_converter = DocumentConverter()
