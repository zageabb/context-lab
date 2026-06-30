from __future__ import annotations

import re

from markupsafe import Markup, escape


def looks_like_markdown(text: str | None) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    lines = value.splitlines()
    for line in lines[:100]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("```", "#", "> ", "- ", "* ", "| ")):
            return True
        if re.match(r"^\d+\.\s+", stripped):
            return True
        if re.match(r"^\|.+\|$", stripped):
            return True
    return bool(
        re.search(r"\[[^\]]+\]\((https?://[^\s)]+)\)", value)
        or re.search(r"\*\*[^*]+\*\*", value)
        or re.search(r"`[^`]+`", value)
    )


def _format_inline_markdown(value: str) -> str:
    escaped = escape(value)
    html = str(escaped)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        html,
    )
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)
    return html


def render_markdown_html(text: str | None) -> Markup:
    source = (text or "").replace("\r\n", "\n").strip()
    if not source:
        return Markup("")

    lines = source.split("\n")
    html: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    list_items: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    table_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        html.append(f"<p>{'<br>'.join(_format_inline_markdown(line) for line in paragraph)}</p>")
        paragraph = []

    def flush_list() -> None:
        nonlocal list_type, list_items
        if not list_type or not list_items:
            return
        html.append(f"<{list_type}>{''.join(f'<li>{_format_inline_markdown(item)}</li>' for item in list_items)}</{list_type}>")
        list_type = None
        list_items = []

    def flush_code_block() -> None:
        nonlocal in_code_block, code_lines
        if not in_code_block:
            return
        code_block = "\n".join(code_lines)
        html.append(f"<pre><code>{escape(code_block)}</code></pre>")
        in_code_block = False
        code_lines = []

    def flush_table() -> None:
        nonlocal table_lines, paragraph
        if len(table_lines) < 2:
            if table_lines:
                paragraph.extend(table_lines)
            table_lines = []
            return
        rows: list[list[str]] = []
        for line in table_lines:
            stripped = line.strip().strip("|")
            cells = [cell.strip() for cell in stripped.split("|")]
            rows.append(cells)
        header = rows[0]
        body_rows = rows[2:] if len(rows) > 2 else []
        header_html = "".join("<th>" + _format_inline_markdown(cell) + "</th>" for cell in header)
        body_html = "".join(
            "<tr>" + "".join("<td>" + _format_inline_markdown(cell) + "</td>" for cell in row) + "</tr>"
            for row in body_rows
        )
        html.append(
            "<table class=\"table table-sm table-bordered markdown-table\">"
            f"<thead><tr>{header_html}</tr></thead>"
            f"<tbody>{body_html}</tbody>"
            "</table>"
        )
        table_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
            if in_code_block:
                flush_code_block()
            else:
                in_code_block = True
            continue
        if in_code_block:
            code_lines.append(line)
            continue
        if re.match(r"^\|.+\|$", stripped):
            flush_paragraph()
            flush_list()
            table_lines.append(line)
            continue
        if table_lines:
            flush_table()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            html.append(f"<h{level}>{_format_inline_markdown(heading_match.group(2))}</h{level}>")
            continue
        unordered_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if unordered_match:
            flush_paragraph()
            if list_type and list_type != "ul":
                flush_list()
            list_type = "ul"
            list_items.append(unordered_match.group(1))
            continue
        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered_match:
            flush_paragraph()
            if list_type and list_type != "ol":
                flush_list()
            list_type = "ol"
            list_items.append(ordered_match.group(1))
            continue
        flush_list()
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    if table_lines:
        flush_table()
    flush_code_block()
    return Markup("".join(html))
