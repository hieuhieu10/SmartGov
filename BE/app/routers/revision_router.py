"""Revision task router: comments -> proposed document -> review -> final."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse

from app import database as db
from app.auth import can_access_repo, get_current_user
from app.config import settings
from app.models import RevisionRejectRequest, RevisionReviewResponse, RevisionTaskResponse
from app.services.docx_preview import render_docx_preview_html
from app.services.revision_service import revision_service


router = APIRouter(prefix="/api/revision-tasks", tags=["Revision Tasks"])


def _task_to_response(task: dict) -> RevisionTaskResponse:
    return RevisionTaskResponse(
        id=task["id"],
        title=task.get("title", ""),
        status=task.get("status", "pending"),
        progress_message=task.get("progress_message", ""),
        error_message=task.get("error_message", ""),
        reject_reason=task.get("reject_reason", ""),
        output_ready=bool(task.get("final_file")) and Path(task.get("final_file", "")).exists(),
        created_at=task.get("created_at", ""),
        updated_at=task.get("updated_at", ""),
    )


async def _get_owned_task(task_id: str, current_user: dict) -> dict:
    task = await db.get_revision_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task không tồn tại")
    if task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
    return task


def _validate_extension(filename: str) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in settings.allowed_doc_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng file không được hỗ trợ: {ext}",
        )


async def _read_upload(file: UploadFile | None) -> dict | None:
    if not file or not file.filename:
        return None
    _validate_extension(file.filename)
    content = await file.read()
    if len(content) > settings.max_doc_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Giới hạn: {settings.max_doc_upload_mb}MB",
        )
    return {
        "filename": file.filename,
        "content": content,
        "file_type": file.content_type or "",
    }


@router.post("", response_model=RevisionTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_revision_task(
    title: str = Form(default=""),
    repo_id: str = Form(default=""),
    original_document_data: str = Form(default=""),
    base_document: UploadFile | None = File(default=None),
    comment_files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
):
    """Create a revision task from an original document and one or more comment files."""
    if repo_id:
        await can_access_repo(repo_id, current_user)

    parsed_original = revision_service.parse_document_data(original_document_data)
    base_payload = await _read_upload(base_document)
    comments_payload = []
    for file in comment_files:
        payload = await _read_upload(file)
        if payload:
            comments_payload.append(payload)

    if not parsed_original and not base_payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cần gửi base_document hoặc original_document_data.",
        )

    task_id = str(uuid.uuid4())
    task = await revision_service.create_task(
        task_id=task_id,
        user_id=current_user["id"],
        repo_id=repo_id or None,
        title=title or (base_payload or {}).get("filename", "") or "Bản rà soát góp ý",
        original_document_data=parsed_original,
        base_document=base_payload,
        comment_files=comments_payload,
    )
    asyncio.create_task(revision_service.process_mock(task_id))
    return _task_to_response(task)


@router.get("", response_model=list[RevisionTaskResponse])
async def list_revision_tasks(current_user: dict = Depends(get_current_user)):
    tasks = await db.get_revision_tasks_by_user(current_user["id"])
    return [_task_to_response(task) for task in tasks]


@router.get("/{task_id}", response_model=RevisionTaskResponse)
async def get_revision_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = await _get_owned_task(task_id, current_user)
    return _task_to_response(task)


@router.get("/{task_id}/review", response_model=RevisionReviewResponse)
async def get_revision_review(task_id: str, current_user: dict = Depends(get_current_user)):
    task = await _get_owned_task(task_id, current_user)
    return RevisionReviewResponse(
        task_id=task["id"],
        status=task.get("status", ""),
        title=task.get("title", ""),
        original={
            "document_data": task.get("original_document_data") or {},
            "preview_url": f"/api/revision-tasks/{task_id}/preview/original",
        },
        proposed={
            "document_data": task.get("proposed_document_data") or {},
            "preview_url": f"/api/revision-tasks/{task_id}/preview/proposed",
        },
        changes=task.get("diff_data") or [],
        extracted_comments=task.get("extracted_comments") or [],
    )


@router.get("/{task_id}/preview/{kind}", response_class=HTMLResponse)
async def preview_revision_document(
    task_id: str,
    kind: str,
    current_user: dict = Depends(get_current_user),
):
    task = await _get_owned_task(task_id, current_user)
    path_by_kind = {
        "original": task.get("original_file", ""),
        "proposed": task.get("proposed_file", ""),
        "final": task.get("final_file", ""),
    }
    if kind not in path_by_kind:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loại preview không hợp lệ")
    path = Path(path_by_kind[kind] or "")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File preview chưa sẵn sàng")
    return HTMLResponse(render_docx_preview_html(path))


@router.post("/{task_id}/approve", response_model=RevisionTaskResponse)
async def approve_revision_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = await _get_owned_task(task_id, current_user)
    if task.get("status") not in {"ready_for_review", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task chưa sẵn sàng để duyệt")
    updated = await revision_service.approve(task_id)
    return _task_to_response(updated)


@router.post("/{task_id}/reject", response_model=RevisionTaskResponse)
async def reject_revision_task(
    task_id: str,
    req: RevisionRejectRequest,
    current_user: dict = Depends(get_current_user),
):
    task = await _get_owned_task(task_id, current_user)
    if task.get("status") != "ready_for_review":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task chưa sẵn sàng để từ chối")
    updated = await revision_service.reject(task_id, req.reason)
    return _task_to_response(updated)


@router.get("/{task_id}/download/final")
async def download_final_revision(task_id: str, current_user: dict = Depends(get_current_user)):
    task = await _get_owned_task(task_id, current_user)
    if task.get("status") != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bản cuối chưa được duyệt")
    path = Path(task.get("final_file") or "")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file hoàn chỉnh")
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{Path(task.get('title') or 'van-ban-hoan-chinh').stem[:80]}.docx",
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_revision_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = await _get_owned_task(task_id, current_user)
    await revision_service.delete_files(task)
    await db.delete_revision_task(task_id)
