"""Shared retrieval: hybrid search (pgvector + full-text) over `document_chunks`.

Đây là nguồn retrieval DUY NHẤT cho mọi luồng cần đọc tài liệu đã upload —
Chat RAG (qua BE) và Agent Researcher (AI gọi ngược lại qua
`internal_retrieval_router`) đều dùng chung service này, để citation/chất
lượng tìm kiếm không lệch nhau giữa hai luồng.
"""

from __future__ import annotations

import logging

from app import database as db
from app.config import settings
from app.services.ai_client import ai_client

logger = logging.getLogger(__name__)


class RetrievalService:
    async def ensure_repository_vectors(self, repo_id: str) -> None:
        """Lazily (re)tạo vector cho tài liệu đã có markdown nhưng chưa có chunk.

        Đây là cơ chế tự hồi phục khi embedding lỗi lúc convert ban đầu (xem
        `ai_client.describe_conversion`) — chạy trước mỗi lần tìm kiếm.
        """
        docs = await db.get_documents_missing_chunks_by_repository(repo_id)
        for doc in docs:
            markdown = str(doc.get("markdown_content") or "").strip()
            if not markdown:
                continue
            stored = await ai_client.chunk_embed_and_store(
                doc["id"], markdown, str(doc.get("filename") or "")
            )
            if stored > 0:
                logger.info("Prepared %s vector chunks for %s", stored, doc.get("filename"))
            else:
                logger.warning(
                    "Retry chunk-embed produced 0 vectors for %s; will retry again later",
                    doc.get("filename"),
                )

    async def search(
        self,
        repo_id: str,
        query: str,
        *,
        document_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Hybrid search trong một repository, tùy chọn giới hạn theo document_ids."""
        query = (query or "").strip()
        if not repo_id or not query:
            return []

        await self.ensure_repository_vectors(repo_id)
        if await db.count_repository_chunks(repo_id) <= 0:
            return []

        embeddings = await ai_client.embed_texts([query], input_type="query")
        query_embedding = embeddings[0] if embeddings else []
        if not query_embedding:
            return []

        top_k = limit or settings.rag_top_k
        # Khi lọc theo document_ids, lấy nhiều candidate hơn trước khi lọc để
        # tránh còn lại quá ít kết quả sau khi loại các tài liệu không được chọn.
        candidate_multiplier = 4 if document_ids else 1

        contexts = await db.search_document_chunks_hybrid(
            repo_id,
            query,
            query_embedding,
            limit=top_k * candidate_multiplier,
            vector_candidates=settings.rag_vector_candidates * candidate_multiplier,
            text_candidates=settings.rag_text_candidates * candidate_multiplier,
            vector_weight=settings.rag_vector_weight,
            text_weight=settings.rag_text_weight,
        )

        if document_ids:
            allowed = {str(value) for value in document_ids}
            contexts = [c for c in contexts if str(c.get("document_id") or "") in allowed]

        return contexts[:top_k]


retrieval_service = RetrievalService()
