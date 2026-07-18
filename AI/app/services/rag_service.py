"""RAG answer generation over BE-provided retrieval contexts."""

from __future__ import annotations

from app.config import settings
from app.services.llm_service import llm_service


RAG_SYSTEM_PROMPT = """Bạn là trợ lý tài liệu hành chính Việt Nam.
Nhiệm vụ: trả lời câu hỏi CHỈ dựa trên các đoạn tài liệu được cung cấp.

Quy tắc:
1. Không bịa thông tin, không suy đoán ngoài ngữ cảnh.
2. Nếu ngữ cảnh không đủ căn cứ, nói rõ là chưa tìm thấy đủ thông tin trong tài liệu.
3. Giữ đúng số hiệu văn bản, ngày tháng, cơ quan, điều/khoản/mục nếu có.
4. Khi dùng thông tin từ đoạn nào, ghi nhãn trích dẫn dạng [1], [2] ngay trong câu.
5. Trả lời bằng tiếng Việt, rõ ràng, ưu tiên văn xuôi ngắn gọn."""


class RAGService:
    async def answer(self, question: str, contexts: list[dict], history: list[dict] | None = None) -> str:
        context_text = self._format_contexts(contexts)
        history_text = self._format_history(history or [])
        user_prompt = f"""LỊCH SỬ HỘI THOẠI GẦN ĐÂY:
{history_text or "(không có)"}

CÂU HỎI:
{question}

NGỮ CẢNH TRUY XUẤT:
{context_text or "(không có ngữ cảnh)"}

Hãy trả lời dựa trên ngữ cảnh truy xuất."""

        return await llm_service.chat(
            system_prompt=RAG_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=4096,
        )

    def _format_contexts(self, contexts: list[dict]) -> str:
        blocks: list[str] = []
        max_chars = settings.context_max_chars
        used = 0
        for index, item in enumerate(contexts, start=1):
            citation = str(item.get("citation_label") or item.get("filename") or f"Nguồn {index}")
            text = str(item.get("chunk_text") or "").strip()
            if not text:
                continue
            block = f"[{index}] {citation}\n{text}"
            if used + len(block) > max_chars:
                break
            blocks.append(block)
            used += len(block)
        return "\n\n---\n\n".join(blocks)

    def _format_history(self, history: list[dict]) -> str:
        lines: list[str] = []
        for item in history[-8:]:
            role = "Người dùng" if item.get("role") == "user" else "Trợ lý"
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)


rag_service = RAGService()
