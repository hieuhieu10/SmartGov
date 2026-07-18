"""Chat domain service. AI execution is delegated to the internal AI service."""

import asyncio
import logging
import re
from typing import AsyncGenerator

from app import database as db
from app.auth import is_user_self_hosted
from app.config import settings
from app.services.ai_client import ai_client

STREAM_DELAY_MS = 35
logger = logging.getLogger(__name__)


class ChatService:
    async def ask_question(
        self, repo_id: str, user_id: str, notebook_id: str, question: str, current_user: dict = None
    ) -> str:
        await db.add_chat_message(repo_id, user_id, "user", question)
        engine = "self_hosted" if (
            is_user_self_hosted(current_user) if current_user else settings.is_self_hosted
        ) else "notebooklm"
        try:
            answer = await self._try_rag_answer(repo_id, user_id, question)
            if answer:
                answer = re.sub(r"<br\s*/?>", "\n", answer, flags=re.IGNORECASE)
            elif engine == "self_hosted":
                data = await ai_client.request(
                    "/internal/chat/self-hosted",
                    repo_id=repo_id,
                    user_id=user_id,
                    engine=engine,
                    input_data={
                        "question": question,
                        "documents": await ai_client.documents(repo_id),
                    },
                    kind="chat",
                )
                answer = re.sub(r"<br\s*/?>", "\n", data["answer"], flags=re.IGNORECASE)
            else:
                data = await ai_client.request(
                    "/internal/notebook/chat",
                    repo_id=repo_id,
                    user_id=user_id,
                    engine=engine,
                    input_data={
                        "notebook_id": notebook_id,
                        "question": f"{question}\n\n(Hãy trả lời dạng văn xuôi, không dùng bảng)",
                    },
                    kind="chat",
                )
                answer = re.sub(r"<br\s*/?>", "\n", data["answer"], flags=re.IGNORECASE)
        except Exception:
            await db.add_chat_message(
                repo_id, user_id, "assistant", "Lỗi hệ thống khi xử lý câu hỏi. Vui lòng thử lại sau."
            )
            raise
        await db.add_chat_message(repo_id, user_id, "assistant", answer)
        return answer

    async def _try_rag_answer(self, repo_id: str, user_id: str, question: str) -> str:
        try:
            await self._ensure_repository_vectors(repo_id)
            if await db.count_repository_chunks(repo_id) <= 0:
                return ""

            embeddings = await ai_client.embed_texts([question], input_type="query")
            query_embedding = embeddings[0] if embeddings else []
            if not query_embedding:
                return ""

            contexts = await db.search_document_chunks_hybrid(
                repo_id,
                question,
                query_embedding,
                limit=settings.rag_top_k,
                vector_candidates=settings.rag_vector_candidates,
                text_candidates=settings.rag_text_candidates,
                vector_weight=settings.rag_vector_weight,
                text_weight=settings.rag_text_weight,
            )
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

    async def _ensure_repository_vectors(self, repo_id: str) -> None:
        docs = await db.get_documents_missing_chunks_by_repository(repo_id)
        for doc in docs:
            markdown = str(doc.get("markdown_content") or "").strip()
            if not markdown:
                continue
            stored = await ai_client.chunk_embed_and_store(
                doc["id"],
                markdown,
                str(doc.get("filename") or ""),
            )
            logger.info(
                "Prepared %s vector chunks for %s",
                stored,
                doc.get("filename"),
            )

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
