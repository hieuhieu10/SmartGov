"""Render generated DOCX files to simple HTML previews."""

from html import escape
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P


def _iter_block_items(parent):
    if isinstance(parent, DocumentObject):
        parent_elm = parent.element.body
    else:
        parent_elm = parent._tc

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _paragraph_html(paragraph: Paragraph) -> str:
    text = paragraph.text.strip()
    if not text:
        return '<div class="docx-spacer"></div>'

    style_name = (paragraph.style.name if paragraph.style else '').lower()
    align = paragraph.alignment
    classes = ['docx-paragraph']
    if align == 1:
        classes.append('align-center')
    elif align == 2:
        classes.append('align-right')
    elif align == 3:
        classes.append('align-justify')

    is_heading = 'heading' in style_name or (text.isupper() and len(text) < 120)
    tag = 'h3' if is_heading else 'p'
    runs = []
    for run in paragraph.runs:
        value = escape(run.text)
        if not value:
            continue
        if run.bold:
            value = f'<strong>{value}</strong>'
        if run.italic:
            value = f'<em>{value}</em>'
        runs.append(value)
    content = ''.join(runs) or escape(text)
    return f'<{tag} class="{" ".join(classes)}">{content}</{tag}>'


def _table_html(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = ''.join(f'<td>{escape(cell.text).replace(chr(10), "<br>")}</td>' for cell in row.cells)
        rows.append(f'<tr>{cells}</tr>')
    return f'<table class="docx-table"><tbody>{"".join(rows)}</tbody></table>'


def render_docx_preview_html(path: str | Path) -> str:
    doc = Document(str(path))
    body = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            body.append(_paragraph_html(block))
        elif isinstance(block, Table):
            body.append(_table_html(block))

    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; background: #f1f5f9; font-family: "Times New Roman", Times, serif; color: #111827; }}
  .page {{ width: min(794px, calc(100vw - 32px)); min-height: 1123px; box-sizing: border-box; margin: 16px auto; padding: 72px 76px; background: white; box-shadow: 0 8px 28px rgba(15, 23, 42, .14); }}
  .docx-paragraph {{ margin: 0 0 8px; font-size: 18px; line-height: 1.35; white-space: pre-wrap; }}
  h3.docx-paragraph {{ margin: 12px 0 8px; font-size: 18px; line-height: 1.25; font-weight: 700; }}
  .align-center {{ text-align: center; }}
  .align-right {{ text-align: right; }}
  .align-justify {{ text-align: justify; }}
  .docx-spacer {{ height: 10px; }}
  .docx-table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 16px; }}
  .docx-table td {{ border: 1px solid #334155; padding: 6px 8px; vertical-align: top; white-space: pre-wrap; }}
  @media (max-width: 720px) {{ .page {{ width: 100vw; min-height: auto; margin: 0; padding: 32px 24px; box-shadow: none; }} .docx-paragraph, h3.docx-paragraph {{ font-size: 16px; }} }}
</style>
</head>
<body><main class="page">{"".join(body)}</main></body>
</html>'''
