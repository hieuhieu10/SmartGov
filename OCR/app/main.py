"""Internal OCR service backed by PaddleOCR.

This service is intentionally private to the Docker network. The AI service
calls it only as a fallback when MarkItDown/Vision LLM cannot produce text.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import fitz
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from paddleocr import PaddleOCR
from pydantic import BaseModel

logger = logging.getLogger("officeai.ocr")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="OfficeAI Internal OCR Service", version="1.0.0")

REPO_FILES_DIR = Path(os.getenv("REPO_FILES_DIR", "/app/repo_files")).resolve()
OCR_LANG = os.getenv("PADDLEOCR_LANG", "vi")
PDF_DPI = int(os.getenv("OCR_PDF_DPI", "180"))

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
PDF_SUFFIXES = {".pdf"}

_ocr: PaddleOCR | None = None


class MarkdownRequest(BaseModel):
    file_path: str


def ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, **(data or {})}


def error(message: str, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error": message, "engine": "paddleocr"},
    )


def get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        logger.info("Initializing PaddleOCR lang=%s", OCR_LANG)
        try:
            _ocr = PaddleOCR(use_angle_cls=True, lang=OCR_LANG, show_log=False)
        except ValueError:
            # PaddleOCR 3.x renamed angle/doc controls. Keep this fallback so a
            # future dependency bump does not break service startup immediately.
            _ocr = PaddleOCR(
                lang=OCR_LANG,
                use_textline_orientation=True,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
            )
    return _ocr


def resolve_input_path(file_path: str) -> Path:
    path = Path(file_path).resolve()
    try:
        path.relative_to(REPO_FILES_DIR)
    except ValueError as exc:
        raise ValueError("File path is outside the shared repo_files volume") from exc
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("File does not exist")
    return path


def extract_lines_from_result(result: Any) -> list[str]:
    lines: list[str] = []
    if not result:
        return lines

    for page in result:
        if not page:
            continue
        for item in page:
            text = ""
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                candidate = item[1]
                if isinstance(candidate, (list, tuple)) and candidate:
                    text = str(candidate[0])
                elif isinstance(candidate, str):
                    text = candidate
            if text.strip():
                lines.append(text.strip())
    return lines


def ocr_image(path: Path) -> str:
    result = get_ocr().ocr(str(path), cls=True)
    return "\n".join(extract_lines_from_result(result)).strip()


def ocr_pdf(path: Path) -> str:
    pages: list[str] = []
    scale = PDF_DPI / 72
    matrix = fitz.Matrix(scale, scale)

    with fitz.open(path) as doc, tempfile.TemporaryDirectory() as temp_dir:
        for page_index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = Path(temp_dir) / f"page-{page_index}.png"
            pix.save(str(image_path))
            text = ocr_image(image_path)
            if text:
                pages.append(f"## Trang {page_index}\n\n{text}")

    return "\n\n".join(pages).strip()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "officeai-ocr"}


@app.post("/ocr/markdown")
async def ocr_markdown(payload: MarkdownRequest):
    try:
        path = resolve_input_path(payload.file_path)
    except (FileNotFoundError, ValueError) as exc:
        return error(str(exc), status_code=400)

    suffix = path.suffix.lower()
    try:
        if suffix in IMAGE_SUFFIXES:
            markdown = ocr_image(path)
        elif suffix in PDF_SUFFIXES:
            markdown = ocr_pdf(path)
        else:
            return error(f"Unsupported OCR file type: {suffix or '(none)'}")
    except Exception as exc:
        logger.exception("PaddleOCR failed for %s", path)
        return error(str(exc), status_code=500)

    if not markdown.strip():
        return error("No OCR text extracted")

    logger.info("PaddleOCR extracted %d chars from %s", len(markdown), path)
    return ok({"markdown": markdown, "engine": "paddleocr"})
