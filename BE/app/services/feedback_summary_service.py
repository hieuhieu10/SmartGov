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
from app.services.repository_service import repository_service

logger = logging.getLogger(__name__)

DRAFT_FOLDER = "draft"
FEEDBACK_FOLDER = "feedback"
SUMMARY_FOLDER = "summary"

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


feedback_summary_service = FeedbackSummaryService()
