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

logger = logging.getLogger(__name__)


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
            llm_prompt="Extract all text from this image, preserving table structure.",
        )
        logger.info(
            f"MarkItDown initialized with Vision LLM: "
            f"{settings.ocr_vllm_base_url} model={settings.ocr_vllm_model_name} (Plugins enabled)"
        )

    def convert_to_markdown(self, file_path: str) -> str:
        """
        Convert a document file to Markdown text.

        Supports: PDF, DOCX, XLSX, PPTX, HTML, TXT, images, etc.

        Args:
            file_path: Path to the source document.

        Returns:
            Markdown text content.
        """
        logger.info(f"Converting to Markdown: {file_path}")

        try:
            result = self._markitdown.convert(file_path)
            raw_markdown = result.text_content

            # Regex tìm nội dung giữa *[Image OCR] ... [End OCR]* (Dành cho file scan PDF/Image)
            pattern = r"\*\[Image OCR\](.*?)\[End OCR\]\*"
            matches = re.findall(pattern, raw_markdown, re.DOTALL)
            
            if matches:
                # Nếu có nhiều block OCR → nối lại
                markdown = "\n".join(match.strip() for match in matches)
            else:
                # Nếu không có → trả toàn bộ nội dung
                markdown = raw_markdown.strip() if raw_markdown else ""

            if not markdown:
                # Fallback: read as plain text for simple text files
                suffix = Path(file_path).suffix.lower()
                if suffix in ('.txt', '.md', '.csv'):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        markdown = f.read()

            logger.info(f"Converted to Markdown: {len(markdown)} chars from {file_path}")
            return markdown

        except Exception as e:
            logger.error(f"MarkItDown conversion failed for {file_path}: {e}")
            # Last resort fallback: try reading as text
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                logger.warning(f"Fallback to plain text read: {file_path}")
                return content
            except Exception:
                raise ValueError(f"Cannot convert file to text: {file_path}")

# Singleton
document_converter = DocumentConverter()
