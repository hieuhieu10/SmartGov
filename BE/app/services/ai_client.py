"""HTTP client for the internal AI service."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app import database as db


class AIServiceError(RuntimeError):
    pass


def describe_conversion(markdown: str, vector_count: int) -> tuple[str, str]:
    """Mô tả trạng thái vector thật sau khi convert/chunk-embed.

    Trả về (đoạn mô tả ngắn, error_message). Nếu markdown có nội dung nhưng
    không có vector nào được lưu, coi là embedding đã lỗi lúc xử lý (dù text
    vẫn dùng được) — khác với trước đây khi `chunk_count` chỉ phản ánh số
    chunk logic dự kiến, không phải số vector thực tế trong `document_chunks`.
    """
    char_count = len(markdown)
    if markdown.strip() and vector_count == 0:
        return (
            f"{char_count} ký tự, CHƯA tạo được vector tìm kiếm",
            "Nhúng vector (embedding) thất bại lúc xử lý; hệ thống sẽ tự tạo lại vector khi có câu hỏi",
        )
    return f"{char_count} ký tự, {vector_count} đoạn", ""


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


class AIClient:
    def _timeout(self, kind: str) -> httpx.Timeout:
        seconds = 5 if kind == "health" else 300 if kind == "chat" else 1800
        return httpx.Timeout(seconds, connect=5)

    async def request(
        self,
        endpoint: str,
        *,
        repo_id: str = "",
        user_id: str = "",
        engine: str = "self_hosted",
        input_data: dict | None = None,
        kind: str = "long",
    ) -> Any:
        payload = {
            "request_id": str(uuid.uuid4()),
            "repo_id": repo_id,
            "user_id": user_id,
            "engine": engine,
            "input_data": _json_safe(input_data or {}),
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

    async def revise_draft_from_summary(
        self, repo_id: str, draft_document: dict, summary_document: dict,
    ) -> str:
        data = await self.request(
            "/internal/summary/revise-draft",
            repo_id=repo_id,
            engine="self_hosted",
            input_data={
                "draft_document": draft_document,
                "summary_document": summary_document,
            },
        )
        return str(data.get("markdown_content") or "")

    async def convert_and_store(self, doc_id: str, file_path: str) -> tuple[str, int]:
        data = await self.request(
            "/internal/documents/convert", input_data={"stored_path": file_path}
        )
        markdown = data.get("markdown_content", "")
        chunks = data.get("chunks")
        vector_count = len(chunks) if isinstance(chunks, list) else 0
        await db.update_document_markdown(doc_id, markdown)
        # chunk_count phải phản ánh số vector THẬT đã lưu, không phải số chunk
        # logic AI dự kiến — nếu không, document có thể hiện "N đoạn" dù
        # document_chunks rỗng khi embedding lỗi.
        await db.update_document_processing(doc_id, chunk_count=vector_count)
        if isinstance(chunks, list) and chunks:
            await db.replace_document_chunks(doc_id, chunks)
        return markdown, vector_count

    async def extract_dataset(self, file_path: str, filename: str) -> dict:
        data = await self.request(
            "/internal/dataset/extract",
            engine="self_hosted",
            input_data={"stored_path": file_path, "filename": filename},
            kind="long",
        )
        document_data = data.get("document_data")
        return document_data if isinstance(document_data, dict) else {}

    async def embed_texts(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        data = await self.request(
            "/internal/embeddings/create",
            input_data={"texts": texts, "input_type": input_type},
            kind="long",
        )
        embeddings = data.get("embeddings") or []
        return embeddings if isinstance(embeddings, list) else []

    async def chunk_embed_and_store(self, doc_id: str, markdown: str, filename: str) -> int:
        data = await self.request(
            "/internal/documents/chunk-embed",
            input_data={"markdown_content": markdown, "filename": filename},
            kind="long",
        )
        chunks = data.get("chunks")
        vector_count = len(chunks) if isinstance(chunks, list) else 0
        await db.update_document_processing(doc_id, chunk_count=vector_count)
        if isinstance(chunks, list) and chunks:
            await db.replace_document_chunks(doc_id, chunks)
        return vector_count

    async def rag_answer(self, question: str, contexts: list[dict], history: list[dict]) -> str:
        data = await self.request(
            "/internal/rag/answer",
            input_data={"question": question, "contexts": contexts, "history": history},
            kind="chat",
        )
        return str(data.get("answer") or "")

    async def analyze_charts(self, text: str, request: str, repo_id: str, user_id: str) -> list[dict]:
        data = await self.request(
            "/internal/charts/analyze", repo_id=repo_id, user_id=user_id,
            input_data={"text": text, "request": request}, kind="chat",
        )
        charts = data.get("charts") or []
        return charts if isinstance(charts, list) else []


ai_client = AIClient()
