"""Document dataset extraction API."""

import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

from app.auth import get_current_user
from app.config import settings
from app.models import DocumentDatasetResponse, DocumentDatasetWordRequest
from app.services.ai_client import AIServiceError, ai_client
from app.services.document_dataset_service import document_dataset_service
from app.services.docx_preview import render_docx_preview_html
from app.services.nd30_exporter import build as build_nd30_docx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/document-datasets", tags=["Document Datasets"])


def _safe_docx_name(filename: str) -> str:
    stem = Path(filename or "van-ban.docx").stem
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip(".-") or "van-ban"
    return f"{stem[:120]}.docx"


def _export_nd30_document(document_data: dict, filename: str) -> Path:
    if not document_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thiếu document_data để tạo file Word.",
        )

    output_dir = Path(settings.output_dir) / "nd30_exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{uuid.uuid4()}_{_safe_docx_name(filename)}"
    try:
        build_nd30_docx(document_data, str(output_path))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể tạo file Word từ document_data: {exc}",
        ) from exc
    return output_path


@router.post("/extract", response_model=DocumentDatasetResponse)
async def extract_document_dataset(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Extract title, content and table-field schema from an uploaded document.

    The file is converted to Markdown and read by the AI service (LLM), then
    mapped into the stable dataset contract FE already integrates against. If
    AI extraction fails for any reason, falls back to a clearly-labeled mock
    response instead of failing the request outright.
    """
    _ = current_user
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ten file khong hop le.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_doc_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chi ho tro file {', '.join(settings.allowed_doc_extensions)}.",
        )

    content = await file.read()
    if len(content) > settings.max_doc_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Giới hạn: {settings.max_doc_upload_mb}MB",
        )

    tmp_dir = Path(settings.upload_dir) / "dataset_extract_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4()}_{Path(file.filename).name}"
    try:
        tmp_path.write_bytes(content)
        document_data = await ai_client.extract_dataset(str(tmp_path), file.filename)
        if not document_data:
            raise AIServiceError("AI trả dữ liệu rỗng")
        return document_dataset_service.build_ai_response(file.filename, document_data)
    except Exception as exc:
        logger.warning("Dataset AI extraction failed for %s: %s", file.filename, exc)
        response = document_dataset_service.build_mock_response(file.filename)
        response.message = f"AI trích xuất thất bại ({exc}); đang hiển thị dữ liệu mẫu tạm thời."
        return response
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/word/preview", response_class=HTMLResponse)
async def preview_dataset_word(
    req: DocumentDatasetWordRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a DOCX from AI JSON using toolnd30, then show it in a popup preview."""
    _ = current_user
    output_path = _export_nd30_document(req.document_data, req.filename)
    try:
        html = render_docx_preview_html(output_path)
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
    return HTMLResponse(html)


@router.post("/word/download")
async def download_dataset_word(
    req: DocumentDatasetWordRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate and download a DOCX from AI JSON using the integrated toolnd30 exporter."""
    _ = current_user
    output_path = _export_nd30_document(req.document_data, req.filename)
    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=_safe_docx_name(req.filename),
        background=BackgroundTask(lambda path: Path(path).unlink(missing_ok=True), str(output_path)),
    )
