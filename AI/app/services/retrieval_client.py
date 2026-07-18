"""HTTP client gọi NGƯỢC về BE để dùng chung hybrid search (pgvector + FTS).

Đây là cách Agent Researcher chia sẻ retrieval với Chat RAG: BE sở hữu
Postgres/pgvector (AI không được thêm DATABASE_URL — xem AGENTS.md), nên khi
AI cần tìm chunk liên quan, nó gọi endpoint nội bộ `/internal/retrieval/search`
trên BE, được bảo vệ bằng cùng secret `AI_INTERNAL_TOKEN` mà BE dùng để gọi
AI (đối xứng, không cần secret mới).
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class RetrievalClient:
    async def search(
        self,
        repo_id: str,
        query: str,
        *,
        document_ids: list[str] | None = None,
        limit: int = 8,
    ) -> list[dict]:
        if not repo_id or not (query or "").strip():
            return []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                response = await client.post(
                    f"{settings.be_service_url.rstrip('/')}/internal/retrieval/search",
                    json={
                        "repository_id": repo_id,
                        "query": query,
                        "document_ids": document_ids or [],
                        "limit": limit,
                    },
                    headers={"X-AI-Internal-Token": settings.ai_internal_token},
                )
                response.raise_for_status()
                data = response.json()
            contexts = data.get("contexts")
            return contexts if isinstance(contexts, list) else []
        except Exception as exc:
            logger.warning("[RetrievalClient] Shared retrieval call failed for repo %s: %s", repo_id, exc)
            return []


retrieval_client = RetrievalClient()
