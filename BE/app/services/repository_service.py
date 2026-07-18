"""
STTNB Repository Service — Business logic for repository management.

Supports dual-engine architecture (per-user):
  - NotebookLM: Creates notebooks, uploads sources
  - Self-hosted: AI converts documents; BE stores Markdown in PostgreSQL

Engine is resolved PER-USER via auth.is_user_self_hosted(user).
"""

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app import database as db
from app.auth import is_user_self_hosted, get_user_engine

logger = logging.getLogger(__name__)


class RepositoryService:
    """Business logic for managing data repositories."""

    @staticmethod
    def _editor_name(current_user: dict | None) -> str:
        if not current_user:
            return "Người dùng"
        return current_user.get("full_name") or current_user.get("username") or "Người dùng"

    async def create_document_snapshot(
        self,
        doc: dict,
        content: bytes,
        current_user: dict | None,
        change_type: str,
    ) -> dict:
        """Persist an immutable file copy and its version metadata."""
        versions_dir = (
            Path(settings.repo_files_dir)
            / doc["repository_id"]
            / ".versions"
            / doc["id"]
        )
        versions_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(doc["filename"]).suffix or ".bin"
        snapshot_path = versions_dir / f"{uuid.uuid4()}{suffix}"
        snapshot_path.write_bytes(content)
        try:
            return await db.create_document_version(
                document_id=doc["id"],
                filename=doc["filename"],
                stored_path=str(snapshot_path),
                file_size=len(content),
                file_type=doc.get("file_type") or "",
                changed_by=current_user.get("id") if current_user else None,
                changed_by_name=self._editor_name(current_user),
                change_type=change_type,
            )
        except Exception:
            snapshot_path.unlink(missing_ok=True)
            raise

    async def ensure_document_history(
        self,
        doc: dict,
        current_user: dict | None,
    ) -> list[dict]:
        versions = await db.get_document_versions(doc["id"])
        if versions:
            return versions
        source_path = Path(doc.get("stored_path") or "")
        if not source_path.exists():
            raise ValueError("Không tìm thấy file tài liệu để tạo lịch sử")
        await self.create_document_snapshot(
            doc,
            source_path.read_bytes(),
            current_user,
            "created",
        )
        return await db.get_document_versions(doc["id"])

    def _looks_like_capacity_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return any(token in message for token in (
            "limit", "quota", "maximum", "too many", "450", "notebook limit"
        ))

    async def ensure_notebooklm_capacity(
        self,
        session_fingerprint: str = "",
        exclude_repo_id: str | None = None,
    ) -> None:
        """Evict least recently used Server 1 repository notebooks when capacity is full."""
        limit = max(int(settings.notebooklm_max_notebooks or 450), 1)
        active_count = await db.count_active_notebooklm_repositories(session_fingerprint)
        if active_count < limit:
            return

        from app.services.ai_client import ai_client as notebooklm_service

        while active_count >= limit:
            candidate = await db.get_notebooklm_eviction_candidate(
                session_fingerprint=session_fingerprint,
                exclude_repo_id=exclude_repo_id,
            )
            if not candidate:
                raise RuntimeError(
                    "Server 1 đã đầy nhưng không tìm thấy kho cũ phù hợp để xoay vòng"
                )

            notebook_id = candidate.get("notebook_id")
            repo_id = candidate["id"]
            try:
                await notebooklm_service.delete_notebook(notebook_id)
            except Exception as e:
                logger.warning(
                    "Could not evict Server 1 notebook %s for repo %s: %s",
                    notebook_id, repo_id, e,
                )
                raise RuntimeError("Không thể xóa sổ tay cũ trên Server 1 để tạo sổ tay mới") from e

            await db.set_repository_notebooklm_state(repo_id, None, None)
            await db.clear_repository_document_source_ids(repo_id)
            logger.info(
                "Evicted Server 1 notebook %s for least recently used repo %s",
                notebook_id, repo_id,
            )
            active_count -= 1

    async def create_notebook_with_capacity(
        self,
        name: str,
        exclude_repo_id: str | None = None,
    ) -> tuple[str, str]:
        """Create a Server 1 notebook, rotating out an old repository notebook if needed."""
        from app.services.ai_client import ai_client as notebooklm_service

        session_fingerprint = await notebooklm_service.get_session_fingerprint()
        await self.ensure_notebooklm_capacity(session_fingerprint, exclude_repo_id)
        try:
            notebook_id = await notebooklm_service.create_notebook(name)
            return notebook_id, session_fingerprint
        except Exception as e:
            if not self._looks_like_capacity_error(e):
                raise
            logger.warning("Server 1 reported capacity while creating notebook; evicting and retrying: %s", e)
            await self.ensure_notebooklm_capacity(session_fingerprint, exclude_repo_id)
            notebook_id = await notebooklm_service.create_notebook(name)
            return notebook_id, session_fingerprint

    async def create_repository(self, user_id: str, name: str,
                                description: str = "",
                                category_id: str = None,
                                current_user: dict = None) -> dict:
        """
        Create a new repository:
        1. Create AI backend (NotebookLM notebook or just DB record)
        2. Save to database
        3. Create file storage directory
        """
        # Resolve AI engine for this user
        use_self_hosted = is_user_self_hosted(current_user) if current_user else settings.is_self_hosted
        engine_name = get_user_engine(current_user) if current_user else settings.ai_engine

        # Create AI backend (notebook for NotebookLM, nothing needed for self-hosted)
        notebook_id = None
        notebooklm_session_fingerprint = None
        try:
            if not use_self_hosted:
                # NotebookLM: create notebook
                notebook_id, notebooklm_session_fingerprint = await self.create_notebook_with_capacity(
                    f"Kho: {name}"
                )
                logger.info(f"[NotebookLM] Created notebook: {notebook_id}")
        except Exception as e:
            logger.warning(
                "NotebookLM backend unavailable while creating repo; "
                "repo will remain usable via self-hosted fallback: %s",
                e,
            )

        # Save to database
        repo = await db.create_repository(
            user_id=user_id,
            name=name,
            description=description,
            notebook_id=notebook_id,
            notebooklm_session_fingerprint=notebooklm_session_fingerprint,
            category_id=category_id,
        )

        actual_repo_id = repo["id"]

        # Create file storage directory
        repo_dir = Path(settings.repo_files_dir) / actual_repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Repository created: {actual_repo_id} for user {user_id} "
                     f"(engine: {engine_name})")
        return repo

    async def ensure_self_hosted_ready(self, repo_id: str) -> dict:
        """
        Ensure all saved files in a repository have Markdown content.

        This is used both for normal NotebookLM uploads and for fallback when
        NotebookLM session/account is unavailable.
        """
        docs = await db.get_documents_by_repository(repo_id)
        converted = 0
        failed = 0

        from app.services.ai_client import ai_client as document_converter, describe_conversion

        for doc in docs:
            if doc.get("markdown_content"):
                continue

            stored_path = doc.get("stored_path") or ""
            if not stored_path or not Path(stored_path).exists():
                failed += 1
                await db.update_document_processing(
                    doc["id"],
                    status="failed",
                    progress_message="Không tìm thấy file nội bộ để chuyển sang Server 2",
                    error_message="Stored file is missing",
                )
                continue

            try:
                await db.update_document_processing(
                    doc["id"],
                    status="processing",
                    progress_message="Đang chuẩn bị dữ liệu cho Server 2",
                )
                markdown, vector_count = await document_converter.convert_and_store(doc["id"], stored_path)
                note, error_message = describe_conversion(markdown, vector_count)
                await db.update_document_processing(
                    doc["id"],
                    status="completed",
                    progress_message=f"Đã sẵn sàng trên Server 2 ({note})",
                    error_message=error_message,
                    processed_at=datetime.now().isoformat(),
                )
                converted += 1
            except Exception as e:
                failed += 1
                logger.error("Self-hosted preparation failed for doc %s: %s", doc["id"], e)
                await db.update_document_processing(
                    doc["id"],
                    status="failed",
                    progress_message="Không thể chuẩn bị dữ liệu cho Server 2",
                    error_message=str(e),
                )

        return {"converted": converted, "failed": failed, "total": len(docs)}

    async def rebuild_notebooklm_repository(self, repo_id: str, user_id: str) -> dict:
        """
        Recreate one repository in the currently authenticated NotebookLM account.

        Only the selected repository is migrated: a new notebook is created and
        all saved local files from this repo are uploaded to it.
        """
        repo = await self.verify_ownership(repo_id, user_id)

        from app.services.ai_client import ai_client as notebooklm_service

        new_notebook_id, session_fingerprint = await self.create_notebook_with_capacity(
            f"Kho: {repo['name']}",
            exclude_repo_id=repo_id,
        )
        docs = await db.get_documents_by_repository(repo_id)
        uploaded = 0
        failed = 0

        try:
            for doc in docs:
                stored_path = doc.get("stored_path") or ""
                if not stored_path or not Path(stored_path).exists():
                    failed += 1
                    await db.update_document_processing(
                        doc["id"],
                        status="failed",
                        progress_message="Không tìm thấy file nội bộ để chuyển sang Server 1",
                        error_message="Stored file is missing",
                    )
                    continue

                try:
                    await db.update_document_processing(
                        doc["id"],
                        status="processing",
                        progress_message="Đang chuyển tài liệu sang Server 1",
                    )
                    source_id = await notebooklm_service.upload_source(new_notebook_id, stored_path)
                    await db.update_document_source_id(doc["id"], source_id)
                    await db.update_document_processing(
                        doc["id"],
                        status="completed",
                        progress_message="Đã chuyển tài liệu sang Server 1",
                        error_message="",
                        processed_at=datetime.now().isoformat(),
                    )
                    uploaded += 1
                except Exception as e:
                    failed += 1
                    logger.error("NotebookLM rebuild upload failed for doc %s: %s", doc["id"], e)
                    await db.update_document_processing(
                        doc["id"],
                        status="failed",
                        progress_message="Không thể chuyển tài liệu sang Server 1",
                        error_message=str(e),
                    )

            old_notebook_id = repo.get("notebook_id")
            updated_repo = await db.set_repository_notebooklm_state(
                repo_id,
                new_notebook_id,
                session_fingerprint,
            )
            if old_notebook_id:
                try:
                    await notebooklm_service.delete_notebook(old_notebook_id)
                except Exception as e:
                    logger.warning("Could not delete old NotebookLM notebook %s: %s", old_notebook_id, e)

            return {
                "repository": updated_repo,
                "notebook_id": new_notebook_id,
                "session_changed": True,
                "uploaded": uploaded,
                "failed": failed,
                "total": len(docs),
            }
        except Exception:
            try:
                await notebooklm_service.delete_notebook(new_notebook_id)
            except Exception:
                pass
            raise

    async def ensure_notebooklm_session_current(self, repo: dict, user_id: str) -> dict:
        """
        If the active NotebookLM session changed, migrate only this repository.

        This runs lazily when a user actually uses a repository, avoiding any
        bulk migration across all repositories.
        """
        from app.services.ai_client import ai_client as notebooklm_service

        current_fingerprint = await notebooklm_service.get_session_fingerprint()
        if not current_fingerprint:
            return repo

        stored_fingerprint = repo.get("notebooklm_session_fingerprint") or ""
        if repo.get("notebook_id") and stored_fingerprint == current_fingerprint:
            return repo

        logger.info(
            "NotebookLM session changed for repo %s; rebuilding only this repository",
            repo["id"],
        )
        result = await self.rebuild_notebooklm_repository(repo["id"], user_id)
        return result["repository"]

    async def get_repository_with_docs(self, repo_id: str, user_id: str,
                                        current_user: dict = None) -> dict:
        """Get repository with document count, verifying ownership."""
        repo = await db.get_repository_by_id(repo_id)
        if not repo:
            raise ValueError("Kho dữ liệu không tồn tại")
        if repo["user_id"] != user_id:
            raise PermissionError("Bạn không có quyền truy cập kho dữ liệu này")

        docs = await db.get_documents_by_repository(repo_id)
        repo["document_count"] = len(docs)

        return repo

    async def verify_ownership(self, repo_id: str, user_id: str) -> dict:
        """Verify that a user owns a repository. Returns the repo dict."""
        repo = await db.get_repository_by_id(repo_id)
        if not repo:
            raise ValueError("Kho dữ liệu không tồn tại")
        if repo["user_id"] != user_id:
            raise PermissionError("Bạn không có quyền truy cập kho dữ liệu này")
        return repo

    async def delete_repository(self, repo_id: str, user_id: str,
                                 current_user: dict = None):
        """
        Delete a repository:
        1. Verify ownership
        2. Delete AI backend (notebook if NotebookLM)
        3. Delete files from disk
        4. Delete from database (cascades to documents and chat)
        """
        repo = await self.verify_ownership(repo_id, user_id)

        # Resolve AI engine for this user
        use_self_hosted = is_user_self_hosted(current_user) if current_user else settings.is_self_hosted

        # Delete AI backend
        if not use_self_hosted:
            # NotebookLM: delete notebook
            if repo.get("notebook_id"):
                from app.services.ai_client import ai_client as notebooklm_service
                try:
                    await notebooklm_service.delete_notebook(repo["notebook_id"])
                    logger.info(f"[NotebookLM] Deleted notebook: {repo['notebook_id']}")
                except Exception as e:
                    logger.warning(f"Could not delete NotebookLM notebook: {e}")

        # Delete files
        repo_dir = Path(settings.repo_files_dir) / repo_id
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
            logger.info(f"Deleted repo files: {repo_dir}")

        # Delete from database
        await db.delete_repository(repo_id)
        logger.info(f"Repository deleted: {repo_id}")

    async def upload_document(self, repo_id: str, user_id: str,
                              filename: str, content: bytes,
                              file_type: str = "",
                              folder_key: str = "draft",
                              current_user: dict = None) -> dict:
        """
        Upload a document to a repository:
        1. Save file to disk
        2. Save record to database
        3. Return immediately; background processing handles AI work
        """
        await self.verify_ownership(repo_id, user_id)

        doc_id = str(uuid.uuid4())
        safe_filename = f"{doc_id}_{filename}"
        repo_dir = Path(settings.repo_files_dir) / repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        stored_path = str(repo_dir / safe_filename)

        # Save file to disk
        with open(stored_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved document: {stored_path} ({len(content)} bytes)")

        # Save to database immediately (so the UI shows the document right away)
        doc = await db.create_document(
            repository_id=repo_id,
            filename=filename,
            stored_path=stored_path,
            file_size=len(content),
            file_type=file_type,
            folder_key=folder_key,
            notebooklm_source_id=None,
            doc_id=doc_id,
            processing_status="processing",
            progress_message="Đang chuyển đổi tài liệu",
        )
        await self.create_document_snapshot(doc, content, current_user, "created")

        return doc

    async def replace_document_file(
        self,
        repo_id: str,
        doc_id: str,
        user_id: str,
        filename: str,
        content: bytes,
        file_type: str = "",
        current_user: dict = None,
        version_change_type: str = "edited",
    ) -> dict:
        """Replace an existing document file and reset its processed data."""
        repo = await self.verify_ownership(repo_id, user_id)
        doc = await db.get_document_by_id(doc_id)
        if not doc or doc["repository_id"] != repo_id:
            raise ValueError("Tài liệu không tồn tại trong kho này")

        await self.ensure_document_history(doc, current_user)

        use_self_hosted = is_user_self_hosted(current_user) if current_user else settings.is_self_hosted
        if not use_self_hosted and repo.get("notebook_id") and doc.get("notebooklm_source_id"):
            from app.services.ai_client import ai_client as notebooklm_service
            try:
                await notebooklm_service.delete_source(
                    repo["notebook_id"], doc["notebooklm_source_id"]
                )
            except Exception as e:
                logger.warning("Could not delete old source from NotebookLM: %s", e)

        safe_filename = f"{doc_id}_{Path(filename).name}"
        repo_dir = Path(settings.repo_files_dir) / repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        stored_path = str(repo_dir / safe_filename)

        old_path = Path(doc["stored_path"])
        with open(stored_path, "wb") as f:
            f.write(content)
        if old_path != Path(stored_path) and old_path.exists():
            try:
                old_path.unlink()
            except Exception as e:
                logger.warning("Could not delete replaced file %s: %s", old_path, e)

        updated = await db.update_document_file(
            doc_id=doc_id,
            filename=filename,
            stored_path=stored_path,
            file_size=len(content),
            file_type=file_type,
        )
        if not updated:
            raise ValueError("Tài liệu không tồn tại trong kho này")
        await self.create_document_snapshot(
            updated,
            content,
            current_user,
            version_change_type,
        )
        logger.info("Replaced document file: %s (%s bytes)", doc_id, len(content))
        return updated

    async def process_document(
        self,
        repo_id: str,
        doc_id: str,
        user_id: str,
        current_user: dict = None,
    ) -> None:
        """
        Process a saved document after the upload response has returned.

        Even in NotebookLM mode, also keep markdown content ready for
        self-hosted fallback.
        """
        doc = await db.get_document_by_id(doc_id)
        if not doc:
            logger.warning("Skipping processing for missing document: %s", doc_id)
            return

        repo = await self.verify_ownership(repo_id, user_id)
        if doc["repository_id"] != repo_id:
            logger.warning(
                "Skipping processing for document %s outside repo %s",
                doc_id,
                repo_id,
            )
            return

        filename = doc["filename"]
        stored_path = doc["stored_path"]
        use_self_hosted = is_user_self_hosted(current_user) if current_user else settings.is_self_hosted

        try:
            if not use_self_hosted:
                repo = await self.ensure_notebooklm_session_current(repo, user_id)

            if use_self_hosted:
                # Self-hosted: AI converts; BE persists the returned markdown.
                from app.services.ai_client import ai_client as document_converter, describe_conversion

                await db.update_document_processing(
                    doc_id, status="processing",
                    progress_message="Đang chuyển đổi sang Markdown",
                )

                markdown, vector_count = await document_converter.convert_and_store(doc_id, stored_path)
                note, error_message = describe_conversion(markdown, vector_count)

                await db.update_document_processing(
                    doc_id,
                    status="completed",
                    progress_message=f"Đã chuyển đổi xong ({note})",
                    error_message=error_message,
                    processed_at=datetime.now().isoformat(),
                )
            else:
                markdown = ""
                vector_count = 0
                try:
                    from app.services.ai_client import ai_client as document_converter, describe_conversion

                    await db.update_document_processing(
                        doc_id, status="processing",
                        progress_message="Đang lưu bản nội bộ cho Server 2",
                    )
                    markdown, vector_count = await document_converter.convert_and_store(doc_id, stored_path)
                except Exception as e:
                    logger.warning("Could not prepare self-hosted copy for %s: %s", filename, e)

                # NotebookLM: upload source
                if repo.get("notebook_id"):
                    from app.services.ai_client import ai_client as notebooklm_service

                    source_id = await notebooklm_service.upload_source(
                        repo["notebook_id"], stored_path
                    )
                    logger.info(f"[NotebookLM] Uploaded source: {source_id}")
                    await db.update_document_source_id(doc_id, source_id)

                note, error_message = describe_conversion(markdown, vector_count) if markdown else ("", "")
                await db.update_document_processing(
                    doc_id,
                    status="completed",
                    progress_message=(
                        f"Đã xử lý xong tài liệu, sẵn sàng trên Server 2 ({note})"
                        if markdown else "Đã xử lý xong tài liệu"
                    ),
                    error_message=error_message,
                    processed_at=datetime.now().isoformat(),
                )

        except Exception as e:
            logger.error(f"Document processing failed for {filename}: {e}")
            if not use_self_hosted:
                try:
                    await self.ensure_self_hosted_ready(repo_id)
                    await db.update_document_processing(
                        doc_id,
                        status="completed",
                        progress_message="Server 1 lỗi, đã chuyển sang Server 2",
                        error_message=str(e),
                        processed_at=datetime.now().isoformat(),
                    )
                    return
                except Exception as fallback_error:
                    logger.error("Fallback conversion also failed for %s: %s", filename, fallback_error)

            await db.update_document_processing(
                doc_id,
                status="failed",
                progress_message="Xử lý tài liệu thất bại",
                error_message=str(e),
            )

    async def delete_document(self, repo_id: str, doc_id: str, user_id: str,
                               current_user: dict = None):
        """Delete a document from repository and AI backend."""
        repo = await self.verify_ownership(repo_id, user_id)

        # Resolve AI engine for this user
        use_self_hosted = is_user_self_hosted(current_user) if current_user else settings.is_self_hosted

        doc = await db.get_document_by_id(doc_id)
        if not doc or doc["repository_id"] != repo_id:
            raise ValueError("Tài liệu không tồn tại trong kho này")

        # Delete file from disk
        try:
            stored = Path(doc["stored_path"])
            if stored.exists():
                stored.unlink()
                logger.info(f"Deleted file: {doc['stored_path']}")
            versions_dir = (
                Path(settings.repo_files_dir)
                / repo_id
                / ".versions"
                / doc_id
            )
            if versions_dir.exists():
                shutil.rmtree(versions_dir)
        except Exception as e:
            logger.warning(f"Could not delete file: {e}")

        # NotebookLM: delete source
        if not use_self_hosted and repo.get("notebook_id") and doc.get("notebooklm_source_id"):
            from app.services.ai_client import ai_client as notebooklm_service
            try:
                await notebooklm_service.delete_source(
                    repo["notebook_id"], doc["notebooklm_source_id"]
                )
            except Exception as e:
                logger.warning(f"Could not delete source from NotebookLM: {e}")

        # Remove from DB (markdown_content is deleted with the row)
        await db.delete_document(doc_id)
        logger.info(f"Document deleted: {doc_id}")


# Singleton
repository_service = RepositoryService()
