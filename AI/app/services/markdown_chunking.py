"""Helpers for structuring OCR text into Markdown-like sections and chunks."""

from __future__ import annotations

import re
import unicodedata


_CID_PATTERN = re.compile(r"\(cid:\d+\)")
_MULTISPACE_PATTERN = re.compile(r"[ \t]+")
_PART_PATTERN = re.compile(r"^phan\s+[ivxlcdm\d]+(?:[\s:.-]|$)")
_ROMAN_PATTERN = re.compile(r"^[ivxlcdm]+\.\s+")
_DECIMAL_PATTERN = re.compile(r"^\d+(?:\.\d+)+\.?\s+")
_NUMBERED_PATTERN = re.compile(r"^\d+\.\s+")
_LEGAL_MAJOR_PATTERN = re.compile(r"^(chuong|muc|dieu)\s+")
_LEGAL_MINOR_PATTERN = re.compile(r"^(khoan|diem)\s+")
_UPPER_TOKEN_PATTERN = re.compile(r"[A-ZÀ-Ỵ0-9]{2,}")
_HEADER_LINE_PATTERN = re.compile(r"^(#{1,6})\s+")


def structure_ocr_markdown(text: str) -> str:
    """Promote OCR-detected section lines into Markdown headers."""
    if not text or not text.strip():
        return ""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    structured: list[str] = []
    pending_blank = False

    for raw_line in lines:
        line = _clean_line(raw_line)
        if not line:
            pending_blank = bool(structured)
            continue

        if pending_blank and structured and structured[-1] != "":
            structured.append("")
        pending_blank = False

        promoted = _promote_heading(line)
        if promoted and structured and structured[-1] != "":
            structured.append("")
        structured.append(promoted or line)

    result = "\n".join(structured)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def split_markdown(text: str, chunk_size: int) -> list[str]:
    """Split markdown text into chunks, keeping one header section per chunk when possible."""
    if not text or chunk_size <= 0:
        return [text] if text else []

    grouped_chunks = [group["chunk_text"] for group in _group_sections(text)]

    chunks: list[str] = []
    for chunk in grouped_chunks:
        if len(chunk) > chunk_size:
            chunks.extend(_split_large_section(chunk, chunk_size))
        else:
            chunks.append(chunk)

    return chunks or [text.strip()]


def estimate_chunk_count(text: str, chunk_size: int) -> int:
    return len(split_markdown(text, chunk_size)) if text.strip() else 0


def build_chunk_records(text: str, chunk_size: int, filename: str = "") -> list[dict]:
    records: list[dict] = []
    index = 0
    for grouped in _group_sections(text):
        chunk_text = grouped["chunk_text"]
        if len(chunk_text) > chunk_size:
            split_chunks = _split_large_section(chunk_text, chunk_size)
        else:
            split_chunks = [chunk_text]

        for piece_index, piece in enumerate(split_chunks):
            piece = piece.strip()
            if not piece:
                continue
            metadata = _chunk_metadata(piece, grouped["headers"], filename, piece_index)
            records.append(
                {
                    "chunk_index": index,
                    "chunk_text": piece,
                    **metadata,
                }
            )
            index += 1

    return records


def _clean_line(line: str) -> str:
    line = _CID_PATTERN.sub(" ", line)
    line = line.replace("\t", " ")
    line = _MULTISPACE_PATTERN.sub(" ", line)
    return line.strip()


def _promote_heading(line: str) -> str | None:
    if "|" in line:
        return None
    if _HEADER_LINE_PATTERN.match(line):
        return re.sub(r"^(#{1,6})\s*", r"\1 ", line).strip()

    folded = _fold_text(line)
    if len(line) > 160:
        return None

    if _PART_PATTERN.match(folded):
        return f"# {line}"
    if _ROMAN_PATTERN.match(folded):
        return f"## {line}"
    if _DECIMAL_PATTERN.match(folded):
        depth = min(_decimal_depth(line), 3)
        return f"{'#' * (depth + 1)} {line}"
    if _NUMBERED_PATTERN.match(folded):
        return f"### {line}"
    if _looks_like_upper_heading(line):
        return f"## {line}"

    return None


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_marks.lower()


def _looks_like_upper_heading(line: str) -> bool:
    words = line.split()
    if len(words) < 3 or len(words) > 18:
        return False
    tokens = _UPPER_TOKEN_PATTERN.findall(line)
    return len(tokens) >= max(2, len(words) // 2)


def _decimal_depth(line: str) -> int:
    token = line.split()[0].rstrip(".")
    parts = [part for part in token.split(".") if part]
    return max(2, len(parts))


def _split_into_sections(text: str) -> list[str]:
    lines = text.split("\n")
    sections: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if _HEADER_LINE_PATTERN.match(line) and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append(current)

    return ["\n".join(section).strip() for section in sections if any(part.strip() for part in section)]


def _group_sections(text: str) -> list[dict]:
    sections = _split_into_sections(text)
    grouped_chunks: list[dict] = []
    current_sections: list[str] = []
    current_headers: list[str] = []
    current_has_boundary = False

    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_line = _extract_header_line(section)
        is_boundary = _is_chunk_boundary_header(header_line)

        if is_boundary and current_sections and current_has_boundary:
            grouped_chunks.append(
                {
                    "chunk_text": "\n\n".join(current_sections).strip(),
                    "headers": current_headers[:],
                }
            )
            current_sections = [section]
            current_headers = [header_line] if header_line else []
            current_has_boundary = True
            continue

        current_sections.append(section)
        if header_line:
            current_headers.append(header_line)
        current_has_boundary = current_has_boundary or is_boundary

    if current_sections:
        grouped_chunks.append(
            {
                "chunk_text": "\n\n".join(current_sections).strip(),
                "headers": current_headers[:],
            }
        )

    return grouped_chunks


def _extract_header_line(section: str) -> str:
    first_line = section.splitlines()[0].strip() if section.splitlines() else ""
    return first_line if _HEADER_LINE_PATTERN.match(first_line) else ""


def _is_chunk_boundary_header(header_line: str) -> bool:
    if not header_line:
        return False

    match = _HEADER_LINE_PATTERN.match(header_line)
    if not match:
        return False

    level = len(match.group(1))
    header_text = header_line[match.end():].strip()
    folded = _fold_text(header_text)

    if level == 1:
        return True
    if _PART_PATTERN.match(folded) or _ROMAN_PATTERN.match(folded) or _LEGAL_MAJOR_PATTERN.match(folded):
        return True
    if level >= 3 and (
        _NUMBERED_PATTERN.match(folded)
        or _DECIMAL_PATTERN.match(folded)
        or _LEGAL_MINOR_PATTERN.match(folded)
    ):
        return True

    return False


def _chunk_metadata(
    chunk_text: str,
    inherited_headers: list[str],
    filename: str,
    piece_index: int,
) -> dict:
    header_lines = [line.strip() for line in chunk_text.splitlines() if _HEADER_LINE_PATTERN.match(line.strip())]
    effective_headers = header_lines or inherited_headers
    header_labels = [_strip_header_markup(line) for line in effective_headers]
    section_label = ""
    for line in effective_headers:
        if _is_chunk_boundary_header(line):
            section_label = _strip_header_markup(line)
            break
    if not section_label and header_labels:
        section_label = header_labels[0]

    page_label = ""
    for label in header_labels:
        if _fold_text(label).startswith("trang "):
            page_label = label
            break

    citation_label = filename.strip()
    if section_label:
        citation_label = f"{citation_label} | {section_label}" if citation_label else section_label
    if piece_index > 0:
        citation_label = f"{citation_label} | phần {piece_index + 1}"

    return {
        "header_path": " > ".join(header_labels),
        "section_label": section_label,
        "page_label": page_label,
        "citation_label": citation_label,
        "metadata": {
            "headers": header_labels,
            "char_count": len(chunk_text),
            "piece_index": piece_index,
        },
    }


def _strip_header_markup(header_line: str) -> str:
    match = _HEADER_LINE_PATTERN.match(header_line.strip())
    if not match:
        return header_line.strip()
    return header_line.strip()[match.end():].strip()


def _split_large_section(section: str, chunk_size: int) -> list[str]:
    lines = section.splitlines()
    header = lines[0].strip() if lines and _HEADER_LINE_PATTERN.match(lines[0]) else ""
    body = "\n".join(lines[1:]).strip() if header else section
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", body) if part.strip()]
    if len(paragraphs) <= 1:
        return _split_by_character_boundary(section, chunk_size)

    chunks: list[str] = []
    current = header if header else ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if current and len(candidate) > chunk_size:
            chunks.append(current.strip())
            current = f"{header}\n\n{paragraph}".strip() if header else paragraph
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    output: list[str] = []
    for chunk in chunks:
        if len(chunk) > chunk_size:
            output.extend(_split_by_character_boundary(chunk, chunk_size))
        else:
            output.append(chunk)
    return output


def _split_by_character_boundary(text: str, chunk_size: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            break_point = text.rfind("\n", start + chunk_size // 2, end)
            if break_point <= start:
                break_point = text.rfind(" ", start + chunk_size // 2, end)
            if break_point > start:
                end = break_point
        chunks.append(text[start:end].strip())
        start = end
        while start < len(text) and text[start] in {" ", "\n"}:
            start += 1
    return [chunk for chunk in chunks if chunk]
