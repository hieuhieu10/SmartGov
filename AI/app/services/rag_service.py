"""RAG answer generation over BE-provided retrieval contexts."""

from __future__ import annotations

from app.config import settings
from app.services.llm_service import llm_service


RAG_SYSTEM_PROMPT = """Bạn là trợ lý tài liệu hành chính Việt Nam.
Nhiệm vụ: trả lời câu hỏi CHỈ dựa trên các đoạn tài liệu được cung cấp trong NGỮ CẢNH TRUY XUẤT.

Quy tắc:
1. Chỉ dùng thông tin xuất hiện trực tiếp trong NGỮ CẢNH TRUY XUẤT; không dùng kiến thức nền hoặc dữ kiện ngoài tài liệu.
2. Không bịa thông tin, không suy đoán, không tự bổ sung số liệu, ngày tháng, cơ quan, căn cứ pháp lý hoặc kết luận nếu tài liệu không nêu.
3. Nếu ngữ cảnh không có câu trả lời trực tiếp, trả lời đúng ý: "Tôi chưa tìm thấy thông tin này trong tài liệu được cung cấp."
4. Giữ đúng số hiệu văn bản, ngày tháng, cơ quan, điều/khoản/mục nếu có trong tài liệu.
5. Mọi nhận định quan trọng phải có nhãn trích dẫn dạng [1], [2] ngay trong câu.
6. Trả lời bằng tiếng Việt, rõ ràng, ưu tiên văn xuôi ngắn gọn."""


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

Chỉ trả lời dựa trên NGỮ CẢNH TRUY XUẤT. Nếu không đủ căn cứ, hãy nói chưa tìm thấy thông tin này trong tài liệu được cung cấp."""

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
