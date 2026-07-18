"""Internal retrieval API — cho phép AI service (Agent Researcher) gọi ngược
về BE để dùng CHUNG hybrid search (pgvector + FTS) với Chat RAG, thay vì tự
quét toàn bộ tài liệu bằng LLM (`DocumentScanner`).

Route này KHÔNG dành cho FE; được bảo vệ bằng cùng secret `AI_INTERNAL_TOKEN`
mà BE dùng khi gọi AI, đối xứng với `X-AI-Internal-Token` bên AI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_ai_internal_token
from app.services.retrieval_service import retrieval_service

router = APIRouter(
    prefix="/internal/retrieval",
    tags=["Internal Retrieval"],
    dependencies=[Depends(require_ai_internal_token)],
)


class RetrievalSearchRequest(BaseModel):
    repository_id: str
    query: str
    document_ids: list[str] = Field(default_factory=list)
    limit: int = 8


class RetrievalContext(BaseModel):
    document_id: str = ""
    filename: str = ""
    chunk_text: str = ""
    header_path: str = ""
    section_label: str = ""
    page_label: str = ""
    citation_label: str = ""


class RetrievalSearchResponse(BaseModel):
    contexts: list[RetrievalContext]


@router.post("/search", response_model=RetrievalSearchResponse)
async def search_chunks(req: RetrievalSearchRequest) -> RetrievalSearchResponse:
    contexts = await retrieval_service.search(
        req.repository_id,
        req.query,
        document_ids=req.document_ids or None,
        limit=req.limit,
    )
    return RetrievalSearchResponse(
        contexts=[
            RetrievalContext(
                document_id=str(context.get("document_id") or ""),
                filename=str(context.get("filename") or ""),
                chunk_text=str(context.get("chunk_text") or ""),
                header_path=str(context.get("header_path") or ""),
                section_label=str(context.get("section_label") or ""),
                page_label=str(context.get("page_label") or ""),
                citation_label=str(context.get("citation_label") or ""),
            )
            for context in contexts
        ]
    )
