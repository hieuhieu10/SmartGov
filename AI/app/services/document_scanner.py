"""
Document Scanner — LLM Sequential Scan for retrieving relevant content.

Replaces the old Milvus/Neo4j hybrid search with a simple approach:
  1. Receive authorized markdown documents from BE
  2. For each document, call LLM to extract relevant excerpts
  3. If document is not relevant, LLM returns empty → skip
  4. Collect all relevant excerpts as context for Writer/Chat
  5. Truncate assembled context to fit within LLM context window

This service is used by both Chat and Drafting pipelines.

Token budget (gpt-oss-120b, 128K context):
  - Scanner call: doc_chunk_size=80000 chars (~20K tokens input)
    + system+query ~1K tokens → leaves ~107K tokens headroom
    + scanner_max_tokens=8192 output
  - Final answer: context_max_chars=400000 chars (~100K tokens)
    + system+query ~1K tokens + output 4-8K → fits in 128K
"""

import json
import logging
import re
from contextvars import ContextVar
from typing import Optional

from app.config import settings
from app.services.llm_service import llm_service
from app.services.markdown_chunking import split_markdown

logger = logging.getLogger(__name__)
_request_documents: ContextVar[list[dict]] = ContextVar("request_documents", default=[])


def set_request_documents(documents: list[dict]):
    return _request_documents.set(documents or [])


def reset_request_documents(token) -> None:
    _request_documents.reset(token)


def get_request_documents() -> list[dict]:
    return _request_documents.get()

# ─── Prompts ─────────────────────────────────────────────────────────

SCAN_FOR_DRAFTING_SYSTEM = """Bạn là chuyên viên phân tích tài liệu hành chính Việt Nam phục vụ soạn thảo văn bản theo Nghị định 30/2020/NĐ-CP.
Nhiệm vụ: Đọc tài liệu được cung cấp và trích xuất ĐẦY ĐỦ tất cả đoạn/thông tin liên quan đến dàn ý/yêu cầu soạn thảo.

QUY TẮC:
1. Chỉ trích xuất nội dung THỰC SỰ có trong tài liệu — KHÔNG bịa thêm.
2. Giữ nguyên số liệu, ngày tháng, tên riêng, căn cứ pháp lý.
3. Nếu tài liệu KHÔNG LIÊN QUAN đến yêu cầu soạn thảo → trả về JSON: {"relevant": false, "excerpts": []}
4. Nếu có nội dung liên quan → trả về JSON:
   {"relevant": true, "priority": "high|medium|low", "document_type": "loại văn bản nếu nhận diện được", "field": "lĩnh vực nếu nhận diện được", "legal_level": "mức giá trị pháp lý nếu nhận diện được", "document_date": "ngày/năm nếu có", "excerpts": ["đoạn trích 1", "đoạn trích 2", ...]}
5. Trích xuất ĐẦY ĐỦ, KHÔNG BỎ SÓT bất kỳ phần nào của tài liệu:
   - Nội dung chính (các điều khoản, mục, khoản)
   - PHỤ LỤC, bảng biểu, danh mục kèm theo
   - Phần đính kèm, ghi chú, chú thích
   - Số liệu, chỉ tiêu, bảng thống kê
   Mỗi đoạn trích giữ nguyên nội dung gốc, không tóm tắt, không rút gọn.
6. Tự làm sạch lỗi OCR/markdown ở mức cần thiết để hiểu đúng ngữ cảnh; không giữ ký tự nhiễu vô nghĩa.
7. Xếp priority cao hơn cho văn bản cùng lĩnh vực, cùng loại, mới hơn, hoặc có giá trị pháp lý cao hơn.
8. CHỈ trả về JSON thuần — KHÔNG markdown, KHÔNG giải thích."""

SCAN_FOR_CHAT_SYSTEM = """Bạn là chuyên viên phân tích tài liệu hành chính Việt Nam.
Nhiệm vụ: Đọc tài liệu được cung cấp và trích xuất ĐẦY ĐỦ tất cả đoạn/thông tin có thể giúp trả lời câu hỏi của người dùng.

QUY TẮC:
1. Chỉ trích xuất nội dung THỰC SỰ có trong tài liệu — KHÔNG bịa thêm.
2. Giữ nguyên số liệu, ngày tháng, tên riêng.
3. Nếu tài liệu KHÔNG LIÊN QUAN đến câu hỏi → trả về JSON: {"relevant": false, "excerpts": []}
4. Nếu có nội dung liên quan → trả về JSON:
   {"relevant": true, "excerpts": ["đoạn trích 1", "đoạn trích 2", ...]}
5. Trích xuất ĐẦY ĐỦ, KHÔNG BỎ SÓT bất kỳ phần nào:
   - Nội dung chính (các điều khoản, mục, khoản)
   - PHỤ LỤC, bảng biểu, danh mục kèm theo
   - Phần đính kèm, ghi chú, chú thích
   - Số liệu, chỉ tiêu, bảng thống kê
   Giữ nguyên nội dung gốc, không tóm tắt, không rút gọn.
6. CHỈ trả về JSON thuần — KHÔNG markdown, KHÔNG giải thích."""


class DocumentScanner:
    """Scan documents in a repository using LLM to extract relevant content."""

    async def scan_repository(
        self,
        repo_id: str,
        outline: str,
        max_docs: int = 0,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        """
        Scan all documents in a repository for content relevant to a drafting outline.

        Args:
            repo_id: Repository UUID.
            outline: The drafting outline/requirements to match against.
            max_docs: Maximum number of documents to scan (0 = no limit).

        Returns:
            List of dicts: {filename, excerpts: [str], doc_id}
            Only includes documents that had relevant content.
        """
        docs = get_request_documents()
        if document_ids:
            selected = set(document_ids)
            docs = [doc for doc in docs if str(doc.get("id")) in selected]

        if max_docs > 0:
            docs = docs[:max_docs]

        if not docs:
            logger.warning(f"[Scanner] No documents with markdown in repo {repo_id}")
            return []

        logger.info(
            f"[Scanner] Scanning {len(docs)} documents in repo {repo_id} "
            f"for drafting outline ({len(outline)} chars, selected={bool(document_ids)})"
        )

        results = []
        for doc in docs:
            doc_result = await self._scan_single_document(
                markdown_content=doc["markdown_content"],
                filename=doc["filename"],
                query=outline,
                system_prompt=SCAN_FOR_DRAFTING_SYSTEM,
                query_label="DÀN Ý/YÊU CẦU SOẠN THẢO",
            )
            if doc_result and doc_result.get("relevant"):
                results.append({
                    "filename": doc["filename"],
                    "doc_id": doc["id"],
                    "priority": doc_result.get("priority", "medium"),
                    "document_type": doc_result.get("document_type", ""),
                    "field": doc_result.get("field", ""),
                    "legal_level": doc_result.get("legal_level", ""),
                    "document_date": doc_result.get("document_date", ""),
                    "excerpts": doc_result.get("excerpts", []),
                })

        results.sort(key=self._result_priority_key)

        logger.info(
            f"[Scanner] Drafting scan complete: {len(results)}/{len(docs)} "
            f"documents had relevant content"
        )
        return results

    async def scan_for_chat(
        self,
        repo_id: str,
        question: str,
        max_docs: int = 0,
    ) -> list[dict]:
        """
        Scan all documents in a repository for content relevant to a chat question.

        Args:
            repo_id: Repository UUID.
            question: The user's question.
            max_docs: Maximum number of documents to scan (0 = no limit).

        Returns:
            List of dicts: {filename, excerpts: [str], doc_id}
            Only includes documents that had relevant content.
        """
        docs = get_request_documents()

        if max_docs > 0:
            docs = docs[:max_docs]

        if not docs:
            logger.warning(f"[Scanner] No documents with markdown in repo {repo_id}")
            return []

        logger.info(
            f"[Scanner] Scanning {len(docs)} documents in repo {repo_id} "
            f"for chat question: '{question[:80]}...'"
        )

        results = []
        for doc in docs:
            doc_result = await self._scan_single_document(
                markdown_content=doc["markdown_content"],
                filename=doc["filename"],
                query=question,
                system_prompt=SCAN_FOR_CHAT_SYSTEM,
                query_label="CÂU HỎI",
            )
            if doc_result and doc_result.get("relevant"):
                results.append({
                    "filename": doc["filename"],
                    "doc_id": doc["id"],
                    "excerpts": doc_result.get("excerpts", []),
                })

        logger.info(
            f"[Scanner] Chat scan complete: {len(results)}/{len(docs)} "
            f"documents had relevant content"
        )
        return results

    async def _scan_single_document(
        self,
        markdown_content: str,
        filename: str,
        query: str,
        system_prompt: str,
        query_label: str = "YÊU CẦU",
    ) -> Optional[dict]:
        """
        Scan a single document's markdown content for relevant excerpts.

        Chunking logic:
        - If doc_chunk_size > 0 and doc exceeds it → split into chunks
        - If doc_chunk_size == 0 but doc exceeds safe limit → auto-chunk
        - Otherwise → single LLM call
        """
        if not markdown_content or not markdown_content.strip():
            return {"relevant": False, "excerpts": []}

        chunk_size = settings.doc_chunk_size
        content_len = len(markdown_content)

        # Auto-chunk safety: even with chunk_size=0, don't exceed ~100K tokens input
        # 128K context - 8K output - 2K system/query = ~118K tokens ≈ 472K chars
        auto_safe_limit = 400000  # ~100K tokens, very conservative

        if chunk_size > 0 and content_len > chunk_size:
            return await self._scan_chunked(
                markdown_content, filename, query,
                system_prompt, query_label, chunk_size,
            )
        elif chunk_size == 0 and content_len > auto_safe_limit:
            # Auto-chunk even when doc_chunk_size=0 to prevent context overflow
            logger.warning(
                f"[Scanner] Document '{filename}' is {content_len} chars, "
                f"auto-chunking to {auto_safe_limit} chars despite doc_chunk_size=0"
            )
            return await self._scan_chunked(
                markdown_content, filename, query,
                system_prompt, query_label, auto_safe_limit,
            )
        else:
            return await self._call_llm_scan(
                markdown_content, filename, query,
                system_prompt, query_label,
            )

    async def _scan_chunked(
        self,
        markdown_content: str,
        filename: str,
        query: str,
        system_prompt: str,
        query_label: str,
        chunk_size: int,
    ) -> dict:
        """Split a large document into chunks and scan each one."""
        chunks = split_markdown(markdown_content, chunk_size)
        all_excerpts = []

        logger.info(
            f"[Scanner] Document '{filename}' is {len(markdown_content)} chars, "
            f"splitting into {len(chunks)} chunks of ~{chunk_size} chars"
        )

        for i, chunk in enumerate(chunks):
            result = await self._call_llm_scan(
                chunk, f"{filename} (phần {i+1}/{len(chunks)})",
                query, system_prompt, query_label,
            )
            if result and result.get("relevant"):
                all_excerpts.extend(result.get("excerpts", []))

        return {
            "relevant": len(all_excerpts) > 0,
            "excerpts": all_excerpts,
        }

    async def _call_llm_scan(
        self,
        content: str,
        filename: str,
        query: str,
        system_prompt: str,
        query_label: str,
    ) -> Optional[dict]:
        """Call LLM to scan content for relevant excerpts."""
        user_prompt = f"""{query_label}:
{query}

---

TÀI LIỆU: {filename}

{content}"""

        try:
            result = await llm_service.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=settings.scanner_max_tokens,
            )
            if not result:
                return {"relevant": False, "excerpts": []}

            relevant = result.get("relevant", False)
            excerpts = result.get("excerpts", [])

            # Ensure excerpts is a list of strings
            if isinstance(excerpts, str):
                excerpts = [excerpts] if excerpts.strip() else []
            elif isinstance(excerpts, list):
                excerpts = [str(e) for e in excerpts if e]

            logger.info(
                f"[Scanner] '{filename}': relevant={relevant}, "
                f"{len(excerpts)} excerpts, "
                f"total_excerpt_chars={sum(len(e) for e in excerpts)}"
            )
            return {
                "relevant": relevant,
                "priority": result.get("priority", "medium"),
                "document_type": result.get("document_type", ""),
                "field": result.get("field", ""),
                "legal_level": result.get("legal_level", ""),
                "document_date": result.get("document_date", ""),
                "excerpts": excerpts,
            }

        except Exception as e:
            logger.error(f"[Scanner] LLM scan failed for '{filename}': {e}")
            return None

    def format_scanner_results(
        self,
        results: list[dict],
        max_chars: int = 0,
    ) -> str:
        """
        Format scanner results into a context string for LLM consumption.
        Respects context_max_chars to prevent context window overflow.

        Args:
            results: List of {filename, excerpts, doc_id} from scan.
            max_chars: Override max context chars (0 = use settings.context_max_chars).

        Returns:
            Formatted context string, truncated if necessary.
        """
        if not results:
            return "Không tìm thấy dữ liệu liên quan trong kho."

        limit = max_chars if max_chars > 0 else settings.context_max_chars

        # Build all excerpt blocks
        blocks = []
        for result in results:
            filename = result.get("filename", "Không rõ nguồn")
            excerpts = result.get("excerpts", [])
            meta_parts = [
                f"ưu tiên: {result.get('priority')}" if result.get("priority") else "",
                f"loại: {result.get('document_type')}" if result.get("document_type") else "",
                f"lĩnh vực: {result.get('field')}" if result.get("field") else "",
                f"giá trị pháp lý: {result.get('legal_level')}" if result.get("legal_level") else "",
                f"thời gian: {result.get('document_date')}" if result.get("document_date") else "",
            ]
            meta = "; ".join(part for part in meta_parts if part)

            for i, excerpt in enumerate(excerpts, 1):
                header = f"[Tài liệu: {filename} — Trích đoạn {i}"
                if meta:
                    header += f" — {meta}"
                header += "]"
                block = f"{header}\n{excerpt}"
                blocks.append(block)

        # Join and check length
        separator = "\n\n---\n\n"
        full_text = separator.join(blocks)

        if limit <= 0 or len(full_text) <= limit:
            logger.info(
                f"[Scanner] Context: {len(blocks)} blocks, "
                f"{len(full_text)} chars (within limit {limit})"
            )
            return full_text

        # Context exceeds limit — truncate smartly
        # Strategy: keep as many complete blocks as possible
        truncated_blocks = []
        current_len = 0
        sep_len = len(separator)

        for block in blocks:
            needed = len(block) + (sep_len if truncated_blocks else 0)
            if current_len + needed > limit:
                # Check if we can fit a truncated version of this block
                remaining = limit - current_len - sep_len - 100  # reserve for note
                if remaining > 200 and not truncated_blocks:
                    # At least include something
                    truncated_blocks.append(block[:remaining] + "\n[... nội dung bị cắt do giới hạn context]")
                break
            truncated_blocks.append(block)
            current_len += needed

        # Add truncation note
        dropped = len(blocks) - len(truncated_blocks)
        result_text = separator.join(truncated_blocks)

        if dropped > 0:
            result_text += (
                f"\n\n[⚠️ Còn {dropped} trích đoạn khác không hiển thị "
                f"do giới hạn context ({limit:,} chars). "
                f"Tổng gốc: {len(full_text):,} chars]"
            )

        logger.warning(
            f"[Scanner] Context TRUNCATED: {len(blocks)} blocks → "
            f"{len(truncated_blocks)} blocks, "
            f"{len(full_text):,} chars → {len(result_text):,} chars "
            f"(limit={limit:,})"
        )
        return result_text

    @staticmethod
    def _result_priority_key(result: dict) -> tuple[int, int]:
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        priority = str(result.get("priority", "medium")).lower()
        date = str(result.get("document_date", ""))
        years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", date)]
        newest_year = max(years) if years else 0
        return (priority_rank.get(priority, 1), -newest_year)


# Singleton
document_scanner = DocumentScanner()
