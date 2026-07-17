import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.database import (
    create_audio_task,
    get_audio_task_by_id,
    get_audio_tasks_by_user,
    delete_audio_task
)
from app.models import AudioTaskResponse, UploadResponse, TaskStatus
from app.routers.auth_router import get_current_user

router = APIRouter(prefix="/api/audio", tags=["Audio to Minutes"])
logger = logging.getLogger(__name__)


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


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a meeting recording audio file for processing.
    Requires authentication.
    """
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không được hỗ trợ: {file_ext}. Hỗ trợ: {', '.join(settings.allowed_extensions)}"
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File quá lớn. Giới hạn: {settings.max_upload_mb}MB"
        )

    task_id = str(uuid.uuid4())
    safe_filename = f"{task_id}{file_ext}"
    upload_path = str(Path(settings.upload_dir) / safe_filename)

    with open(upload_path, "wb") as f:
        f.write(content)

    logger.info(f"User {current_user['username']} uploaded audio: {file.filename} -> task {task_id}")

    # Create DB record
    await create_audio_task(task_id, current_user["id"], file.filename)

    # Queue for processing (Import locally to avoid circular dependency)
    from app.main import processing_queue
    await processing_queue.put((task_id, upload_path))

    return UploadResponse(
        task_id=task_id,
        status="pending",
        message="File đã được upload. Đang bắt đầu xử lý..."
    )

@router.get("/tasks", response_model=list[AudioTaskResponse])
async def list_audio_tasks(current_user: dict = Depends(get_current_user)):
    """List all audio processing tasks of the current user."""
    tasks = await get_audio_tasks_by_user(current_user["id"])
    
    result = []
    for t in tasks:
        # Determine output readiness based on status and output_file presence
        output_ready = t["status"] == "completed" and bool(t["output_file"])
        result.append(AudioTaskResponse(
            id=t["id"],
            filename=t["filename"],
            status=t["status"],
            progress_message=_public_ai_text(t["progress_message"]),
            error_message=_public_ai_text(t["error_message"]),
            output_file=t["output_file"],
            created_at=str(t["created_at"]),
            updated_at=str(t["updated_at"]),
            output_ready=output_ready
        ))
    return result

@router.get("/status/{task_id}", response_model=AudioTaskResponse)
async def get_audio_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """Check the status of an audio task."""
    t = await get_audio_task_by_id(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập task này")

    output_ready = t["status"] == "completed" and bool(t["output_file"])
    return AudioTaskResponse(
        id=t["id"],
        filename=t["filename"],
        status=t["status"],
        progress_message=_public_ai_text(t["progress_message"]),
        error_message=_public_ai_text(t["error_message"]),
        output_file=t["output_file"],
        created_at=str(t["created_at"]),
        updated_at=str(t["updated_at"]),
        output_ready=output_ready
    )

@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an audio processing task and its output file."""
    t = await get_audio_task_by_id(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập task này")

    # Optional: Delete output file if it exists
    try:
        if t["output_file"]:
            fp = Path(t["output_file"])
            if fp.exists():
                fp.unlink()
    except Exception as e:
        logger.warning(f"Could not delete audio task output file: {e}")

    await delete_audio_task(task_id)

@router.get("/download/{task_id}")
async def download_audio_minutes(task_id: str):
    """Download the generated Word meeting minutes."""
    t = await get_audio_task_by_id(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task không tồn tại")

    if t["status"] != "completed":
        raise HTTPException(status_code=400, detail="File chưa xử lý xong.")

    if not t["output_file"] or not Path(t["output_file"]).exists():
        raise HTTPException(status_code=404, detail="File kết quả không tìm thấy, có thể đã bị xóa")

    clean_name = Path(t["filename"]).stem
    download_name = f"Bien_ban_{clean_name}.docx"

    return FileResponse(
        path=t["output_file"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )
