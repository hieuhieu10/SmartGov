"""
STTNB Word Exporter — Generate .docx documents.

Supports:
  1. Biên bản họp (meeting minutes)
  2. Công văn
  3. Quyết định
  4. Kế hoạch
  5. Thông báo
  6. Tờ trình
  7. Báo cáo

All output follows NĐ 30/2020/NĐ-CP:
  - Khổ A4, font Times New Roman, Unicode
  - Lề: trái 3cm, phải 2cm, trên/dưới 2cm
  - Quốc hiệu — Tiêu ngữ đúng chuẩn
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from app.config import settings
from app.models import DocumentType

logger = logging.getLogger(__name__)


# ─── Shared Utilities ────────────────────────────────────────────────

def _set_cell_border(cell, **kwargs):
    """Set cell borders. Usage: _set_cell_border(cell, top=..., bottom=..., ...)"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for edge, val in kwargs.items():
        element = OxmlElement(f'w:{edge}')
        element.set(qn('w:val'), val.get('val', 'single'))
        element.set(qn('w:sz'), val.get('sz', '4'))
        element.set(qn('w:color'), val.get('color', '000000'))
        element.set(qn('w:space'), val.get('space', '0'))
        borders.append(element)
    tcPr.append(borders)


def _remove_cell_borders(cell):
    """Remove all borders from a table cell."""
    no_border = {'val': 'none', 'sz': '0', 'color': 'FFFFFF'}
    _set_cell_border(cell,
        top=no_border, bottom=no_border,
        start=no_border, end=no_border,
        left=no_border, right=no_border)


def _add_run(paragraph, text, bold=False, italic=False, size=14, 
             font_name="Times New Roman", color=None, underline=False):
    """Add a formatted run to a paragraph."""
    run = paragraph.add_run(text)
    run.font.name = font_name
    run.font.size = Pt(size)
    if bold:
        run.font.bold = True
    if italic:
        run.font.italic = True
    if underline:
        run.font.underline = True
    if color:
        run.font.color.rgb = color
    return run


def _setup_document():
    """Create a Document with standard A4 setup per NĐ 30/2020."""
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2)
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(14)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.line_spacing = 1.0
    return doc


def _add_header_table(doc, co_quan_chu_quan: str, ten_don_vi: str,
                      so_van_ban: str = "", ky_hieu: str = ""):
    """Add standard header table: Cơ quan | Quốc hiệu."""
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for row in table.rows:
        for cell in row.cells:
            _remove_cell_borders(cell)

    # Left cell: Cơ quan
    left_cell = table.cell(0, 0)
    left_cell.width = Cm(7)

    if co_quan_chu_quan:
        p = left_cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, co_quan_chu_quan.upper(), size=14)

    ten_dv = ten_don_vi.upper() if ten_don_vi else "_______________"
    p = left_cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p, ten_dv, bold=True, size=14)

    # Số ký hiệu
    p = left_cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = left_cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    so_ky_hieu = so_van_ban if so_van_ban else "         "
    ky_hieu_text = ky_hieu if ky_hieu else "..."
    _add_run(p, f"Số: {so_ky_hieu}/{ky_hieu_text}", size=14)

    # Right cell: Quốc hiệu
    right_cell = table.cell(0, 1)
    right_cell.width = Cm(9)

    p = right_cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p, "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", bold=True, size=14)

    p = right_cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p, "Độc lập - Tự do - Hạnh phúc", bold=True, size=14, underline=True)

    p = right_cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Ngày tháng
    now = datetime.now()
    p = right_cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p, f"......., ngày {now.day} tháng {now.month} năm {now.year}",
             italic=True, size=14)


def _add_signature_block(doc, nguoi_ky: str = "", chuc_vu: str = "",
                         label: str = ""):
    """Add a right-aligned signature block."""
    doc.add_paragraph()  # spacing

    # Right-aligned label + chuc vu
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if label:
        _add_run(p, label, bold=True, size=14)
    elif chuc_vu:
        _add_run(p, chuc_vu.upper(), bold=True, size=14)

    # Signature space
    for _ in range(3):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _add_run(p, "", size=14)

    # Name
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    ten = nguoi_ky if nguoi_ky else "_______________"
    _add_run(p, ten, bold=True, size=14)


def _add_noi_nhan(doc, noi_nhan_list: list[str] = None):
    """Add Nơi nhận section."""
    if noi_nhan_list is None:
        noi_nhan_list = ["Như trên;", "Lưu: VT."]

    p = doc.add_paragraph()
    _add_run(p, "Nơi nhận:", bold=True, italic=True, size=11)

    for nn in noi_nhan_list:
        p = doc.add_paragraph()
        _add_run(p, f"- {nn}", italic=True, size=11)


def _normalize_noi_nhan(value, default: list[str] | None = None) -> list[str]:
    """Normalize recipients from a string/list while avoiding duplicate bullets."""
    if not value:
        return default or ["Như trên;", "Lưu: VT."]
    if isinstance(value, str):
        items = value.splitlines()
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = [str(value)]
    normalized = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        item = item.lstrip("-• ").strip()
        normalized.append(item)
    if normalized and not any("lưu:" in item.lower() for item in normalized):
        normalized.append("Lưu: VT.")
    return normalized or (default or ["Như trên;", "Lưu: VT."])


def _add_section_title(doc, text: str):
    """Add a bold, justified section title with indent. Strips markdown bold stars."""
    import re
    # Strip markdown stars if present
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Cm(1.27)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.0
    _add_run(p, text, bold=True, size=14)


def _clean_section_content(text: str, section_heading: str = "") -> list[str]:
    """Clean AI-generated content: remove duplicate heading and split into paragraphs.

    Handles:
    - Duplicate section headings (with/without 'Phan' prefix)
    - Smart paragraph splitting on numbered items
    - Merging orphan number lines ('1.' on its own) back with their content
    """
    import re

    if not text or not text.strip():
        return []

    text = text.strip()

    # Remove duplicate section heading at the start
    # AI may return: "I. MUC DICH..." or "Phan I. MUC DICH..." etc.
    if section_heading:
        heading_clean = section_heading.strip().rstrip(".:").strip()
        heading_without_roman = re.sub(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s*", "", heading_clean, flags=re.IGNORECASE)
        for duplicate_heading in (heading_clean, f"Phần {heading_clean}", heading_without_roman):
            if duplicate_heading:
                text = re.sub(
                    rf"^\s*{re.escape(duplicate_heading)}\s*[\.:]?\s*",
                    "",
                    text,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip()
        m = re.match(r'^([IVXLC]+)\.\s*', heading_clean, re.IGNORECASE)
        if m:
            numeral = m.group(1)
            rest = re.escape(heading_clean[m.end():].strip())
            pattern = rf'^(?:Phần\s+)?{re.escape(numeral)}\.\s*{rest}[\.:]?\s*'
            text = re.sub(pattern, '', text, count=1, flags=re.IGNORECASE).strip()

    if not text:
        return []

    # If text already has newlines, split on them
    if "\n" in text:
        raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
    else:
        # Smart split: detect numbered items followed by text
        parts = re.split(r'(?=\d+[\.\)]\s\S|[-–•]\s\S)', text)
        raw_lines = [p.strip() for p in parts if p.strip()]

    # Merge orphan number-only lines with the next line
    # E.g. ["1.", "Muc dich: ..."] -> ["1. Muc dich: ..."]
    result = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if re.match(r'^\d+[\.\)]$', line) and i + 1 < len(raw_lines):
            result.append(f"{line} {raw_lines[i + 1]}")
            i += 2
        else:
            line = re.sub(r"^(\s*\d+[\.\)]\s*)Nội\s*dung\s*:\s*", r"\1", line, flags=re.IGNORECASE)
            result.append(line)
            i += 1

    cleaned_result = result if result else [text]
    cleaned_result = _normalize_plan_subsection_numbering(cleaned_result, section_heading)
    return [_normalize_body_line_case(line) for line in cleaned_result]


def _normalize_plan_subsection_numbering(lines: list[str], section_heading: str = "") -> list[str]:
    """Add required subsection numbering for plan sections when the LLM omits it."""
    heading = (section_heading or "").lower()
    if "mục đích" not in heading and "yêu cầu" not in heading:
        return lines

    normalized = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            normalized.append(line)
            continue

        if re.match(r"^mục\s*đích\b", stripped, re.IGNORECASE):
            normalized.append(re.sub(r"^mục\s*đích\s*[:\-–]?\s*", "1. Mục đích: ", stripped, count=1, flags=re.IGNORECASE).strip())
            continue

        if re.match(r"^yêu\s*cầu\b", stripped, re.IGNORECASE):
            normalized.append(re.sub(r"^yêu\s*cầu\s*[:\-–]?\s*", "2. Yêu cầu: ", stripped, count=1, flags=re.IGNORECASE).strip())
            continue

        normalized.append(line)

    return normalized


def _normalize_body_line_case(line: str) -> str:
    """Use sentence case for body/subsection lines; major section titles are handled separately."""
    if not line or not _looks_mostly_uppercase(line):
        return line
    if re.match(r"^\s*(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s+", line):
        return line

    marker = ""
    body = line.strip()
    marker_match = re.match(
        r"^(\s*(?:[-+•]\s*|\d+(?:\.\d+)*[\.\)]\s*|[a-zđ][\.\)]\s*))(.+)$",
        body,
        re.IGNORECASE,
    )
    if marker_match:
        marker = marker_match.group(1)
        body = marker_match.group(2).strip()

    body = body.lower()
    body = _capitalize_first_letter(body)
    body = _restore_common_acronyms(body)
    return f"{marker}{body}".strip()


def _looks_mostly_uppercase(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 4:
        return False
    uppercase_letters = [char for char in letters if char.isupper()]
    return len(uppercase_letters) / len(letters) >= 0.65


def _capitalize_first_letter(text: str) -> str:
    for idx, char in enumerate(text):
        if char.isalpha():
            return text[:idx] + char.upper() + text[idx + 1:]
    return text


def _restore_common_acronyms(text: str) -> str:
    proper_phrases = {
        "sở khoa học và công nghệ": "Sở Khoa học và Công nghệ",
        "phòng văn hóa - xã hội": "Phòng Văn hóa - Xã hội",
        "phòng văn hóa – xã hội": "Phòng Văn hóa - Xã hội",
        "trung tâm cung ứng dịch vụ sự nghiệp công": "Trung tâm Cung ứng dịch vụ sự nghiệp công",
        "ban chỉ đạo": "Ban Chỉ đạo",
        "tổ chuyển đổi số cộng đồng": "Tổ chuyển đổi số cộng đồng",
        "đại sứ số": "Đại sứ số",
    }
    for phrase, replacement in proper_phrases.items():
        text = re.sub(re.escape(phrase), replacement, text, flags=re.IGNORECASE)

    acronyms = [
        "ubnd", "hđnd", "mttq", "cntt", "attt", "tthc", "kh", "qđ", "bcđ",
        "pvhxh", "vp", "vt", "kt-xh", "anqp", "qppl", "pccc", "bhyt", "bhxh",
    ]
    for acronym in acronyms:
        replacement = acronym.upper()
        text = re.sub(
            rf"(?<![\wÀ-ỹ]){re.escape(acronym)}(?![\wÀ-ỹ])",
            replacement,
            text,
            flags=re.IGNORECASE,
        )
    return text



def _add_content_paragraphs(doc, text: str, section_heading: str = ""):
    """Add cleaned, properly-split body content paragraphs to a document."""
    paragraphs = _clean_section_content(text, section_heading)
    for p_text in paragraphs:
        _add_paragraph_text(doc, p_text)


def _add_task_appendix(doc, text: str):
    """Add a task appendix table when rows are provided as semicolon-delimited text."""
    import re

    rows = []
    for line in _clean_section_content(text, "PHỤ LỤC NHIỆM VỤ"):
        cleaned = re.sub(r"^\s*(?:[-+•]|\d+[\.\)])\s*", "", line).strip()
        if not cleaned:
            continue
        values = {
            "STT": "",
            "Nội dung nhiệm vụ": "",
            "Văn bản giao nhiệm vụ": "",
            "Thời hạn hoàn thành": "",
            "Cơ quan chủ trì": "",
            "Cơ quan phối hợp": "",
        }
        for part in [p.strip() for p in cleaned.split(";") if p.strip()]:
            if ":" not in part:
                if not values["Nội dung nhiệm vụ"]:
                    values["Nội dung nhiệm vụ"] = part
                continue
            key, value = [p.strip() for p in part.split(":", 1)]
            key_lower = key.lower()
            if key_lower == "stt":
                values["STT"] = value
            elif "nội dung" in key_lower:
                values["Nội dung nhiệm vụ"] = value
            elif "văn bản" in key_lower:
                values["Văn bản giao nhiệm vụ"] = value
            elif "thời hạn" in key_lower:
                values["Thời hạn hoàn thành"] = value
            elif "chủ trì" in key_lower:
                values["Cơ quan chủ trì"] = value
            elif "phối hợp" in key_lower:
                values["Cơ quan phối hợp"] = value
        if any(values.values()):
            if not values["STT"]:
                values["STT"] = str(len(rows) + 1)
            rows.append(values)

    headers = ["STT", "Nội dung nhiệm vụ", "Văn bản giao nhiệm vụ", "Thời hạn hoàn thành", "Cơ quan chủ trì", "Cơ quan phối hợp"]
    if not rows:
        _add_content_paragraphs(doc, text, "PHỤ LỤC NHIỆM VỤ")
        return

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for idx, header in enumerate(headers):
        p = table.rows[0].cells[idx].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, header, bold=True, size=12)

    for row in rows:
        cells = table.add_row().cells
        for idx, header in enumerate(headers):
            p = cells[idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if header == "STT" else WD_ALIGN_PARAGRAPH.JUSTIFY
            _add_run(p, row.get(header, ""), size=12)


def _add_ke_hoach_custom_sections(doc, sections: list[dict]):
    """Render plan sections learned from a same-type sample document."""
    major_index = 0
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "") or "").strip()
        content = str(section.get("content", "") or "").strip()
        if not title or not content:
            continue

        is_appendix = "phụ lục" in title.lower()
        is_opening = "mở đầu" in title.lower()
        if is_appendix:
            section_title = title.upper()
        elif is_opening:
            section_title = title.upper()
        elif re.match(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s+", title, re.IGNORECASE):
            section_title = title.upper()
        else:
            major_index += 1
            section_title = f"{_roman(major_index)}. {title.upper()}"

        _add_section_title(doc, section_title)
        if is_appendix:
            _add_task_appendix(doc, content)
        else:
            _add_content_paragraphs(doc, content, section_title)


def _has_content(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    return bool(value)


def _roman(number: int) -> str:
    values = [
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    result = ""
    for value, symbol in values:
        while number >= value:
            result += symbol
            number -= value
    return result or "I"


def _add_paragraph_text(doc, text: str, bold=False, indent=True):
    """Add a justified paragraph with markdown bold (**text**) support. Bullets (-, +) follow standard alignment."""
    import re
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.0

    if not text:
        return

    # Standard indentation
    if indent:
        p.paragraph_format.first_line_indent = Cm(1.27)

    # Simple markdown bold parser: split by **
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            content = part[2:-2]
            _add_run(p, content, bold=True, size=14)
        else:
            _add_run(p, part, bold=bold, size=14)


def _save_doc(doc, output_path: str) -> str:
    """Save document and return path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    logger.info(f"Exported document to: {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════
# WordExporter Class
# ═══════════════════════════════════════════════════════════════════════

class WordExporter:
    """Export documents in VN administrative format (NĐ 30/2020/NĐ-CP)."""

    # ─── Administrative Documents (NĐ 30/2020) ──────────────────────

    def export_administrative_document(self, doc_type: DocumentType,
                                       data: dict, output_path: str) -> str:
        """Route to the appropriate exporter based on document type."""
        exporters = {
            DocumentType.CONG_VAN: self._export_cong_van,
            DocumentType.QUYET_DINH: self._export_quyet_dinh,
            DocumentType.KE_HOACH: self._export_ke_hoach,
            DocumentType.THONG_BAO: self._export_thong_bao,
            DocumentType.TO_TRINH: self._export_to_trinh,
            DocumentType.BAO_CAO: self._export_bao_cao,
        }

        exporter = exporters.get(doc_type)
        if not exporter:
            raise ValueError(f"Loại văn bản không được hỗ trợ: {doc_type}")

        return exporter(data, output_path)

    def _export_cong_van(self, data: dict, output_path: str) -> str:
        """Export Công văn."""
        doc = _setup_document()

        # Header
        _add_header_table(
            doc,
            co_quan_chu_quan=data.get("co_quan_chu_quan", ""),
            ten_don_vi=data.get("co_quan_ban_hanh", ""),
            so_van_ban=data.get("so_van_ban", ""),
            ky_hieu="CV",
        )

        # Trích yếu
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        trich_yeu = data.get("trich_yeu", "")
        _add_run(p, f"V/v {trich_yeu}", bold=True, italic=True, size=14)

        # Kính gửi
        doc.add_paragraph()
        noi_nhan = data.get("noi_nhan", "")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, f"Kính gửi: {noi_nhan}", size=14)

        doc.add_paragraph()

        # Nội dung
        noi_dung = data.get("noi_dung", data.get("noi_dung_chinh", ""))
        if noi_dung:
            _add_content_paragraphs(doc, noi_dung)

        # Đề nghị
        de_nghi = data.get("de_nghi", "")
        if de_nghi:
            _add_paragraph_text(doc, de_nghi)

        # Kết thúc
        _add_paragraph_text(doc, f"{data.get('co_quan_ban_hanh', '')} trân trọng kính gửi./.")

        # Ký tên
        _add_signature_block(
            doc,
            nguoi_ky=data.get("nguoi_ky", ""),
            chuc_vu=data.get("chuc_vu_nguoi_ky", ""),
        )

        # Nơi nhận
        noi_nhan_list = [f"{noi_nhan};", "Lưu: VT."]
        _add_noi_nhan(doc, noi_nhan_list)

        return _save_doc(doc, output_path)

    def _export_quyet_dinh(self, data: dict, output_path: str) -> str:
        """Export Quyết định."""
        doc = _setup_document()

        # Header
        _add_header_table(
            doc,
            co_quan_chu_quan=data.get("co_quan_chu_quan", ""),
            ten_don_vi=data.get("co_quan_ban_hanh", ""),
            so_van_ban=data.get("so_van_ban", ""),
            ky_hieu="QĐ",
        )

        # Tiêu đề
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "QUYẾT ĐỊNH", bold=True, size=14)

        trich_yeu = data.get("trich_yeu", "")
        if trich_yeu:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_run(p, trich_yeu, bold=True, size=14)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "________", size=14)

        # Chức vụ người ký
        doc.add_paragraph()
        chuc_vu = data.get("chuc_vu_nguoi_ky", "GIÁM ĐỐC")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, chuc_vu.upper(), bold=True, size=14)

        doc.add_paragraph()

        # Căn cứ
        can_cu_list = data.get("can_cu", [])
        if isinstance(can_cu_list, str):
            can_cu_list = [can_cu_list]
        for can_cu in can_cu_list:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Cm(1.27)
            _add_run(p, f"Căn cứ {can_cu}", italic=True, size=14)

        doc.add_paragraph()

        # QUYẾT ĐỊNH
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "QUYẾT ĐỊNH:", bold=True, size=14)

        doc.add_paragraph()

        # Điều khoản
        dieu_khoan = data.get("dieu_khoan", [])
        if isinstance(dieu_khoan, list):
            for dieu in dieu_khoan:
                if isinstance(dieu, dict):
                    _add_paragraph_text(doc, dieu.get("so_dieu", ""), bold=True)
                    _add_paragraph_text(doc, dieu.get("noi_dung", ""))
                else:
                    _add_paragraph_text(doc, str(dieu))
        else:
            # Fallback: noi_dung as text
            noi_dung = data.get("noi_dung", data.get("noi_dung_chinh", ""))
            if noi_dung:
                _add_content_paragraphs(doc, noi_dung)

        # Ký tên
        _add_signature_block(
            doc,
            nguoi_ky=data.get("nguoi_ky", ""),
            chuc_vu=data.get("chuc_vu_nguoi_ky", ""),
        )

        # Nơi nhận
        _add_noi_nhan(doc, ["Như Điều ...;", "Lưu: VT."])

        return _save_doc(doc, output_path)

    def _export_ke_hoach(self, data: dict, output_path: str) -> str:
        """Export Kế hoạch."""
        doc = _setup_document()

        # Header
        _add_header_table(
            doc,
            co_quan_chu_quan=data.get("co_quan_chu_quan", ""),
            ten_don_vi=data.get("co_quan_ban_hanh", ""),
            so_van_ban=data.get("so_van_ban", ""),
            ky_hieu="KH",
        )

        # Tiêu đề
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "KẾ HOẠCH", bold=True, size=14)

        trich_yeu = data.get("trich_yeu", "")
        if trich_yeu:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_run(p, trich_yeu, bold=True, size=14)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "________", size=14)

        doc.add_paragraph()

        phan_mo_dau = data.get("phan_mo_dau", "")
        if phan_mo_dau:
            _add_content_paragraphs(doc, phan_mo_dau, "PHẦN MỞ ĐẦU")

        custom_sections = data.get("custom_sections", [])
        if isinstance(custom_sections, list) and custom_sections:
            _add_ke_hoach_custom_sections(doc, custom_sections)
        else:
            plan_sections = [
                ("MỤC ĐÍCH, YÊU CẦU", data.get("muc_dich_yeu_cau", data.get("dinh_huong_chi_dao", ""))),
                ("NỘI DUNG THỰC HIỆN", data.get("noi_dung_thuc_hien", data.get("nhiem_vu_trong_tam", data.get("noi_dung_ke_hoach", data.get("noi_dung", data.get("noi_dung_chinh", "")))))),
                ("KINH PHÍ", data.get("kinh_phi", "")),
                ("TỔ CHỨC THỰC HIỆN", data.get("to_chuc_thuc_hien", "")),
            ]
            major_index = 0
            for title, content in plan_sections:
                if not _has_content(content):
                    continue
                major_index += 1
                section_title = f"{_roman(major_index)}. {title}"
                _add_section_title(doc, section_title)
                _add_content_paragraphs(doc, content, section_title)

            # PHỤ LỤC NHIỆM VỤ
            phu_luc = data.get("phu_luc_nhiem_vu", "")
            if phu_luc:
                _add_section_title(doc, "PHỤ LỤC NHIỆM VỤ")
                _add_task_appendix(doc, phu_luc)

        # Kết thúc
        _add_paragraph_text(doc, f"Trên đây là Kế hoạch {trich_yeu}. Trong quá trình thực hiện, nếu có vướng mắc, phát sinh, các đơn vị phản ánh kịp thời về {data.get('co_quan_ban_hanh', '')} để xem xét, giải quyết./.")

        # Ký tên
        _add_signature_block(
            doc,
            nguoi_ky=data.get("nguoi_ky", ""),
            chuc_vu=data.get("chuc_vu_nguoi_ky", ""),
        )

        # Nơi nhận
        _add_noi_nhan(
            doc,
            _normalize_noi_nhan(
                data.get("noi_nhan"),
                ["Như trên;", "Lưu: VT."],
            ),
        )

        return _save_doc(doc, output_path)

    def _export_thong_bao(self, data: dict, output_path: str) -> str:
        """Export Thông báo."""
        doc = _setup_document()

        # Header
        _add_header_table(
            doc,
            co_quan_chu_quan=data.get("co_quan_chu_quan", ""),
            ten_don_vi=data.get("co_quan_ban_hanh", ""),
            so_van_ban=data.get("so_van_ban", ""),
            ky_hieu="TB",
        )

        # Tiêu đề
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "THÔNG BÁO", bold=True, size=14)

        trich_yeu = data.get("trich_yeu", "")
        if trich_yeu:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_run(p, trich_yeu, bold=True, size=14)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "________", size=14)

        doc.add_paragraph()

        # Nội dung
        noi_dung = data.get("noi_dung", data.get("noi_dung_chinh", ""))
        if noi_dung:
            _add_content_paragraphs(doc, noi_dung)

        # Kết thúc
        _add_paragraph_text(doc, f"{data.get('co_quan_ban_hanh', '')} thông báo để các cơ quan, đơn vị, cá nhân liên quan biết và thực hiện./.")

        # Ký tên
        _add_signature_block(
            doc,
            nguoi_ky=data.get("nguoi_ky", ""),
            chuc_vu=data.get("chuc_vu_nguoi_ky", ""),
        )

        # Nơi nhận
        noi_nhan_str = data.get("noi_nhan", "Như trên")
        _add_noi_nhan(doc, [f"{noi_nhan_str};", "Lưu: VT."])

        return _save_doc(doc, output_path)

    def _export_to_trinh(self, data: dict, output_path: str) -> str:
        """Export Tờ trình."""
        doc = _setup_document()

        # Header
        _add_header_table(
            doc,
            co_quan_chu_quan=data.get("co_quan_chu_quan", ""),
            ten_don_vi=data.get("co_quan_ban_hanh", ""),
            so_van_ban=data.get("so_van_ban", ""),
            ky_hieu="TTr",
        )

        # Tiêu đề
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "TỜ TRÌNH", bold=True, size=14)

        trich_yeu = data.get("trich_yeu", "")
        if trich_yeu:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_run(p, trich_yeu, bold=True, size=14)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "________", size=14)

        # Kính gửi
        doc.add_paragraph()
        noi_nhan = data.get("noi_nhan", "")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, f"Kính gửi: {noi_nhan}", size=14)

        doc.add_paragraph()

        # I. SỰ CẦN THIẾT
        su_can_thiet = data.get("su_can_thiet", data.get("ly_do", ""))
        if su_can_thiet:
            _add_section_title(doc, "I. SỰ CẦN THIẾT")
            _add_content_paragraphs(doc, su_can_thiet, "I. SỰ CẦN THIẾT")

        # II. NỘI DUNG ĐỀ XUẤT
        noi_dung = data.get("noi_dung_de_xuat", data.get("noi_dung", data.get("noi_dung_chinh", "")))
        if noi_dung:
            _add_section_title(doc, "II. NỘI DUNG ĐỀ XUẤT")
            _add_content_paragraphs(doc, noi_dung, "II. NỘI DUNG ĐỀ XUẤT")

        # III. KIẾN NGHỊ
        kien_nghi = data.get("kien_nghi", "")
        if kien_nghi:
            _add_section_title(doc, "III. KIẾN NGHỊ")
            _add_content_paragraphs(doc, kien_nghi, "III. KIẾN NGHỊ")

        # Kết thúc
        _add_paragraph_text(doc, f"{data.get('co_quan_ban_hanh', '')} kính trình {noi_nhan} xem xét, quyết định./.")

        # Ký tên
        _add_signature_block(
            doc,
            nguoi_ky=data.get("nguoi_ky", ""),
            chuc_vu=data.get("chuc_vu_nguoi_ky", ""),
        )

        # Nơi nhận
        _add_noi_nhan(doc, [f"Như trên;", "Lưu: VT."])

        return _save_doc(doc, output_path)

    def _export_bao_cao(self, data: dict, output_path: str) -> str:
        """Export Báo cáo."""
        doc = _setup_document()

        # Header
        _add_header_table(
            doc,
            co_quan_chu_quan=data.get("co_quan_chu_quan", ""),
            ten_don_vi=data.get("co_quan_ban_hanh", ""),
            so_van_ban=data.get("so_van_ban", ""),
            ky_hieu="BC",
        )

        # Tiêu đề
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "BÁO CÁO", bold=True, size=14)

        trich_yeu = data.get("trich_yeu", "")
        if trich_yeu:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_run(p, trich_yeu, bold=True, size=14)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_run(p, "________", size=14)

        doc.add_paragraph()

        # I. TÌNH HÌNH CHUNG
        tinh_hinh = data.get("tinh_hinh_chung", "")
        if tinh_hinh:
            _add_section_title(doc, "I. TÌNH HÌNH CHUNG")
            _add_content_paragraphs(doc, tinh_hinh, "I. TÌNH HÌNH CHUNG")

        # II. KẾT QUẢ THỰC HIỆN
        ket_qua = data.get("ket_qua", data.get("noi_dung", data.get("noi_dung_chinh", "")))
        if ket_qua:
            _add_section_title(doc, "II. KẾT QUẢ THỰC HIỆN")
            _add_content_paragraphs(doc, ket_qua, "II. KẾT QUẢ THỰC HIỆN")

        # III. HẠN CHẾ, KHÓ KHĂN
        han_che = data.get("han_che", "")
        if han_che:
            _add_section_title(doc, "III. HẠN CHẾ, KHÓ KHĂN")
            _add_content_paragraphs(doc, han_che, "III. HẠN CHẾ, KHÓ KHĂN")

        # IV. PHƯƠNG HƯỚNG, KIẾN NGHỊ
        phuong_huong = data.get("phuong_huong", "")
        if phuong_huong:
            _add_section_title(doc, "IV. PHƯƠNG HƯỚNG, KIẾN NGHỊ")
            _add_content_paragraphs(doc, phuong_huong, "IV. PHƯƠNG HƯỚNG, KIẾN NGHỊ")

        # Kết thúc
        _add_paragraph_text(doc, f"Trên đây là Báo cáo {trich_yeu}. {data.get('co_quan_ban_hanh', '')} kính báo cáo./.")

        # Ký tên
        _add_signature_block(
            doc,
            nguoi_ky=data.get("nguoi_ky", ""),
            chuc_vu=data.get("chuc_vu_nguoi_ky", ""),
        )

        # Nơi nhận
        _add_noi_nhan(doc, ["Như trên;", "Lưu: VT."])

        return _save_doc(doc, output_path)


# Singleton instance
word_exporter = WordExporter()
