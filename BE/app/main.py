"""Backend API for auth, repositories, documents, chat, and administration."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.models import HealthResponse

# Import routers
from app.routers import (
    admin_router,
    auth_router,
    chat_router,
    document_dataset_router,
    document_router,
    internal_retrieval_router,
    repository_router,
    revision_router,
)

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sttnb")

# ─── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(
    title="SmartGov Backend",
    description=(
        "API đa chức năng: Kho dữ liệu + AI, Chat Q&A streaming, "
        "Auth/RBAC và quản trị hệ thống"
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
app.include_router(revision_router.router)
app.include_router(document_dataset_router.router)
app.include_router(internal_retrieval_router.router)


# ─── System Endpoints ────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Public liveness endpoint."""
    return HealthResponse(
        status="ok",
        service="SmartGov AI",
        version="2.0.0",
        ai_service="internal",
    )


# ─── Startup Event ───────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Initialize on server startup."""
    logger.info("=" * 60)
    logger.info("  SmartGov AI v2.0")
    logger.info("  Kho dữ liệu | Chat | Quản trị")
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


# ─── Run directly ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
