"""HTTP client for the internal AI service."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.config import settings
from app import database as db


class AIServiceError(RuntimeError):
    pass


class AIClient:
    async def get_session_fingerprint(self) -> str:
        data = await self.request("/internal/notebook/session")
        return data.get("session_fingerprint", "")

    def _timeout(self, kind: str) -> httpx.Timeout:
        seconds = 5 if kind == "health" else 300 if kind == "chat" else 1800
        return httpx.Timeout(seconds, connect=5)

    async def request(
        self,
        endpoint: str,
        *,
        repo_id: str = "",
        user_id: str = "",
        engine: str = "notebooklm",
        input_data: dict | None = None,
        kind: str = "long",
    ) -> Any:
        payload = {
            "request_id": str(uuid.uuid4()),
            "repo_id": repo_id,
            "user_id": user_id,
            "engine": engine,
            "input_data": input_data or {},
        }
        headers = {"X-AI-Internal-Token": settings.ai_internal_token}
        try:
            async with httpx.AsyncClient(timeout=self._timeout(kind)) as client:
                response = await client.post(
                    f"{settings.ai_service_url.rstrip('/')}{endpoint}",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise AIServiceError(f"Không thể kết nối AI service: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise AIServiceError(f"AI service trả dữ liệu không hợp lệ ({response.status_code})") from exc
        if response.is_error or not body.get("ok"):
            error = body.get("error") or body.get("detail") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise AIServiceError(message or f"AI service lỗi HTTP {response.status_code}")
        return body.get("data") or {}

    async def documents(self, repo_id: str, selected_ids: list[str] | None = None) -> list[dict]:
        rows = await db.get_documents_markdown_by_repository(repo_id, selected_ids or None)
        return [
            {
                "id": row["id"],
                "filename": row["filename"],
                "markdown_content": row.get("markdown_content", ""),
            }
            for row in rows
        ]

    async def create_notebook(self, name: str) -> str:
        data = await self.request("/internal/notebook/create", input_data={"name": name})
        return data["notebook_id"]

    async def delete_notebook(self, notebook_id: str) -> None:
        await self.request("/internal/notebook/delete", input_data={"notebook_id": notebook_id})

    async def upload_source(self, notebook_id: str, file_path: str):
        data = await self.request(
            "/internal/notebook/source/upload",
            input_data={"notebook_id": notebook_id, "stored_path": file_path},
        )
        return data.get("source_id")

    async def delete_source(self, notebook_id: str, source_id: str) -> None:
        await self.request(
            "/internal/notebook/source/delete",
            input_data={"notebook_id": notebook_id, "source_id": source_id},
        )

    async def chat_ask(self, notebook_id: str, question: str) -> str:
        data = await self.request(
            "/internal/notebook/chat",
            input_data={"notebook_id": notebook_id, "question": question},
            kind="chat",
        )
        return data["answer"]

    async def process_audio(self, audio_path: str, on_status=None):
        from app.models import MeetingMinutes
        if on_status:
            await on_status("Đang xử lý nội dung âm thanh...")
        data = await self.request(
            "/internal/audio/process", input_data={"stored_path": audio_path}
        )
        return MeetingMinutes(**data["minutes"])

    async def consolidate_feedback(
        self,
        repo_id: str,
        feedback_documents: list[dict],
        draft_documents: list[dict] | None = None,
    ) -> dict:
        data = await self.request(
            "/internal/summary/consolidate",
            repo_id=repo_id,
            engine="self_hosted",
            input_data={
                "feedback_documents": feedback_documents,
                "draft_documents": draft_documents or [],
            },
        )
        return data.get("summary") or {}

    async def convert_and_store(self, doc_id: str, file_path: str) -> str:
        data = await self.request(
            "/internal/documents/convert", input_data={"stored_path": file_path}
        )
        markdown = data.get("markdown_content", "")
        await db.update_document_markdown(doc_id, markdown)
        return markdown


ai_client = AIClient()
