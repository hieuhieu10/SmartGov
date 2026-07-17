"""
STTNB Document Router — Upload and manage documents in repositories.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse

from app.auth import get_current_user, can_access_repo
from app.config import settings
from app import database as db
from app.models import DocumentResponse
from app.services.docx_preview import render_docx_preview_html
from app.services.repository_service import repository_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories/{repo_id}/documents", tags=["Documents"])


def _public_ai_text(value: object) -> str:
    """Hide implementation-specific engine names in user-facing API text."""
    text = str(value or "")
    for old, new in {
        "NotebookLM": "Server 1",
        "notebooklm": "Server 1",
        "self-hosted": "Server 2",
        "Self-hosted": "Server 2",
        "self_hosted": "Server 2",
    }.items():
        text = text.replace(old, new)
    return text


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024


def _build_document_response(doc: dict) -> DocumentResponse:
    return DocumentResponse(
        id=doc["id"],
        repository_id=doc["repository_id"],
        filename=doc["filename"],
        file_size=doc["file_size"],
        file_type=doc["file_type"],
        processing_status=doc.get("processing_status") or "queued",
        progress_message=_public_ai_text(doc.get("progress_message")),
        error_message=_public_ai_text(doc.get("error_message")),
        chunk_count=doc.get("chunk_count") or 0,
        processed_at=doc.get("processed_at"),
        uploaded_at=doc["uploaded_at"],
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    repo_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload tài liệu vào kho dữ liệu.
    
    Hỗ trợ tất cả định dạng: PDF, Word, Excel, PowerPoint, ảnh, audio, video, text...
    
    Tài liệu sẽ tự động được xử lý bởi hệ thống AI.
    """
    # Validate extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_doc_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng file không được hỗ trợ: {file_ext}. "
                   f"Hỗ trợ: {', '.join(settings.allowed_doc_extensions)}",
        )

    # Validate size
    content = await file.read()
    if len(content) > settings.max_doc_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Giới hạn: {settings.max_doc_upload_mb}MB",
        )

    # Check ownership (only owner can upload)
    repo = await can_access_repo(repo_id, current_user)
    if not repo.get("is_owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ chủ sở hữu kho mới có quyền thêm tài liệu",
        )

    current_total = await db.get_user_total_document_bytes(current_user["id"])
    projected_total = current_total + len(content)
    if projected_total > settings.max_user_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "Vượt giới hạn tổng dung lượng upload của tài khoản. "
                f"Đã dùng: {_format_bytes(current_total)}; "
                f"file tải lên: {_format_bytes(len(content))}; "
                f"giới hạn: {_format_bytes(settings.max_user_upload_bytes)}."
            ),
        )

    try:
        doc = await repository_service.upload_document(
            repo_id=repo_id,
            user_id=current_user["id"],
            filename=file.filename,
            content=content,
            file_type=file.content_type or "",
            current_user=current_user,
        )
        return _build_document_response(doc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    repo_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Liệt kê tất cả tài liệu trong kho (bao gồm kho chia sẻ)."""
    # Allow both owner and shared users to list documents
    await can_access_repo(repo_id, current_user)

    docs = await db.get_documents_by_repository(repo_id)
    return [_build_document_response(d) for d in docs]


@router.get("/{doc_id}/preview", response_class=HTMLResponse)
async def preview_document(
    repo_id: str,
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Preview an uploaded Word document as HTML without downloading it."""
    await can_access_repo(repo_id, current_user)

    doc = await db.get_document_by_id(doc_id)
    if not doc or doc.get("repository_id") != repo_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tài liệu không tồn tại")

    file_path = Path(doc.get("stored_path") or "")
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file tài liệu")

    if file_path.suffix.lower() != ".docx":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Xem trước dạng Word hiện chỉ hỗ trợ file .docx",
        )

    return HTMLResponse(render_docx_preview_html(file_path))


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    repo_id: str,
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Xóa tài liệu khỏi kho dữ liệu (chỉ chủ sở hữu)."""
    repo = await can_access_repo(repo_id, current_user)
    if not repo.get("is_owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ chủ sở hữu kho mới có quyền xóa tài liệu",
        )
    try:
        await repository_service.delete_document(repo_id, doc_id, current_user["id"], current_user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
