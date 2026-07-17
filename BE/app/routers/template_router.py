"""
Template Router — Custom document template management.

v5.1 Flow:
    POST   /api/templates/upload              — Upload file (docx/pdf/img) & extract headings
    GET    /api/templates                     — List user's templates
    GET    /api/templates/{id}                — Get template details (with headings)
    PUT    /api/templates/{id}                — Rename/update template
    DELETE /api/templates/{id}                — Delete a template
    POST   /api/templates/{id}/generate       — Generate NĐ 30 document from template + repo
    GET    /api/templates/{id}/history        — Get generation history for a template
    GET    /api/templates/generate/status/{tid} — Check generation status
    GET    /api/templates/download/{tid}       — Download generated file
"""

import asyncio
import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.auth import get_current_user, is_user_self_hosted
from app.config import settings
from app import database as db
from app.models import (
    TemplateHeading, TemplateResponse,
    TemplateGenerateRequest, TemplateGenerateResponse,
)
from app.services.repository_service import repository_service
from app.services.template_service import template_service
from app.services.docx_preview import render_docx_preview_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["Custom Templates"])


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


# Allowed file extensions for template upload
ALLOWED_TEMPLATE_EXTENSIONS = {".docx", ".pdf", ".jpg", ".jpeg", ".png"}


# ─── Request Models ──────────────────────────────────────────────────

class TemplateUpdateRequest(BaseModel):
    """Request to rename/update a template."""
    name: str = Field(None, min_length=1, max_length=200)
    description: str = Field(None, max_length=2000)


# ─── Helpers ─────────────────────────────────────────────────────────

def _template_to_response(t: dict) -> TemplateResponse:
    """Convert a DB template row to a TemplateResponse."""
    headings = []
    try:
        raw = t.get("placeholders") or []
        if isinstance(raw, str):
            raw = json.loads(raw)
        headings = [TemplateHeading(**h) for h in raw]
    except Exception:
        pass

    return TemplateResponse(
        id=t["id"],
        name=t["name"],
        description=t.get("description", ""),
        doc_type=t.get("doc_type", ""),
        doc_type_label=_get_doc_type_label(t.get("doc_type", "")),
        headings=headings,
        status=t.get("status", "ready"),
        error_message=_public_ai_text(t.get("error_message")),
        created_at=t.get("created_at", ""),
        updated_at=t.get("updated_at", ""),
    )


def _get_doc_type_label(doc_type: str) -> str:
    """Get Vietnamese label for doc_type."""
    from app.services.template_service import DOC_TYPE_MAP
    return DOC_TYPE_MAP.get(doc_type, {}).get("label", "")


# ─── Upload & Extract Headings ───────────────────────────────────────

@router.post("/upload", response_model=TemplateResponse)
async def upload_template(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a file (docx/pdf/img) and extract main headings using AI."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên file không hợp lệ.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_TEMPLATE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ hỗ trợ file {', '.join(ALLOWED_TEMPLATE_EXTENSIONS)}.",
        )

    template_id = str(uuid.uuid4())
    user_dir = Path(settings.user_templates_dir) / current_user["id"]
    user_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    source_path = str(user_dir / f"{template_id}_source{ext}")
    with open(source_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info(f"Template uploaded: {file.filename} → {source_path}")

    # Create DB record
    template_name = Path(file.filename).stem
    t = await db.create_template(
        template_id, current_user["id"], template_name,
        source_path, source_file=source_path,
    )

    # Extract headings in background
    engine = "self_hosted" if is_user_self_hosted(current_user) else "notebooklm"
    asyncio.create_task(_extract_headings_bg(template_id, source_path, engine))

    return _template_to_response(t)


async def _extract_headings_bg(template_id: str, source_path: str, engine: str):
    """Background task: extract headings from uploaded file using the configured server."""
    try:
        result = await template_service.extract_headings(source_path, engine=engine)

        headings_json = result.get("headings", [])

        await db.update_template(
            template_id,
            description=result.get("trich_yeu", ""),
            doc_type=result.get("doc_type", "khac"),
            placeholders=headings_json,
            status="ready",
        )
        logger.info(
            f"Template {template_id} headings extracted: "
            f"{len(result.get('headings', []))} headings, "
            f"doc_type={result.get('doc_type')}"
        )

    except ValueError as e:
        await db.update_template(
            template_id,
            status="error",
            error_message=str(e),
        )
        logger.warning(f"Template {template_id} extraction issue: {e}")

    except Exception as e:
        await db.update_template(
            template_id,
            status="error",
            error_message="Lỗi hệ thống khi trích xuất đầu mục. Vui lòng thử lại.",
        )
        logger.error(f"Template {template_id} extraction failed: {e}", exc_info=True)


# ─── List / Get / Update / Delete ────────────────────────────────────

@router.get("", response_model=list[TemplateResponse])
async def list_templates(current_user: dict = Depends(get_current_user)):
    """List all templates for the current user."""
    templates = await db.get_templates_by_user(current_user["id"])
    return [_template_to_response(t) for t in templates]


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific template's details."""
    t = await db.get_template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Mẫu không tồn tại")
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    return _template_to_response(t)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    req: TemplateUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Rename or update a template's metadata."""
    t = await db.get_template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Mẫu không tồn tại")
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description

    if updates:
        t = await db.update_template(template_id, **updates)

    return _template_to_response(t)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a template and its file."""
    t = await db.get_template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Mẫu không tồn tại")
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    # Delete files
    for file_col in ["template_file", "source_file"]:
        try:
            fp = Path(t.get(file_col, ""))
            if fp.exists():
                fp.unlink()
        except Exception as e:
            logger.warning(f"Could not delete {file_col}: {e}")

    await db.delete_template(template_id)


# ─── Generation History ──────────────────────────────────────────────

@router.get("/{template_id}/history")
async def get_template_history(template_id: str, current_user: dict = Depends(get_current_user)):
    """Get generation history for a template."""
    t = await db.get_template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Mẫu không tồn tại")
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    tasks = await db.get_template_tasks_by_template(template_id)
    return [
        {
            "task_id": task["id"],
            "status": task["status"],
            "progress_message": _public_ai_text(task.get("progress_message")),
            "error_message": _public_ai_text(task.get("error_message")),
            "output_ready": task["status"] == "completed" and bool(task.get("output_file")) and Path(task["output_file"]).exists(),
            "created_at": task.get("created_at", ""),
        }
        for task in tasks
    ]


@router.delete("/history/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_task(task_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a template generation history task."""
    task = await db.get_template_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    if task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Optional: Delete Output File if exists
    try:
        if task.get("output_file"):
            fp = Path(task["output_file"])
            if fp.exists():
                fp.unlink()
    except Exception as e:
        logger.warning(f"Could not delete task output file: {e}")

    await db.delete_template_task(task_id)

# ─── Generate Document from Template ─────────────────────────────────

@router.post("/{template_id}/generate", response_model=TemplateGenerateResponse)
async def generate_from_template(
    template_id: str,
    req: TemplateGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a NĐ 30 formatted document from template headings + repo data."""
    t = await db.get_template_by_id(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Mẫu không tồn tại")
    if t["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    if t["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Mẫu chưa sẵn sàng. Trạng thái: {t['status']}. {_public_ai_text(t.get('error_message'))}",
        )

    # Resolve repo_id → notebook_id (required)
    if not req.repo_id:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng chọn kho dữ liệu để sinh nội dung.",
        )

    repo = await db.get_repository_by_id(req.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Kho dữ liệu không tồn tại")
    if repo["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập kho dữ liệu này")
    if not is_user_self_hosted(current_user):
        repo = await repository_service.ensure_notebooklm_session_current(
            repo,
            repo["user_id"],
        )

    notebook_id = repo.get("notebook_id", "")
    if not is_user_self_hosted(current_user) and not notebook_id:
        raise HTTPException(
            status_code=400,
            detail="Kho dữ liệu chưa sẵn sàng. Vui lòng thử lại sau.",
        )

    task_id = str(uuid.uuid4())

    # Store task in DB (persistent)
    await db.create_template_task(task_id, template_id, current_user["id"])

    # Parse headings
    try:
        headings = t.get("placeholders") or []
        if isinstance(headings, str):
            headings = json.loads(headings)
    except Exception:
        headings = []

    asyncio.create_task(
        _generate_document_bg(
            task_id, t, headings, req.input_data,
            notebook_id, req.repo_id,
            selected_document_ids=req.selected_document_ids,
            current_user=current_user,
        )
    )

    return TemplateGenerateResponse(
        task_id=task_id,
        status="processing",
        message="Đang sinh nội dung văn bản từ kho dữ liệu...",
    )


async def _generate_document_bg(
    task_id: str, template: dict,
    headings: list[dict], user_input: dict,
    notebook_id: str, repo_id: str = "",
    selected_document_ids: list[str] | None = None,
    current_user: dict = None,
):
    """Background task: generate heading content + build NĐ 30 document."""
    from app.services.template_service import DOC_TYPE_MAP

    try:
        doc_type = template.get("doc_type", "khac")
        doc_info = DOC_TYPE_MAP.get(doc_type, DOC_TYPE_MAP["khac"])
        trich_yeu = template.get("description", "")

        # Step 1: Generate content for each heading via AI engine
        await db.update_template_task(
            task_id,
            progress_message="AI đang sinh nội dung cho từng đầu mục...",
        )

        headings_data = await template_service.generate_from_headings(
            headings=headings,
            notebook_id=notebook_id,
            doc_type_label=doc_info["label"],
            trich_yeu=trich_yeu,
            user_input=user_input,
            repo_id=repo_id,
            selected_document_ids=selected_document_ids or [],
            engine="self_hosted" if is_user_self_hosted(current_user) else "notebooklm",
        )

        # Step 2: Build NĐ 30 document
        await db.update_template_task(
            task_id,
            progress_message="Đang tạo file Word chuẩn NĐ 30...",
        )

        output_filename = f"vb_{doc_type}_{task_id[:8]}.docx"
        output_path = str(Path(settings.output_dir) / output_filename)

        # Merge trich_yeu from template into user_input for build
        build_input = dict(user_input)
        if "trich_yeu" not in build_input or not build_input["trich_yeu"]:
            build_input["trich_yeu"] = trich_yeu

        template_service.build_nd30_document(
            doc_type=doc_type,
            headings=headings,
            headings_data=headings_data,
            user_input=build_input,
            output_path=output_path,
        )

        await db.update_template_task(
            task_id,
            status="completed",
            progress_message="Hoàn thành! File văn bản đã sẵn sàng.",
            output_file=output_path,
        )
        logger.info(f"Template generation {task_id} completed → {output_path}")

    except Exception as e:
        await db.update_template_task(
            task_id,
            status="error",
            error_message=str(e),
            progress_message="Lỗi hệ thống. Vui lòng thử lại sau.",
        )
        logger.error(f"Template generation {task_id} failed: {e}", exc_info=True)


@router.get("/generate/status/{task_id}")
async def get_generation_status(task_id: str):
    """Check status of a template generation task."""
    task = await db.get_template_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress_message": _public_ai_text(task.get("progress_message")),
        "error_message": _public_ai_text(task.get("error_message")),
        "output_ready": task["status"] == "completed" and bool(task.get("output_file")) and Path(task["output_file"]).exists(),
    }


@router.get("/preview/{task_id}", response_class=HTMLResponse)
async def preview_generated_document(task_id: str, current_user: dict = Depends(get_current_user)):
    """Preview a generated template document as HTML without downloading it."""
    task = await db.get_template_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    if task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="File chưa sẵn sàng")

    output_file = task.get("output_file")
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="File không tìm thấy")

    return HTMLResponse(render_docx_preview_html(output_file))


@router.get("/download/{task_id}")
async def download_generated_document(task_id: str):
    """Download a generated document."""
    task = await db.get_template_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="File chưa sẵn sàng")

    output_file = task.get("output_file")
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="File không tìm thấy")

    download_name = Path(output_file).name
    return FileResponse(
        path=output_file,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )
