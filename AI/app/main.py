"""Internal FastAPI service for NotebookLM and self-hosted AI workloads."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.models import DocumentType
from app.services.document_converter import document_converter
from app.services.embedding_service import embedding_service
from app.services.document_scanner import (
    document_scanner,
    reset_request_documents,
    set_request_documents,
)
from app.services.dataset_service import dataset_service
from app.services.drafting_service import drafting_service
from app.services.llm_service import llm_service
from app.services.notebooklm_service import notebooklm_service
from app.services.rag_service import rag_service
from app.services.summary_service import summary_service
from app.services.template_service import template_service

logger = logging.getLogger("officeai.ai")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="OfficeAI Internal AI Service", version="1.0.0")


class Envelope(BaseModel):
    request_id: str
    repo_id: str = ""
    user_id: str = ""
    engine: str = "self_hosted"
    input_data: dict[str, Any] = Field(default_factory=dict)


def ok(data: Any = None) -> dict:
    return {"ok": True, "data": data if data is not None else {}}


async def require_internal_token(
    x_ai_internal_token: str = Header(default="", alias="X-AI-Internal-Token"),
) -> None:
    if not settings.ai_internal_token or x_ai_internal_token != settings.ai_internal_token:
        raise HTTPException(status_code=401, detail="Invalid internal AI token")


def _documents(payload: Envelope) -> list[dict]:
    return payload.input_data.get("documents") or []


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    logger.exception("Internal AI request failed")
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": {"code": "AI_ERROR", "message": str(exc)}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Internal AI request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {"code": f"HTTP_{exc.status_code}", "message": message},
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": {"code": "INVALID_REQUEST", "message": str(exc)},
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "officeai-ai"}


@app.post("/internal/documents/convert", dependencies=[Depends(require_internal_token)])
async def convert_document(payload: Envelope) -> dict:
    path = payload.input_data["stored_path"]
    result = await asyncio.to_thread(document_converter.convert_document, path)
    return ok(result)


@app.post("/internal/documents/chunk-embed", dependencies=[Depends(require_internal_token)])
async def chunk_embed_document(payload: Envelope) -> dict:
    data = payload.input_data
    result = await asyncio.to_thread(
        document_converter.chunk_and_embed_markdown,
        str(data.get("markdown_content") or ""),
        str(data.get("filename") or ""),
    )
    return ok(result)


@app.post("/internal/embeddings/create", dependencies=[Depends(require_internal_token)])
async def create_embeddings(payload: Envelope) -> dict:
    texts = [str(item) for item in (payload.input_data.get("texts") or [])]
    input_type = str(payload.input_data.get("input_type") or "document")
    embeddings = await asyncio.to_thread(embedding_service.embed_texts, texts, input_type)
    return ok(
        {
            "model": embedding_service.model_name if embeddings else "",
            "dimensions": len(embeddings[0]) if embeddings else 0,
            "embeddings": embeddings,
        }
    )


@app.post("/internal/rag/answer", dependencies=[Depends(require_internal_token)])
async def answer_with_rag(payload: Envelope) -> dict:
    data = payload.input_data
    answer = await rag_service.answer(
        question=str(data.get("question") or ""),
        contexts=data.get("contexts") or [],
        history=data.get("history") or [],
    )
    return ok({"answer": answer})


@app.post("/internal/chat/self-hosted", dependencies=[Depends(require_internal_token)])
async def chat_self_hosted(payload: Envelope) -> dict:
    question = str(payload.input_data["question"])
    token = set_request_documents(_documents(payload))
    try:
        results = await document_scanner.scan_for_chat(payload.repo_id, question)
        if not results:
            return ok({"answer": "Không tìm thấy thông tin đủ căn cứ trong các tài liệu đã chọn."})
        context = document_scanner.format_scanner_results(results)
        answer = await llm_service.chat(
            "Bạn là trợ lý hành chính. Chỉ trả lời từ ngữ cảnh tài liệu, không bịa thông tin.",
            f"CÂU HỎI:\n{question}\n\nNGỮ CẢNH:\n{context}",
            max_tokens=4096,
        )
        return ok({"answer": answer})
    finally:
        reset_request_documents(token)


@app.post("/internal/dataset/extract", dependencies=[Depends(require_internal_token)])
async def extract_dataset(payload: Envelope) -> dict:
    path = payload.input_data["stored_path"]
    filename = str(payload.input_data.get("filename") or "")
    markdown = await asyncio.to_thread(document_converter.convert_to_markdown_only, path)
    document_data = await dataset_service.extract(markdown, filename)
    return ok({"document_data": document_data})


@app.post("/internal/summary/consolidate", dependencies=[Depends(require_internal_token)])
async def consolidate_feedback(payload: Envelope) -> dict:
    feedback_docs = payload.input_data.get("feedback_documents") or _documents(payload)
    draft_docs = payload.input_data.get("draft_documents") or []
    summary = await summary_service.consolidate_feedback(feedback_docs, draft_docs)
    return ok({"summary": summary})


@app.post("/internal/draft/generate", dependencies=[Depends(require_internal_token)])
async def generate_draft(payload: Envelope) -> dict:
    data = payload.input_data
    doc_type = DocumentType(data["document_type"])
    token = set_request_documents(_documents(payload))
    try:
        if payload.engine == "self_hosted":
            result = await drafting_service._draft_self_hosted(
                payload.repo_id,
                doc_type,
                data.get("draft_input") or {},
                selected_document_ids=data.get("selected_document_ids") or [],
            )
        else:
            result = await drafting_service._draft_notebooklm(
                data.get("notebook_id", ""),
                doc_type,
                data.get("draft_input") or {},
                repo_id=payload.repo_id,
                selected_document_ids=data.get("selected_document_ids") or [],
            )
        return ok({"draft_data": result})
    finally:
        reset_request_documents(token)


@app.post("/internal/draft/edit", dependencies=[Depends(require_internal_token)])
async def edit_draft(payload: Envelope) -> dict:
    data = payload.input_data
    doc_type = DocumentType(data["document_type"])
    if payload.engine == "self_hosted":
        draft, inputs = await drafting_service._edit_draft_data_self_hosted(
            doc_type, data.get("draft_data") or {}, data.get("draft_input") or {}, data["instruction"]
        )
    else:
        draft, inputs = await drafting_service._edit_draft_data_notebooklm(
            data.get("notebook_id", ""),
            doc_type,
            data.get("draft_data") or {},
            data.get("draft_input") or {},
            data["instruction"],
        )
    return ok({"draft_data": draft, "input_data": inputs})


@app.post("/internal/template/extract", dependencies=[Depends(require_internal_token)])
async def extract_template(payload: Envelope) -> dict:
    path = payload.input_data["stored_path"]
    if payload.engine == "self_hosted":
        result = await template_service._extract_headings_self_hosted(path)
    else:
        result = await template_service._extract_headings_notebooklm(path)
    return ok(result)


@app.post("/internal/template/generate", dependencies=[Depends(require_internal_token)])
async def generate_template(payload: Envelope) -> dict:
    data = payload.input_data
    token = set_request_documents(_documents(payload))
    try:
        if payload.engine == "self_hosted":
            result = await template_service._generate_self_hosted(
                data.get("headings") or [],
                data.get("doc_type_label", ""),
                data.get("trich_yeu", ""),
                data.get("user_input") or {},
                payload.repo_id,
                selected_document_ids=data.get("selected_document_ids") or [],
            )
        else:
            source_filter = await template_service._build_source_filter(
                data.get("selected_document_ids") or []
            )
            result = await template_service._generate_notebooklm(
                data.get("headings") or [],
                data.get("notebook_id", ""),
                data.get("doc_type_label", ""),
                data.get("trich_yeu", ""),
                data.get("user_input") or {},
                source_filter=source_filter,
            )
        return ok({"content": result})
    finally:
        reset_request_documents(token)


@app.post("/internal/notebook/create", dependencies=[Depends(require_internal_token)])
async def create_notebook(payload: Envelope) -> dict:
    notebook_id = await notebooklm_service.create_notebook(payload.input_data["name"])
    return ok(
        {
            "notebook_id": notebook_id,
            "session_fingerprint": notebooklm_service.get_session_fingerprint(),
        }
    )


@app.post("/internal/notebook/session", dependencies=[Depends(require_internal_token)])
async def notebook_session(_: Envelope) -> dict:
    return ok({"session_fingerprint": notebooklm_service.get_session_fingerprint()})


@app.post("/internal/notebook/delete", dependencies=[Depends(require_internal_token)])
async def delete_notebook(payload: Envelope) -> dict:
    await notebooklm_service.delete_notebook(payload.input_data["notebook_id"])
    return ok()


@app.post("/internal/notebook/source/upload", dependencies=[Depends(require_internal_token)])
async def upload_source(payload: Envelope) -> dict:
    source_id = await notebooklm_service.upload_source(
        payload.input_data["notebook_id"], payload.input_data["stored_path"]
    )
    return ok({"source_id": source_id})


@app.post("/internal/notebook/source/delete", dependencies=[Depends(require_internal_token)])
async def delete_source(payload: Envelope) -> dict:
    await notebooklm_service.delete_source(
        payload.input_data["notebook_id"], payload.input_data["source_id"]
    )
    return ok()


