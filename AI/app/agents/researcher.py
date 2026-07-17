"""
Researcher Agent — Scan repository documents for relevant content.

Uses DocumentScanner to sequentially scan each document in the repository,
extracting relevant excerpts based on the Planner's outline.
"""

import json
import logging

from app.config import settings
from app.services.document_scanner import document_scanner

logger = logging.getLogger(__name__)


async def researcher_node(state: dict) -> dict:
    """
    Researcher Agent: scan repository documents for relevant data.

    Input state: plan, warehouse_ids
    Output state: scanner_results, research_context
    """
    plan = state.get("plan", {})
    warehouse_ids = state.get("warehouse_ids", [])
    selected_document_ids = state.get("selected_document_ids", []) or []
    user_request = state.get("user_request", "")
    trich_yeu = state.get("trich_yeu", "")
    template_outline = state.get("template_outline", {})

    if not warehouse_ids:
        logger.warning("[Researcher] No warehouse_ids provided")
        return {
            "scanner_results": [],
            "research_context": "Không có kho dữ liệu nào được chọn.",
        }

    section_queries = _build_section_queries(plan, user_request, trich_yeu, template_outline)

    all_results = []
    section_contexts = []
    for section_query in section_queries:
        section_results = []
        for repo_id in warehouse_ids:
            results = await document_scanner.scan_repository(
                repo_id=repo_id,
                outline=section_query["query"],
                document_ids=selected_document_ids,
            )
            section_results.extend(results)
            all_results.extend(results)
        section_contexts.append({
            "title": section_query["title"],
            "context": document_scanner.format_scanner_results(section_results, max_chars=60000),
        })

    research_context = _format_section_contexts(section_contexts)

    if not all_results:
        research_context = (
            "Không tìm thấy dữ liệu liên quan trong kho. "
            "Hãy soạn văn bản dựa trên yêu cầu của người dùng, "
            "ghi chú các phần cần bổ sung thêm dữ liệu."
        )

    logger.info(
        f"[Researcher] Scan complete: {len(all_results)} relevant documents, "
        f"context={len(research_context)} chars "
        f"(limit={settings.context_max_chars})"
    )

    return {
        "scanner_results": all_results,
        "research_context": research_context,
    }


def _build_outline_from_plan(
    plan: dict,
    user_request: str,
    trich_yeu: str,
    template_outline: dict | None = None,
) -> str:
    """Build an outline string from the planner's output for the scanner."""
    parts = []

    if trich_yeu:
        parts.append(f"Trích yếu: {trich_yeu}")
    if user_request:
        parts.append(f"Yêu cầu nội dung: {user_request}")
    if template_outline:
        parts.append("\nĐầu mục mẫu cùng loại đã trích xuất:")
        for heading in template_outline.get("headings", [])[:30]:
            level = heading.get("level", 1)
            marker = heading.get("marker", "")
            title = heading.get("title", "")
            indent = "  " * max(int(level or 1) - 1, 0)
            parts.append(f"{indent}- level {level}: {marker}. {title}" if marker else f"{indent}- level {level}: {title}")

    sections = plan.get("sections", [])
    if sections:
        parts.append("\nDàn ý:")
        for i, section in enumerate(sections, 1):
            title = section.get("title", "")
            key_points = section.get("key_points", [])
            parts.append(f"  {i}. {title}")
            for point in key_points:
                parts.append(f"     - {point}")

    summary = plan.get("summary", "")
    if summary and not sections:
        parts.append(f"\nTóm tắt dàn ý: {summary}")

    return "\n".join(parts) if parts else user_request


def _build_section_queries(
    plan: dict,
    user_request: str,
    trich_yeu: str,
    template_outline: dict | None = None,
) -> list[dict]:
    """Build one concrete retrieval task per planned section."""
    sections = plan.get("sections", []) if isinstance(plan, dict) else []
    if not sections:
        return [{
            "title": "Nội dung chính",
            "query": _build_outline_from_plan(plan, user_request, trich_yeu, template_outline),
        }]

    template_part = ""
    if template_outline:
        lines = ["Đầu mục mẫu cùng loại:"]
        for heading in template_outline.get("headings", [])[:30]:
            marker = heading.get("marker", "")
            marker_text = f"{marker}. " if marker else ""
            lines.append(f"- level {heading.get('level', 1)}: {marker_text}{heading.get('title', '')}")
        template_part = "\n".join(lines)

    tasks = []
    for section in sections:
        title = section.get("title", "Nội dung")
        key_points = section.get("key_points", [])
        search_queries = section.get("search_queries", [])
        query_lines = [
            f"Trích yếu văn bản cần soạn: {trich_yeu}",
            f"Yêu cầu nội dung chính của người dùng: {user_request}",
            template_part,
            f"Mục cần tìm dữ liệu: {title}",
            "Các ý cần làm rõ:",
            *[f"- {point}" for point in key_points if point],
            "Các truy vấn cụ thể cần thực hiện:",
            *[f"- {query}" for query in search_queries if query],
            "Yêu cầu trích xuất: lấy căn cứ, số liệu, nhiệm vụ, thời hạn, cơ quan chủ trì/phối hợp và nội dung liên quan trực tiếp đến mục này.",
        ]
        tasks.append({
            "title": title,
            "query": "\n".join(line for line in query_lines if line),
        })
    return tasks


def _format_section_contexts(section_contexts: list[dict]) -> str:
    blocks = ["--- CHI TIẾT NGUỒN TRÍCH DẪN ---"]
    found_any = False
    for item in section_contexts:
        title = item.get("title", "Nội dung")
        context = item.get("context", "").strip()
        if not context or context == "Không tìm thấy dữ liệu liên quan trong kho.":
            continue
        found_any = True
        blocks.append(f"### {title}\n{context}")
    if not found_any:
        return (
            "Không tìm thấy dữ liệu liên quan trong kho. "
            "Hãy soạn văn bản dựa trên yêu cầu của người dùng, "
            "ghi chú các phần cần bổ sung thêm dữ liệu."
        )
    return "\n\n---\n\n".join(blocks)
