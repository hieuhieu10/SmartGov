"""
STTNB Drafting Router — Soạn văn bản hành chính theo NĐ 30/2020/NĐ-CP.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse

from app.auth import get_current_user, can_access_repo, is_user_self_hosted
from app.config import settings
from app import database as db
from app.models import (
    DocumentType, DraftRequest, DraftTaskResponse, DraftStatusResponse,
    DraftEditRequest, DraftTypeInfo, TaskStatus,
)
from app.services.repository_service import repository_service
from app.services.drafting_service import drafting_service
from app.services.word_exporter import word_exporter
from app.services.docx_preview import render_docx_preview_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Drafting"])


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


@router.get("/draft/types", response_model=list[DraftTypeInfo])
async def list_document_types():
    """
    Liệt kê 6 loại văn bản hành chính được hỗ trợ.

    Trả về thông tin về required_fields và optional_fields cho mỗi loại.
    """
    types = drafting_service.get_document_types()
    return [
        DraftTypeInfo(
            type_code=t["type_code"],
            name=t["name"],
            description=t["description"],
            required_fields=t["required_fields"],
            optional_fields=t["optional_fields"],
        )
        for t in types
    ]


@router.post("/repositories/{repo_id}/draft", response_model=DraftTaskResponse)
async def create_draft(
    repo_id: str,
    req: DraftRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Soạn văn bản hành chính từ dữ liệu trong kho.

    Hệ thống sẽ kết hợp thông tin người dùng nhập với dữ liệu trong kho
    (thông qua AI) để soạn văn bản theo đúng thể thức.

    Trả về task_id để theo dõi tiến trình.
    """
    # Verify access (owner or shared)
    repo = await can_access_repo(repo_id, current_user)
    if not is_user_self_hosted(current_user):
        repo = await repository_service.ensure_notebooklm_session_current(
            repo,
            repo["user_id"],
        )

    # Server 1 mode requires notebook_id
    if not is_user_self_hosted(current_user) and not repo.get("notebook_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kho dữ liệu chưa sẵn sàng. Vui lòng thử lại sau.",
        )

    if not req.document_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vui lòng chọn loại văn bản trước khi soạn.",
        )
    resolved_doc_type = req.document_type

    # Validate required fields
    missing = drafting_service.validate_input(resolved_doc_type, req.input_data)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Thiếu các trường bắt buộc: {', '.join(missing)}",
        )

    # Create task in DB
    task_id = str(uuid.uuid4())
    await db.create_draft_task(
        task_id,
        current_user["id"],
        repo_id,
        resolved_doc_type.value,
        input_data=_json_dumps(req.input_data),
    )

    # Start background processing
    asyncio.create_task(
        _process_draft(
            task_id, repo.get("notebook_id", ""),
            resolved_doc_type, req.input_data, repo_id,
            selected_document_ids=req.selected_document_ids,
            current_user=current_user,
        )
    )

    return DraftTaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        document_type=resolved_doc_type.value,
        message=f"Đang soạn {drafting_service.get_document_types_by_code().get(resolved_doc_type.value, 'văn bản')}...",
    )


@router.post("/draft/edit/{source_task_id}", response_model=DraftTaskResponse)
async def edit_exported_draft(
    source_task_id: str,
    req: DraftEditRequest,
    current_user: dict = Depends(get_current_user),
):
    """Chỉnh sửa nội dung trên file Word đã xuất, không soạn văn bản mới."""
    source_task = await db.get_draft_task_by_id(source_task_id)
    if not source_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task gốc không tồn tại")
    if source_task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
    if source_task.get("status") != TaskStatus.COMPLETED.value or not source_task.get("output_file"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File Word gốc chưa sẵn sàng để chỉnh sửa")
    if not Path(source_task["output_file"]).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file Word gốc")

    task_id = str(uuid.uuid4())
    doc_type = source_task.get("document_type", "")
    source_input_data = _json_loads_dict(source_task.get("input_data"))
    await db.create_draft_task(
        task_id,
        current_user["id"],
        source_task.get("repo_id", ""),
        doc_type,
        input_data=_json_dumps(source_input_data),
    )
    asyncio.create_task(_process_edit_draft(task_id, source_task, req.instruction, current_user))

    return DraftTaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        document_type=doc_type,
        message="Đang chỉnh sửa file Word đã xuất...",
    )


@router.get("/draft/status/{task_id}", response_model=DraftStatusResponse)
async def get_draft_status(task_id: str):
    """Kiểm tra trạng thái soạn thảo văn bản."""
    task = await db.get_draft_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task không tồn tại")

    return DraftStatusResponse(
        task_id=task["id"],
        status=task["status"],
        document_type=task.get("document_type", ""),
        progress_message=_public_ai_text(task.get("progress_message")),
        error_message=_public_ai_text(task.get("error_message")),
        output_ready=task["status"] == "completed" and bool(task.get("output_file")) and Path(task["output_file"]).exists(),
    )


@router.get("/draft/preview/{task_id}", response_class=HTMLResponse)
async def preview_draft(task_id: str, current_user: dict = Depends(get_current_user)):
    """Preview a generated Word document as HTML without downloading it."""
    task = await db.get_draft_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task không tồn tại")
    if task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
    if task["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File chưa sẵn sàng")

    output_file = task.get("output_file")
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File không tìm thấy")

    return HTMLResponse(render_docx_preview_html(output_file))


@router.get("/draft/download/{task_id}")
async def download_draft(task_id: str):
    """Download file Word văn bản đã soạn."""
    task = await db.get_draft_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task không tồn tại")

    if task["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Văn bản chưa sẵn sàng. Trạng thái: {task['status']}",
        )

    if not task.get("output_file") or not Path(task["output_file"]).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File không tìm thấy")

    doc_type = task.get("document_type", "vb")
    download_name = f"{doc_type}_{task_id[:8]}.docx"

    return FileResponse(
        path=task["output_file"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )


# ─── History Endpoints ───────────────────────────────────────────────

@router.get("/draft/history")
async def get_draft_history(current_user: dict = Depends(get_current_user)):
    """Get export history for the current user's drafting tasks."""
    tasks = await db.get_draft_tasks_by_user(current_user["id"])
    return [
        {
            "task_id": task["id"],
            "document_type": task.get("document_type", ""),
            "status": task.get("status", ""),
            "progress_message": _public_ai_text(task.get("progress_message")),
            "error_message": _public_ai_text(task.get("error_message")),
            "output_ready": task.get("status") == "completed" and bool(task.get("output_file")) and Path(task["output_file"]).exists(),
            "created_at": task.get("created_at", ""),
        }
        for task in tasks
    ]


@router.delete("/draft/history/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft_history_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a drafting history task and its output file."""
    task = await db.get_draft_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task không tồn tại")

    if task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")

    # Delete output file if exists
    try:
        if task.get("output_file"):
            fp = Path(task["output_file"])
            if fp.exists():
                fp.unlink()
    except Exception as e:
        logger.warning(f"Could not delete draft task output file: {e}")

    await db.delete_draft_task(task_id)


@router.delete("/draft/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft_task(task_id: str):
    """Delete a drafting task and its output file (legacy endpoint)."""
    task = await db.get_draft_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task không tồn tại")

    try:
        if task.get("output_file"):
            fp = Path(task["output_file"])
            if fp.exists():
                fp.unlink()
    except Exception as e:
        logger.warning(f"Could not delete draft task output file: {e}")

    await db.delete_draft_task(task_id)

# ─── Background Processing ───────────────────────────────────────────

async def _process_draft(task_id: str, notebook_id: str,
                         doc_type: DocumentType, input_data: dict,
                         repo_id: str = "", current_user: dict = None,
                         selected_document_ids: list[str] | None = None):
    """Background task to process a drafting request."""
    try:
        # Step 1: Ask AI engine
        await db.update_draft_task(
            task_id,
            status=TaskStatus.PROCESSING.value,
            progress_message="Đang phân tích tài liệu và soạn nội dung...",
        )

        draft_data = await drafting_service.draft_document(
            notebook_id, doc_type, input_data, repo_id=repo_id,
            current_user=current_user,
            selected_document_ids=selected_document_ids,
        )

        drafting_service.validate_draft_quality(doc_type, draft_data, input_data)

        # Step 2: Export to Word
        await db.update_draft_task(
            task_id,
            status=TaskStatus.EXPORTING_WORD.value,
            progress_message="Đang xuất file Word...",
        )

        output_filename = f"{doc_type.value}_{task_id[:8]}.docx"
        output_path = str(Path(settings.output_dir) / output_filename)

        word_exporter.export_administrative_document(doc_type, draft_data, output_path)
        saved_draft_data = _strip_internal_fields(draft_data)

        await db.update_draft_task(
            task_id,
            status=TaskStatus.COMPLETED.value,
            progress_message="Hoàn thành! File văn bản đã sẵn sàng để tải về.",
            output_file=output_path,
            input_data=_json_dumps(input_data),
            draft_data=_json_dumps(saved_draft_data),
        )
        logger.info(f"Draft task {task_id} completed → {output_path}")

    except Exception as e:
        await db.update_draft_task(
            task_id,
            status=TaskStatus.ERROR.value,
            error_message=str(e),
            progress_message="Lỗi hệ thống. Vui lòng thử lại sau.",
        )
        logger.error(f"Draft task {task_id} failed: {e}", exc_info=True)


async def _process_edit_draft(task_id: str, source_task: dict, instruction: str, current_user: dict):
    """Background task to edit an existing exported Word file."""
    try:
        await db.update_draft_task(
            task_id,
            status=TaskStatus.PROCESSING.value,
            progress_message="AI đang chỉnh sửa toàn bộ nội dung văn bản...",
        )

        source_path = Path(source_task["output_file"])
        output_filename = f"{source_task.get('document_type', 'van_ban')}_edited_{task_id[:8]}.docx"
        output_path = str(Path(settings.output_dir) / output_filename)
        doc_type = DocumentType(source_task.get("document_type", ""))
        input_data = _json_loads_dict(source_task.get("input_data"))
        draft_data = _json_loads_dict(source_task.get("draft_data"))

        if draft_data:
            repo = await db.get_repository_by_id(source_task.get("repo_id", ""))
            notebook_id = repo.get("notebook_id", "") if repo else ""

            edited_draft_data, edited_input_data = await drafting_service.edit_draft_data(
                notebook_id=notebook_id,
                doc_type=doc_type,
                draft_data=draft_data,
                input_data=input_data,
                instruction=instruction,
                current_user=current_user,
            )

            await db.update_draft_task(
                task_id,
                status=TaskStatus.EXPORTING_WORD.value,
                progress_message="Đang xuất lại file Word...",
            )
            export_data = {**edited_draft_data, **edited_input_data}
            export_data["document_type"] = doc_type.value
            word_exporter.export_administrative_document(doc_type, export_data, output_path)
            changed_message = "toàn bộ nội dung"
            saved_input_data = edited_input_data
            saved_draft_data = export_data
        else:
            # Backward compatibility for old tasks created before draft_data was saved.
            changed = await drafting_service.edit_exported_docx(
                str(source_path),
                instruction,
                output_path,
            )
            changed_message = f"{changed} phần"
            saved_input_data = input_data
            saved_draft_data = {}

        await db.update_draft_task(
            task_id,
            status=TaskStatus.COMPLETED.value,
            progress_message=f"Hoàn thành chỉnh sửa {changed_message} và xuất lại file Word.",
            output_file=output_path,
            input_data=_json_dumps(saved_input_data),
            draft_data=_json_dumps(saved_draft_data),
        )
        logger.info("Draft edit task %s completed → %s", task_id, output_path)

    except Exception as e:
        await db.update_draft_task(
            task_id,
            status=TaskStatus.ERROR.value,
            error_message=str(e),
            progress_message="Lỗi khi chỉnh sửa file Word.",
        )
        logger.error("Draft edit task %s failed: %s", task_id, e, exc_info=True)


def _json_dumps(data: dict) -> str:
    return json.dumps(data or {}, ensure_ascii=False)


def _json_loads_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _strip_internal_fields(data: dict) -> dict:
    return {
        key: value
        for key, value in (data or {}).items()
        if not str(key).startswith("_")
    }
