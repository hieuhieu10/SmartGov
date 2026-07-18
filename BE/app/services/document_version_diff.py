"""Create a read-only DOCX preview with changes highlighted."""

from __future__ import annotations

import re
from copy import deepcopy
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path
from typing import Iterator

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run


def _iter_paragraphs(parent: DocumentObject | _Cell) -> Iterator[Paragraph]:
    """Yield body and table-cell paragraphs in document order."""
    parent_element = parent.element.body if isinstance(parent, DocumentObject) else parent._tc
    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            table = Table(child, parent)
            seen_cells: set[int] = set()
            for row in table.rows:
                for cell in row.cells:
                    cell_key = id(cell._tc)
                    if cell_key in seen_cells:
                        continue
                    seen_cells.add(cell_key)
                    yield from _iter_paragraphs(cell)


def _highlight_all(paragraph: Paragraph) -> None:
    for run in paragraph.runs:
        if run.text:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _highlight_ranges(paragraph: Paragraph, ranges: list[tuple[int, int]]) -> None:
    offset = 0
    for run in list(paragraph.runs):
        start = offset
        end = start + len(run.text)
        offset = end
        if not run.text:
            continue

        local_boundaries = {0, len(run.text)}
        for range_start, range_end in ranges:
            if start < range_end and end > range_start:
                local_boundaries.add(max(range_start - start, 0))
                local_boundaries.add(min(range_end - start, len(run.text)))
        boundaries = sorted(local_boundaries)
        segments = [
            (run.text[left:right], start + left, start + right)
            for left, right in zip(boundaries, boundaries[1:])
            if left < right
        ]
        highlighted_segments = [
            (
                text,
                any(segment_start < range_end and segment_end > range_start for range_start, range_end in ranges),
            )
            for text, segment_start, segment_end in segments
        ]
        if not any(highlighted for _, highlighted in highlighted_segments):
            continue
        if len(highlighted_segments) == 1:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            continue

        run_element = run._r
        parent = run_element.getparent()
        insert_at = parent.index(run_element)
        for text, highlighted in highlighted_segments:
            cloned_element = deepcopy(run_element)
            cloned_run = Run(cloned_element, paragraph)
            cloned_run.text = text
            if highlighted:
                cloned_run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            parent.insert(insert_at, cloned_element)
            insert_at += 1
        parent.remove(run_element)


def _highlight_word_changes(current: Paragraph, previous: Paragraph) -> None:
    current_words = list(re.finditer(r"\S+", current.text))
    previous_words = list(re.finditer(r"\S+", previous.text))
    matcher = SequenceMatcher(
        None,
        [match.group(0) for match in previous_words],
        [match.group(0) for match in current_words],
        autojunk=False,
    )
    ranges: list[tuple[int, int]] = []
    deleted_only = False
    for tag, _old_start, _old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if new_start < new_end:
            ranges.append(
                (
                    current_words[new_start].start(),
                    current_words[new_end - 1].end(),
                )
            )
        else:
            deleted_only = True

    if ranges:
        _highlight_ranges(current, ranges)
    elif deleted_only and current.text:
        # A pure deletion has no remaining characters to color, so mark the
        # surviving paragraph to show where the change occurred.
        _highlight_all(current)


def render_highlighted_docx(current_path: Path, previous_path: Path | None) -> bytes:
    """Return the selected version with additions/replacements highlighted."""
    current_document = Document(current_path)
    if previous_path is None:
        output = BytesIO()
        current_document.save(output)
        return output.getvalue()

    previous_document = Document(previous_path)
    current_paragraphs = list(_iter_paragraphs(current_document))
    previous_paragraphs = list(_iter_paragraphs(previous_document))
    matcher = SequenceMatcher(
        None,
        [paragraph.text for paragraph in previous_paragraphs],
        [paragraph.text for paragraph in current_paragraphs],
        autojunk=False,
    )

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal" or tag == "delete":
            continue
        if tag == "insert":
            for paragraph in current_paragraphs[new_start:new_end]:
                _highlight_all(paragraph)
            continue

        paired_count = min(old_end - old_start, new_end - new_start)
        for offset in range(paired_count):
            _highlight_word_changes(
                current_paragraphs[new_start + offset],
                previous_paragraphs[old_start + offset],
            )
        for paragraph in current_paragraphs[new_start + paired_count:new_end]:
            _highlight_all(paragraph)

    output = BytesIO()
    current_document.save(output)
    return output.getvalue()
