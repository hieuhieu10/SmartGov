"""
STTNB — Speech To Text NoteBook (v2.0)
Backend API đa chức năng:
  1. Chuyển file ghi âm thành biên bản họp (Word) qua NotebookLM
  2. Quản lý kho dữ liệu + upload tài liệu lên NotebookLM
  3. Chat Q&A với NotebookLM (simulated streaming)
  4. Soạn văn bản hành chính theo NĐ 30/2020/NĐ-CP

Endpoints:
  Auth:
    POST /api/auth/register   — Đăng ký
    POST /api/auth/login      — Đăng nhập
    GET  /api/auth/me         — Thông tin user

  Repository:
    POST   /api/repositories               — Tạo kho
    GET    /api/repositories               — Danh sách kho
    GET    /api/repositories/{id}          — Chi tiết kho
    PUT    /api/repositories/{id}          — Cập nhật kho
    DELETE /api/repositories/{id}          — Xóa kho

  Document:
    POST   /api/repositories/{id}/documents     — Upload tài liệu
    GET    /api/repositories/{id}/documents     — Danh sách tài liệu
    DELETE /api/repositories/{id}/documents/{d} — Xóa tài liệu

  Chat:
    POST   /api/repositories/{id}/chat          — Chat Q&A (SSE streaming)
    GET    /api/repositories/{id}/chat/history   — Lịch sử chat
    DELETE /api/repositories/{id}/chat/history   — Xóa lịch sử

  Drafting:
    GET    /api/draft/types                     — Danh sách loại văn bản
    POST   /api/repositories/{id}/draft         — Soạn văn bản
    GET    /api/draft/status/{task_id}          — Trạng thái soạn thảo
    GET    /api/draft/download/{task_id}        — Download Word

  Legacy:
    POST /api/upload-audio     — Upload file ghi âm
    GET  /api/status/{task_id} — Kiểm tra trạng thái
    GET  /api/download/{task_id} — Download biên bản
    GET  /api/health           — Health check
    GET  /api/tasks            — Danh sách tasks (debug)
"""

import asyncio
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.models import (
    HealthResponse,
    MeetingMinutes,
)
from app.services.ai_client import ai_client
from app.services.word_exporter import word_exporter

# Import routers
from app.routers import auth_router, repository_router, document_router, chat_router, drafting_router, audio_router, template_router, admin_router, document_dataset_router, revision_router
from app.database import update_audio_task

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sttnb")

# ─── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(
    title="STTNB — Speech To Text NoteBook",
    description=(
        "API đa chức năng: Ghi âm → Biên bản họp, "
        "Kho dữ liệu + AI, Chat Q&A streaming, "
        "Soạn văn bản hành chính theo NĐ 30/2020/NĐ-CP"
    ),
    version="2.0.0",
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Include Routers ─────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(repository_router.router)
app.include_router(document_router.router)
app.include_router(chat_router.router)
app.include_router(drafting_router.router)
app.include_router(audio_router.router)
app.include_router(template_router.router)
app.include_router(document_dataset_router.router)
app.include_router(revision_router.router)

# ─── Sequential Processing Queue ─────────────────────────────────────
# Ensures only ONE audio task is processed at a time (NotebookLM cannot
# handle concurrent sessions reliably).
processing_queue: asyncio.Queue = asyncio.Queue()


# ─── Background Processing ───────────────────────────────────────────

async def process_audio_task(task_id: str, audio_path: str):
    """Background task: process audio through NotebookLM pipeline."""

    async def update_status(message: str):
        await update_audio_task(task_id, progress_message=message)

    try:
        # Step 1: Upload to NotebookLM & get meeting minutes
        await update_audio_task(task_id, status="uploading", progress_message="Đang kết nối hệ thống phân tích âm thanh...")

        minutes: MeetingMinutes = await ai_client.process_audio(
            audio_path, on_status=update_status
        )

        # Step 2: Export to Word
        await update_audio_task(task_id, status="exporting_word", progress_message="Đang xuất file Word biên bản họp...")

        output_filename = f"bien_ban_{task_id[:8]}.docx"
        output_path = str(Path(settings.output_dir) / output_filename)
        word_exporter.export(minutes, output_path)

        await update_audio_task(
            task_id, 
            status="completed", 
            progress_message="Hoàn thành! File biên bản đã sẵn sàng để tải về.",
            output_file=output_path
        )

        logger.info(f"Task {task_id} completed successfully → {output_path}")

    except Exception as e:
        await update_audio_task(
            task_id, 
            status="error", 
            error_message=str(e), 
            progress_message="Lỗi hệ thống. Vui lòng thử lại sau."
        )
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)

    finally:
        # Clean up uploaded audio file
        try:
            if Path(audio_path).exists():
                Path(audio_path).unlink()
                logger.info(f"Cleaned up temp audio: {audio_path}")
        except Exception as cleanup_err:
            logger.warning(f"Could not clean up {audio_path}: {cleanup_err}")


# ─── System Endpoints ────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint — skips NotebookLM auth check to avoid interrupting long-running prompts."""
    return HealthResponse(
        status="ok",
        service="STTNB - Speech To Text NoteBook",
        version="2.0.0",
        notebooklm_auth="ok",
    )


# -- Removed legacy /api/tasks logic since it's now user-specific in audio_router --


# ─── Queue Worker ────────────────────────────────────────────────────

async def queue_worker():
    """Background worker that processes audio tasks sequentially."""
    logger.info("Queue worker started — processing tasks one at a time")
    while True:
        task_id, audio_path = await processing_queue.get()
        logger.info(f"Queue worker picked up task {task_id} (remaining: {processing_queue.qsize()})")
        try:
            await process_audio_task(task_id, audio_path)
        except Exception as e:
            logger.error(f"Queue worker: unhandled error for task {task_id}: {e}")
        finally:
            processing_queue.task_done()


# ─── Startup Event ───────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Initialize on server startup."""
    logger.info("=" * 60)
    logger.info("  STTNB — Speech To Text NoteBook v2.0")
    logger.info("  Ghi âm → Biên bản | Kho dữ liệu | Chat | Soạn VB")
    logger.info("=" * 60)
    logger.info(f"  Upload dir:    {settings.upload_dir}")
    logger.info(f"  Output dir:    {settings.output_dir}")
    logger.info(f"  Repo files:    {settings.repo_files_dir}")
    logger.info("  Database:      PostgreSQL")
    logger.info(f"  Max upload:    {settings.max_upload_mb} MB")
    logger.info(f"  Max doc upload:{settings.max_doc_upload_mb} MB")
    logger.info(f"  Max user docs: {settings.max_user_upload_gb:g} GB")
    engine_label = "Server 2" if settings.is_self_hosted else "Server 1"
    logger.info(f"  Máy chủ xử lý: {engine_label}")
    logger.info(f"  AI service:    {settings.ai_service_url}")
    logger.info("=" * 60)

    # Initialize database
    await init_db()

    # Start the sequential queue worker
    asyncio.create_task(queue_worker())


# ─── Run directly ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
