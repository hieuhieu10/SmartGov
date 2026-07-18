"""Revision workflow service for comments-to-final-document tasks."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from app import database as db
from app.config import settings
from app.services.document_dataset_service import document_dataset_service
from app.services.nd30_exporter import build as build_nd30_docx


class RevisionService:
    """Owns the BE-side revision lifecycle.

    The current implementation uses deterministic mock extraction so FE and BE
    can integrate before the internal AI endpoint is ready.
    """

    def task_dir(self, task_id: str) -> Path:
        path = Path(settings.output_dir) / "revision_tasks" / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def create_task(
        self,
        *,
        task_id: str,
        user_id: str,
        repo_id: str | None,
        title: str,
        original_document_data: dict[str, Any] | None,
        base_document: dict[str, Any] | None,
        comment_files: list[dict[str, Any]],
    ) -> dict:
        task_path = self.task_dir(task_id)
        saved_files = self._save_inputs(task_path, base_document, comment_files)
        return await db.create_revision_task(
            task_id,
            user_id,
            repo_id,
            title=title,
            input_files=saved_files,
            original_document_data=original_document_data or {},
            status="pending",
            progress_message="Đã tạo yêu cầu xử lý góp ý.",
        )

    async def process_mock(self, task_id: str) -> None:
        task = await db.get_revision_task_by_id(task_id)
        if not task:
            return

        try:
            await db.update_revision_task(
                task_id,
                status="processing",
                progress_message="Đang trích xuất góp ý và tạo bản đề xuất...",
                error_message="",
            )

            title = task.get("title") or "Bản tổng hợp góp ý"
            original_data = task.get("original_document_data") or {}
            if not original_data:
                original_data = document_dataset_service.build_mock_response(title).document_data
                original_data["trich_yeu"] = title
                original_data["trich_yeu_dong"] = [title]

            comments = self._mock_extract_comments(task.get("input_files") or {})
            proposed_data = self._apply_comments(original_data, comments)
            diff_data = self._build_diff(original_data, proposed_data, comments)

            task_path = self.task_dir(task_id)
            original_file = str(task_path / "original.docx")
            proposed_file = str(task_path / "proposed.docx")
            build_nd30_docx(original_data, original_file)
            build_nd30_docx(proposed_data, proposed_file)

            await db.update_revision_task(
                task_id,
                status="ready_for_review",
                progress_message="Bản đề xuất đã sẵn sàng để rà soát.",
                original_document_data=original_data,
                proposed_document_data=proposed_data,
                extracted_comments=comments,
                diff_data=diff_data,
                original_file=original_file,
                proposed_file=proposed_file,
            )
        except Exception as exc:
            await db.update_revision_task(
                task_id,
                status="error",
                progress_message="Không thể xử lý góp ý.",
                error_message=str(exc),
            )

    async def approve(self, task_id: str) -> dict | None:
        task = await db.get_revision_task_by_id(task_id)
        if not task:
            return None
        proposed_data = task.get("proposed_document_data") or {}
        proposed_file = Path(task.get("proposed_file") or "")
        final_file = self.task_dir(task_id) / "final.docx"

        if proposed_file.exists():
            shutil.copy2(proposed_file, final_file)
        else:
            build_nd30_docx(proposed_data, str(final_file))

        return await db.update_revision_task(
            task_id,
            status="completed",
            progress_message="Đã duyệt góp ý và tạo bản hoàn chỉnh.",
            approved_document_data=proposed_data,
            final_file=str(final_file),
            reject_reason="",
        )

    async def reject(self, task_id: str, reason: str = "") -> dict | None:
        return await db.update_revision_task(
            task_id,
            status="rejected",
            progress_message="Bản đề xuất đã bị từ chối.",
            reject_reason=reason,
        )

    async def delete_files(self, task: dict) -> None:
        task_id = task.get("id")
        if task_id:
            shutil.rmtree(self.task_dir(task_id), ignore_errors=True)

    def _save_inputs(
        self,
        task_path: Path,
        base_document: dict[str, Any] | None,
        comment_files: list[dict[str, Any]],
    ) -> dict:
        input_dir = task_path / "inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {"base_document": None, "comment_files": []}

        if base_document:
            path = input_dir / f"base_{Path(base_document['filename']).name}"
            path.write_bytes(base_document["content"])
            result["base_document"] = {
                "filename": base_document["filename"],
                "stored_path": str(path),
                "file_size": len(base_document["content"]),
                "file_type": base_document.get("file_type", ""),
            }

        for index, item in enumerate(comment_files, start=1):
            path = input_dir / f"comment_{index}_{Path(item['filename']).name}"
            path.write_bytes(item["content"])
            result["comment_files"].append({
                "filename": item["filename"],
                "stored_path": str(path),
                "file_size": len(item["content"]),
                "file_type": item.get("file_type", ""),
            })

        return result

    def _mock_extract_comments(self, input_files: dict) -> list[dict[str, Any]]:
        files = input_files.get("comment_files") or []
        if not files:
            files = [{"filename": "gop-y-mau.pdf"}]
        comments = []
        for index, item in enumerate(files, start=1):
            comments.append({
                "id": f"comment-{index}",
                "source_file": item.get("filename", ""),
                "section": "Phụ lục nhiệm vụ",
                "content": f"Bổ sung nội dung góp ý từ {item.get('filename', 'file góp ý')}.",
                "suggestion": "Cập nhật vào danh mục nhiệm vụ để người dùng rà soát trước khi duyệt.",
                "status": "proposed",
            })
        return comments

    def _apply_comments(self, original_data: dict, comments: list[dict[str, Any]]) -> dict:
        proposed = copy.deepcopy(original_data)
        proposed.setdefault("noi_dung", [])
        proposed["noi_dung"].append("IV. NỘI DUNG TIẾP THU, GIẢI TRÌNH GÓP Ý")
        for item in comments:
            proposed["noi_dung"].append(f"- {item['suggestion']}")

        proposed.setdefault("phu_luc", [])
        if not proposed["phu_luc"]:
            proposed["phu_luc"].append({
                "tieu_de": "DANH MỤC GÓP Ý ĐƯỢC ĐỀ XUẤT TIẾP THU",
                "noi_dung": [],
                "landscape": True,
                "bang": [],
            })

        appendix = proposed["phu_luc"][0]
        appendix.setdefault("bang", [])
        if not appendix["bang"]:
            appendix["bang"].append({
                "headers": ["STT", "Nguồn góp ý", "Nội dung góp ý", "Đề xuất cập nhật"],
                "rows": [],
            })

        table = appendix["bang"][0]
        rows = table.setdefault("rows", [])
        for index, item in enumerate(comments, start=len(rows) + 1):
            rows.append([
                str(index),
                item.get("source_file", ""),
                item.get("content", ""),
                item.get("suggestion", ""),
            ])
        return proposed

    def _build_diff(
        self,
        original_data: dict,
        proposed_data: dict,
        comments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        original_len = len(original_data.get("noi_dung") or [])
        proposed_body = proposed_data.get("noi_dung") or []
        return [
            {
                "id": item["id"],
                "section": item.get("section", ""),
                "field": "noi_dung",
                "original_text": "",
                "proposed_text": proposed_body[original_len + index] if original_len + index < len(proposed_body) else item.get("suggestion", ""),
                "comment_source": item.get("source_file", ""),
                "reason": "Mock BE: đề xuất này sẽ được thay bằng phân tích AI thật ở bước tích hợp AI.",
            }
            for index, item in enumerate(comments, start=1)
        ]

    def parse_document_data(self, raw: str = "") -> dict[str, Any]:
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}


revision_service = RevisionService()
