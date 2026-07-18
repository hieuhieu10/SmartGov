"""Chat domain service. AI execution is delegated to the internal AI service."""

import asyncio
import logging
import re
from typing import AsyncGenerator

from app import database as db
from app.services.ai_client import ai_client
from app.services.retrieval_service import retrieval_service

STREAM_DELAY_MS = 35
logger = logging.getLogger(__name__)


class ChatService:
    async def ask_question(self, repo_id: str, user_id: str, question: str) -> str:
        """Answer a chat question.

        RAG-only: chat luôn thử trả lời bằng RAG (pgvector + hybrid search)
        trước; nếu RAG không có gì để trả lời (kho chưa có vector, hoặc không
        tìm thấy nội dung liên quan), fallback sang self-hosted DocumentScanner
        — luồng chat KHÔNG còn phụ thuộc NotebookLM (cần session Google đăng
        nhập qua browser), nên không còn bị lỗi 500 khi NotebookLM chưa login.
        """
        await db.add_chat_message(repo_id, user_id, "user", question)
        try:
            answer = await self._try_rag_answer(repo_id, user_id, question)
            if not answer:
                data = await ai_client.request(
                    "/internal/chat/self-hosted",
                    repo_id=repo_id,
                    user_id=user_id,
                    engine="self_hosted",
                    input_data={
                        "question": question,
                        "documents": await ai_client.documents(repo_id),
                    },
                    kind="chat",
                )
                answer = data["answer"]
            answer = re.sub(r"<br\s*/?>", "\n", answer, flags=re.IGNORECASE)
        except Exception:
            await db.add_chat_message(
                repo_id, user_id, "assistant", "Lỗi hệ thống khi xử lý câu hỏi. Vui lòng thử lại sau."
            )
            raise
        await db.add_chat_message(repo_id, user_id, "assistant", answer)
        return answer

    async def _try_rag_answer(self, repo_id: str, user_id: str, question: str) -> str:
        try:
            contexts = await retrieval_service.search(repo_id, question)
            if not contexts:
                return ""

            history = await db.get_chat_history(repo_id, user_id, limit=12)
            try:
                return await ai_client.rag_answer(question, contexts, history)
            except Exception as exc:
                logger.warning("RAG generation failed; returning retrieval fallback: %s", exc)
                return self._format_retrieval_fallback_answer(contexts)
        except Exception as exc:
            logger.warning("RAG answer path failed; falling back to legacy chat: %s", exc)
            return ""

    def _format_retrieval_fallback_answer(self, contexts: list[dict]) -> str:
        lines = [
            "Tôi tìm thấy các đoạn liên quan trong kho dữ liệu, nhưng bước sinh câu trả lời bằng AI đang lỗi. Các nguồn phù hợp nhất:"
        ]
        for idx, context in enumerate(contexts[:5], start=1):
            citation = str(
                context.get("citation_label")
                or context.get("section_label")
                or context.get("filename")
                or f"Nguồn {idx}"
            )
            excerpt = re.sub(r"\s+", " ", str(context.get("chunk_text") or "")).strip()
            if len(excerpt) > 600:
                excerpt = excerpt[:600].rsplit(" ", 1)[0] + "..."
            lines.append(f"[{idx}] {citation}\n{excerpt}")
        return "\n\n".join(lines)

    async def stream_response(self, full_response: str) -> AsyncGenerator[str, None]:
        tokens = re.findall(r"\S+\s*", full_response)
        if not tokens:
            yield f'{{"type": "chunk", "content": "{full_response}"}}'
        for token in tokens:
            escaped = token.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
            yield f'{{"type": "chunk", "content": "{escaped}"}}'
            await asyncio.sleep(STREAM_DELAY_MS / 1000)
        yield '{"type": "done", "content": ""}'

    async def get_history(self, repo_id: str, user_id: str, limit: int = 50):
        return await db.get_chat_history(repo_id, user_id, limit)

    async def clear_history(self, repo_id: str, user_id: str):
        await db.delete_chat_history(repo_id, user_id)


chat_service = ChatService()
