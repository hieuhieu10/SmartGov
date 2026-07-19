"""Tạo bản tổng hợp ý kiến góp ý theo mẫu.

Luồng:
- Lấy Markdown các văn bản trong folder "draft" (Bản dự thảo) làm cơ sở cho phần
  thể thức (cơ quan ban hành, địa danh, tên dự thảo).
- Lấy Markdown các văn bản trong folder "feedback" (Văn bản góp ý) làm nội dung
  điền vào bảng.
- Gọi AI service sinh cấu trúc JSON (metadata + sections), render ra .docx đúng
  thể thức hành chính (quốc hiệu, tiêu ngữ, tiêu đề, bảng 4 cột), rồi lưu thành
  một document mới trong folder "summary" (Bảng tổng hợp ý kiến).
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from app import database as db
from app.config import settings
from app.services.ai_client import ai_client
from app.services.draft_docx_updater import update_revised_draft_docx
from app.services.nghi_dinh_30_renderer import render_revised_draft
from app.services.repository_service import repository_service

logger = logging.getLogger(__name__)

DRAFT_FOLDER = "draft"
FEEDBACK_FOLDER = "feedback"
SUMMARY_FOLDER = "summary"
FINAL_FOLDER = "final"

QUOC_HIEU = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
TIEU_NGU = "Độc lập - Tự do - Hạnh phúc"
TITLE_PREFIX = "BẢNG TỔNG HỢP Ý KIẾN, TIẾP THU, GIẢI TRÌNH Ý KIẾN GÓP Ý"

TABLE_HEADERS = [
    "NHÓM VẤN ĐỀ, ĐIỀU, KHOẢN",
    "CHỦ THỂ GÓP Ý",
    "NỘI DUNG GÓP Ý",
    "NỘI DUNG TIẾP THU, GIẢI TRÌNH",
]
ROW_KEYS = ["nhom_van_de", "chu_the_gop_y", "noi_dung_gop_y", "noi_dung_tiep_thu_giai_trinh"]


def _referenced_articles(markdown: str) -> list[str]:
    """Lấy các Điều được nêu rõ trong bảng tổng hợp để kiểm tra tài liệu nguồn."""
    return sorted(set(re.findall(r"\bđiều\s+(\d+)\b", markdown, flags=re.IGNORECASE)), key=int)


def _add_line(cell_or_doc, text: str, *, bold=False, italic=False, size=13,
              align=WD_ALIGN_PARAGRAPH.CENTER):
    para = cell_or_doc.add_paragraph()
    para.alignment = align
    para.paragraph_format.space_after = Pt(0)
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = "Times New Roman"
    return para


def _date_line(metadata: dict) -> str:
    dia_danh = (metadata.get("dia_danh") or "").strip()
    ngay = (metadata.get("ngay_ban_hanh") or "").strip()
    if not ngay:
        now = datetime.now()
        ngay = f"ngày {now.day} tháng {now.month} năm {now.year}"
    return f"{dia_danh}, {ngay}" if dia_danh else ngay


def _render_header(doc: DocxDocument, metadata: dict) -> None:
    """Render khối đầu văn bản: cơ quan ban hành | quốc hiệu, tiêu ngữ, ngày."""
    table = doc.add_table(rows=1, cols=2)  # bảng không viền (không đặt style)
    table.autofit = True
    left, right = table.rows[0].cells

    # Cột trái: cơ quan chủ quản + cơ quan ban hành (lấy từ dự thảo)
    left.paragraphs[0].text = ""
    chu_quan = (metadata.get("co_quan_chu_quan") or "").strip()
    ban_hanh = (metadata.get("co_quan_ban_hanh") or "").strip()
    if chu_quan:
        _add_line(left, chu_quan.upper(), size=12)
    _add_line(left, (ban_hanh or "…").upper(), bold=True, size=12)
    _add_line(left, "_______________", size=12)

    # Cột phải: quốc hiệu + tiêu ngữ (hằng số) + địa danh, ngày
    right.paragraphs[0].text = ""
    _add_line(right, QUOC_HIEU, bold=True, size=12)
    _add_line(right, TIEU_NGU, bold=True, size=13)
    _add_line(right, "___________________", size=12)
    _add_line(right, _date_line(metadata), italic=True, size=13)


def _render_title(doc: DocxDocument, metadata: dict) -> None:
    _add_line(doc, TITLE_PREFIX, bold=True, size=14)
    ten_du_thao = (metadata.get("ten_du_thao") or "").strip()
    if ten_du_thao:
        _add_line(doc, f"ĐỐI VỚI DỰ THẢO {ten_du_thao.upper()}", bold=True, size=14)
    _add_line(doc, "____________", size=12)
    doc.add_paragraph()


def _distinct_chu_the(summary: dict) -> int:
    names = set()
    for section in summary.get("sections") or []:
        for row in section.get("rows") or []:
            name = (row.get("chu_the_gop_y") or "").strip()
            if name:
                names.add(name)
    return len(names)


def _render_modau(doc: DocxDocument, summary: dict) -> None:
    """Render phần mở đầu: căn cứ + thống kê đơn vị góp ý/thống nhất."""
    mo_dau = summary.get("mo_dau") or {}
    metadata = summary.get("metadata") or {}

    can_cu = (mo_dau.get("can_cu") or "").strip()
    if not can_cu:
        ten = (metadata.get("ten_du_thao") or "dự thảo").strip()
        can_cu = (
            "Căn cứ Luật Ban hành văn bản quy phạm pháp luật, cơ quan chủ trì soạn "
            f"thảo đã tổ chức lấy ý kiến đối với dự thảo {ten}. Kết quả:"
        )
    _add_line(doc, can_cu, size=13, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    _add_line(
        doc,
        "1. Tổng số cơ quan, tổ chức, cá nhân đã gửi xin ý kiến, góp ý: …… đơn vị",
        size=13, align=WD_ALIGN_PARAGRAPH.LEFT,
    )
    so_van_ban = mo_dau.get("so_van_ban_gop_y")
    if isinstance(so_van_ban, int):
        _add_line(
            doc, f"- Tổng số văn bản góp ý nhận được: {so_van_ban} văn bản",
            size=13, align=WD_ALIGN_PARAGRAPH.LEFT,
        )
    _add_line(doc, "2. Kết quả cụ thể như sau:", size=13, align=WD_ALIGN_PARAGRAPH.LEFT)

    _add_line(
        doc, "2.1. Đơn vị thống nhất với nội dung dự thảo:",
        size=13, align=WD_ALIGN_PARAGRAPH.LEFT,
    )
    parts = []
    for dv in mo_dau.get("don_vi_thong_nhat") or []:
        ten = (dv.get("ten") or "").strip()
        if not ten:
            continue
        cv = (dv.get("so_cong_van") or "").strip()
        ng = (dv.get("ngay") or "").strip()
        ref = ""
        if cv or ng:
            ref = " (Công văn số " + cv + (f" ngày {ng}" if ng else "") + ")"
        parts.append(ten + ref)
    if parts:
        _add_line(doc, "; ".join(parts) + ".", size=13, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    _add_line(
        doc, "- Đơn vị không gửi văn bản góp ý xem như thống nhất nội dung dự thảo.",
        size=13, align=WD_ALIGN_PARAGRAPH.LEFT,
    )

    so_y_kien = _distinct_chu_the(summary)
    tail = f": {so_y_kien} đơn vị." if so_y_kien else "."
    _add_line(
        doc, f"2.2. Đơn vị đóng góp ý kiến cho dự thảo{tail}",
        bold=True, size=13, align=WD_ALIGN_PARAGRAPH.LEFT,
    )
    doc.add_paragraph()


def _render_section(doc: DocxDocument, section: dict) -> None:
    rows = section.get("rows") or []
    if not rows:
        return
    tieu_de = (section.get("tieu_de") or "").strip()
    if tieu_de:
        _add_line(doc, tieu_de, bold=True, size=13, align=WD_ALIGN_PARAGRAPH.LEFT)

    table = doc.add_table(rows=1, cols=len(TABLE_HEADERS))
    table.style = "Table Grid"
    for cell, header in zip(table.rows[0].cells, TABLE_HEADERS):
        cell.text = ""
        _add_line(cell, header, bold=True, size=12)

    for row in rows:
        cells = table.add_row().cells
        for cell, key in zip(cells, ROW_KEYS):
            cell.text = ""
            align = (
                WD_ALIGN_PARAGRAPH.CENTER
                if key in ("nhom_van_de", "chu_the_gop_y")
                else WD_ALIGN_PARAGRAPH.LEFT
            )
            _add_line(cell, str(row.get(key, "") or ""), size=12, align=align)
    doc.add_paragraph()


def _render_docx(summary: dict, output_path: str) -> None:
    """Render cấu trúc JSON (metadata + sections) thành .docx khổ ngang A4."""
    metadata = summary.get("metadata") or {}
    sections = summary.get("sections") or []

    doc = DocxDocument()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.left_margin = section.right_margin = Cm(2)
    section.top_margin = section.bottom_margin = Cm(1.5)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)

    _render_header(doc, metadata)
    _render_title(doc, metadata)
    _render_modau(doc, summary)
    for sec in sections:
        _render_section(doc, sec)

    doc.save(output_path)


_MARKDOWN_TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")
_MARKDOWN_INLINE = re.compile(r"(\*\*.+?\*\*|__.+?__|`.+?`|(?<!\*)\*[^*]+?\*(?!\*)|(?<!_)_[^_]+?_(?!_))")


def _markdown_table_cells(line: str) -> list[str]:
    """Tách một hàng bảng Markdown, bỏ hai ký tự | ở biên nếu có."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip().replace(r"\|", "|") for cell in text.split("|")]


def _is_markdown_table_separator(line: str) -> bool:
    cells = _markdown_table_cells(line)
    return bool(cells) and all(_MARKDOWN_TABLE_SEPARATOR.fullmatch(cell) for cell in cells)


def _add_markdown_runs(paragraph, text: str, *, size: int = 13) -> None:
    """Ghi Markdown inline cơ bản vào paragraph Word, không để lộ dấu **/*."""
    cursor = 0
    for match in _MARKDOWN_INLINE.finditer(text):
        if match.start() > cursor:
            run = paragraph.add_run(text[cursor:match.start()])
            run.font.name = "Times New Roman"
            run.font.size = Pt(size)
        token = match.group(0)
        if token.startswith(("**", "__")):
            value, bold, italic = token[2:-2], True, False
        elif token.startswith("`"):
            value, bold, italic = token[1:-1], False, False
        else:
            value, bold, italic = token[1:-1], False, True
        run = paragraph.add_run(value)
        run.bold = bold
        run.italic = italic
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
        cursor = match.end()
    if cursor < len(text):
        run = paragraph.add_run(text[cursor:])
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)


def _add_revised_paragraph(doc, text: str, *, bold: bool = False, size: int = 13,
                           align=WD_ALIGN_PARAGRAPH.JUSTIFY) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(6)
    _add_markdown_runs(paragraph, text, size=size)
    for run in paragraph.runs:
        if bold:
            run.bold = True


def _render_revised_table(doc: DocxDocument, headers: list[str], rows: list[list[str]]) -> None:
    """Render bảng Markdown thành bảng Word như phần bảng tổng hợp ở bước 3."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = ""
        _add_line(cell, header, bold=True, size=12)

    for values in rows:
        cells = table.add_row().cells
        for index, cell in enumerate(cells):
            cell.text = ""
            value = values[index] if index < len(values) else ""
            align = WD_ALIGN_PARAGRAPH.CENTER if index == 0 else WD_ALIGN_PARAGRAPH.LEFT
            paragraph = _add_line(cell, "", size=12, align=align)
            _add_markdown_runs(paragraph, value, size=12)
    doc.add_paragraph()


def _render_revised_draft_docx(markdown: str, output_path: str) -> None:
    """Xuất DOCX dự thảo với tiêu đề, đoạn và bảng Word thay vì văn bản Markdown thô."""
    doc = DocxDocument()
    section = doc.sections[0]
    section.left_margin = section.right_margin = Cm(2.5)
    section.top_margin = section.bottom_margin = Cm(2)
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)

    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        text = lines[index].strip()
        if not text:
            index += 1
            continue

        # Một bảng Markdown gồm hàng tiêu đề và hàng phân cách ---.
        if text.startswith("|") and index + 1 < len(lines) and _is_markdown_table_separator(lines[index + 1]):
            headers = _markdown_table_cells(text)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_markdown_table_cells(lines[index]))
                index += 1
            _render_revised_table(doc, headers, rows)
            continue

        if text.startswith("### "):
            _add_revised_paragraph(doc, text[4:], bold=True, size=13, align=WD_ALIGN_PARAGRAPH.LEFT)
        elif text.startswith("## "):
            _add_revised_paragraph(doc, text[3:], bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
        elif text.startswith("# "):
            _add_revised_paragraph(doc, text[2:], bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
        elif text.startswith(("- ", "* ")):
            _add_revised_paragraph(doc, text[2:], size=13, align=WD_ALIGN_PARAGRAPH.LEFT)
        else:
            _add_revised_paragraph(doc, text, size=13)
        index += 1
    doc.save(output_path)


def _build_markdown(summary: dict) -> str:
    """Bản Markdown để lưu markdown_content (phục vụ preview/chỉnh sửa)."""
    metadata = summary.get("metadata") or {}
    mo_dau = summary.get("mo_dau") or {}
    lines = [f"# {TITLE_PREFIX}"]
    ten = (metadata.get("ten_du_thao") or "").strip()
    if ten:
        lines.append(f"**Đối với dự thảo:** {ten}")
    can_cu = (mo_dau.get("can_cu") or "").strip()
    if can_cu:
        lines.append(f"\n{can_cu}")
    so_van_ban = mo_dau.get("so_van_ban_gop_y")
    if isinstance(so_van_ban, int):
        lines.append(f"- Tổng số văn bản góp ý nhận được: {so_van_ban} văn bản")
    so_y_kien = _distinct_chu_the(summary)
    if so_y_kien:
        lines.append(f"- Đơn vị đóng góp ý kiến cho dự thảo: {so_y_kien} đơn vị")
    for section in summary.get("sections") or []:
        rows = section.get("rows") or []
        if not rows:
            continue
        lines.append(f"\n## {section.get('tieu_de', '')}")
        lines.append("| " + " | ".join(TABLE_HEADERS) + " |")
        lines.append("| " + " | ".join(["---"] * len(TABLE_HEADERS)) + " |")
        for row in rows:
            cells = [str(row.get(k, "") or "").replace("\n", " ").replace("|", "\\|")
                     for k in ROW_KEYS]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


class FeedbackSummaryService:
    async def create_summary(
        self,
        repo_id: str,
        user_id: str,
        feedback_document_id: str | None = None,
        draft_document_id: str | None = None,
        feedback_repository_id: str | None = None,
    ) -> dict:
        """Tạo bản tổng hợp từ một dự thảo và các góp ý của kho được chọn.

        Trả về document mới (folder summary). Raise ValueError nếu không có
        văn bản góp ý đã xử lý.
        """
        await repository_service.verify_ownership(repo_id, user_id)

        all_docs = await db.get_documents_by_repository(repo_id)
        feedback_ids = [
            doc["id"] for doc in all_docs
            if (doc.get("folder_key") or "draft") == FEEDBACK_FOLDER
        ]
        feedback_repo_id = feedback_repository_id or repo_id
        if feedback_repository_id:
            feedback_source_docs = await db.get_documents_by_repository(feedback_repo_id)
            feedback_ids = [
                doc["id"]
                for doc in feedback_source_docs
                if (doc.get("folder_key") or "draft") not in {SUMMARY_FOLDER, "final"}
            ]
        if feedback_document_id:
            if feedback_document_id not in feedback_ids:
                raise ValueError("Văn bản góp ý đã chọn không thuộc kho nguồn")
            feedback_ids = [feedback_document_id]
        draft_ids = [
            doc["id"] for doc in all_docs
            if (doc.get("folder_key") or "draft") == DRAFT_FOLDER
        ]
        if draft_document_id:
            if draft_document_id not in {doc["id"] for doc in all_docs}:
                raise ValueError("Tài liệu dự thảo đã chọn không thuộc kho nguồn")
            draft_ids = [draft_document_id]
        if not feedback_ids:
            raise ValueError("Chưa có văn bản góp ý nào trong kho")

        feedback_rows = await db.get_documents_markdown_by_repository(feedback_repo_id, feedback_ids)
        feedback_documents = [
            {"filename": row["filename"], "markdown_content": row.get("markdown_content", "")}
            for row in feedback_rows
            if (row.get("markdown_content") or "").strip()
        ]
        if not feedback_documents:
            raise ValueError(
                "Các văn bản góp ý chưa được xử lý xong, chưa có nội dung để tổng hợp"
            )

        draft_documents: list[dict] = []
        if draft_ids:
            draft_rows = await db.get_documents_markdown_by_repository(repo_id, draft_ids)
            draft_documents = [
                {"filename": row["filename"], "markdown_content": row.get("markdown_content", "")}
                for row in draft_rows
                if (row.get("markdown_content") or "").strip()
            ]

        summary = await ai_client.consolidate_feedback(
            repo_id, feedback_documents, draft_documents
        )
        if not summary or not (summary.get("sections") or []):
            raise ValueError("AI không trả về nội dung tổng hợp")

        # Số văn bản góp ý thực nhận do BE nắm chính xác (không để model tự đếm).
        summary.setdefault("mo_dau", {})["so_van_ban_gop_y"] = len(feedback_documents)

        markdown = _build_markdown(summary)

        doc_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Bảng tổng hợp ý kiến {timestamp}.docx"
        safe_filename = f"{doc_id}_{filename}"
        repo_dir = Path(settings.repo_files_dir) / repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        stored_path = str(repo_dir / safe_filename)
        _render_docx(summary, stored_path)
        file_size = Path(stored_path).stat().st_size

        doc = await db.create_document(
            repository_id=repo_id,
            filename=filename,
            stored_path=stored_path,
            file_size=file_size,
            file_type="docx",
            folder_key=SUMMARY_FOLDER,
            doc_id=doc_id,
            markdown_content=markdown,
            processing_status="completed",
            progress_message="",
            processed_at=datetime.now(),
        )
        logger.info("Created feedback summary %s for repo %s", doc_id, repo_id)
        return doc

    async def revise_draft(
        self, repo_id: str, user_id: str, draft_document_id: str, summary_document_id: str,
    ) -> dict:
        """Tạo bản dự thảo hoàn thiện mới từ dự thảo gốc và bảng tổng hợp."""
        await repository_service.verify_ownership(repo_id, user_id)
        documents = await db.get_documents_by_repository(repo_id)
        documents_by_id = {doc["id"]: doc for doc in documents}
        draft_doc = documents_by_id.get(draft_document_id)
        summary_doc = documents_by_id.get(summary_document_id)
        if not draft_doc or (draft_doc.get("folder_key") or DRAFT_FOLDER) != DRAFT_FOLDER:
            raise ValueError("Bản dự thảo đã chọn không thuộc kho hoặc không phải bản dự thảo")
        if not summary_doc or summary_doc.get("folder_key") != SUMMARY_FOLDER:
            raise ValueError("Bảng tổng hợp đã chọn không thuộc kho")

        rows = await db.get_documents_markdown_by_repository(
            repo_id, [draft_document_id, summary_document_id]
        )
        content_by_id = {row["id"]: row for row in rows}
        draft_source = content_by_id.get(draft_document_id) or {}
        summary_source = content_by_id.get(summary_document_id) or {}
        draft_markdown = str(draft_source.get("markdown_content") or "")
        summary_markdown = str(summary_source.get("markdown_content") or "")
        referenced_articles = _referenced_articles(summary_markdown)
        missing_articles = [
            article for article in referenced_articles
            if not re.search(rf"\bđiều\s+{re.escape(article)}\b", draft_markdown, re.IGNORECASE)
        ]
        if missing_articles:
            raise ValueError(
                "Bản dự thảo đã chọn không chứa "
                f"Điều {', '.join(missing_articles)} được nêu trong bảng góp ý. "
                "Hãy chọn hoặc tải lên bản dự thảo đầy đủ cần hoàn thiện, không chọn công văn góp ý/chủ trương."
            )
        revised_markdown = await ai_client.revise_draft_from_summary(
            repo_id,
            {"filename": draft_doc["filename"], "markdown_content": draft_markdown},
            {"filename": summary_doc["filename"], "markdown_content": summary_markdown},
        )
        if not revised_markdown.strip():
            raise ValueError("AI không trả về bản dự thảo đã cập nhật")

        doc_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Dự thảo hoàn thiện {timestamp}.docx"
        repo_dir = Path(settings.repo_files_dir) / repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        stored_path = str(repo_dir / f"{doc_id}_{filename}")
        # Ưu tiên sao chép và vá trực tiếp DOCX gốc theo từng Điều: cách này giữ
        # nguyên hoàn toàn thể thức, bảng, header/footer, chữ ký và định dạng run.
        # Mẫu Nghị định 30 chỉ là phương án cho đầu vào không phải DOCX.
        if Path(draft_doc["stored_path"]).suffix.casefold() == ".docx":
            update_result = update_revised_draft_docx(
                draft_doc["stored_path"], revised_markdown, stored_path,
            )
            logger.info(
                "Updated draft DOCX in place: %s/%s articles changed",
                update_result["updated_articles"], update_result["matched_articles"],
            )
        else:
            render_revised_draft(
                revised_markdown,
                draft_doc["stored_path"],
                stored_path,
                fallback_title=Path(draft_doc["filename"]).stem,
            )
        file_size = Path(stored_path).stat().st_size
        doc = await db.create_document(
            repository_id=repo_id,
            filename=filename,
            stored_path=stored_path,
            file_size=file_size,
            file_type="docx",
            folder_key=FINAL_FOLDER,
            doc_id=doc_id,
            markdown_content=revised_markdown,
            processing_status="completed",
            progress_message="",
            processed_at=datetime.now(),
        )
        logger.info("Created revised draft %s from draft %s", doc_id, draft_document_id)
        return doc


feedback_summary_service = FeedbackSummaryService()
