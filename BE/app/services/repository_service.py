"""Repository lifecycle backed by local files, PostgreSQL and the internal AI service."""

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from app import database as db
from app.config import settings

logger = logging.getLogger(__name__)


class RepositoryService:
    async def create_repository(self, user_id: str, name: str, description: str = "", category_id: str | None = None, current_user: dict | None = None) -> dict:
        repo = await db.create_repository(user_id=user_id, name=name, description=description, category_id=category_id)
        (Path(settings.repo_files_dir) / repo["id"]).mkdir(parents=True, exist_ok=True)
        return repo

    async def verify_ownership(self, repo_id: str, user_id: str) -> dict:
        repo = await db.get_repository_by_id(repo_id)
        if not repo:
            raise ValueError("Kho dữ liệu không tồn tại")
        if repo["user_id"] != user_id:
            raise PermissionError("Bạn không có quyền truy cập kho dữ liệu này")
        return repo

    async def get_repository_with_docs(self, repo_id: str, user_id: str, current_user: dict | None = None) -> dict:
        repo = await self.verify_ownership(repo_id, user_id)
        repo["document_count"] = len(await db.get_documents_by_repository(repo_id))
        return repo

    async def delete_repository(self, repo_id: str, user_id: str, current_user: dict | None = None) -> None:
        await self.verify_ownership(repo_id, user_id)
        repo_dir = Path(settings.repo_files_dir) / repo_id
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        await db.delete_repository(repo_id)

    async def upload_document(self, repo_id: str, user_id: str, filename: str, content: bytes, file_type: str = "", folder_key: str = "draft", current_user: dict | None = None) -> dict:
        await self.verify_ownership(repo_id, user_id)
        doc_id = str(uuid.uuid4())
        repo_dir = Path(settings.repo_files_dir) / repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        stored_path = repo_dir / f"{doc_id}_{Path(filename).name}"
        stored_path.write_bytes(content)
        return await db.create_document(repository_id=repo_id, filename=filename, stored_path=str(stored_path), file_size=len(content), file_type=file_type, folder_key=folder_key, doc_id=doc_id, processing_status="processing", progress_message="Đang chuyển đổi tài liệu")

    async def replace_document_file(self, repo_id: str, doc_id: str, user_id: str, filename: str, content: bytes, file_type: str = "", current_user: dict | None = None) -> dict:
        await self.verify_ownership(repo_id, user_id)
        doc = await db.get_document_by_id(doc_id)
        if not doc or doc["repository_id"] != repo_id:
            raise ValueError("Tài liệu không tồn tại trong kho này")
        path = Path(settings.repo_files_dir) / repo_id / f"{doc_id}_{Path(filename).name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        old_path = Path(doc["stored_path"])
        if old_path != path and old_path.exists():
            old_path.unlink()
        updated = await db.update_document_file(doc_id, filename, str(path), len(content), file_type)
        if not updated:
            raise ValueError("Tài liệu không tồn tại")
        return updated

    async def process_document(self, repo_id: str, doc_id: str, user_id: str, current_user: dict | None = None) -> None:
        doc = await db.get_document_by_id(doc_id)
        if not doc or doc["repository_id"] != repo_id:
            return
        await self.verify_ownership(repo_id, user_id)
        from app.services.ai_client import ai_client, describe_conversion
        try:
            markdown, vector_count = await ai_client.convert_and_store(doc_id, doc["stored_path"])
            note, error = describe_conversion(markdown, vector_count)
            await db.update_document_processing(doc_id, status="completed", progress_message=f"Đã xử lý xong ({note})", error_message=error, processed_at=datetime.now().isoformat())
        except Exception as exc:
            logger.exception("Document processing failed: %s", doc_id)
            await db.update_document_processing(doc_id, status="failed", progress_message="Xử lý tài liệu thất bại", error_message=str(exc))

    async def delete_document(self, repo_id: str, doc_id: str, user_id: str, current_user: dict | None = None) -> None:
        await self.verify_ownership(repo_id, user_id)
        doc = await db.get_document_by_id(doc_id)
        if not doc or doc["repository_id"] != repo_id:
            raise ValueError("Tài liệu không tồn tại trong kho này")
        path = Path(doc["stored_path"])
        if path.exists():
            path.unlink()
        await db.delete_document(doc_id)


repository_service = RepositoryService()
