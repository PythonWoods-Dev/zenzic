# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Deterministic Markdown Parser (AST Builder)."""

from __future__ import annotations

from zenzic.core import regex
from zenzic.core.ast import (
    CodeSpanNode,
    Document,
    EmphasisNode,
    Heading,
    LinkNode,
    Node,
    Paragraph,
    StrongNode,
    TableCell,
    TableNode,
    TableRow,
    TextNode,
)


_DELIM_CELL_RE = regex.compile(r"^:?-+:?$")


def parse_table_cells(line: str) -> list[str]:
    """Parse table cells from a single Markdown table line in O(N) time.

    Respects escaped pipes (\\|) and inline code spans (`...`).
    """
    stripped = line.strip()
    if not stripped:
        return []

    # Strip outer leading pipe
    if stripped.startswith("|"):
        stripped = stripped[1:]

    # Strip outer trailing pipe if not escaped
    if stripped.endswith("|"):
        k = len(stripped) - 2
        bs_count = 0
        while k >= 0 and stripped[k] == "\\":
            bs_count += 1
            k -= 1
        if bs_count % 2 == 0:
            stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    in_code = False
    i = 0
    n = len(stripped)

    while i < n:
        c = stripped[i]
        if c == "\\" and i + 1 < n and stripped[i + 1] == "|":
            current.append(r"\|")
            i += 2
            continue
        elif c == "`":
            in_code = not in_code
            current.append(c)
            i += 1
            continue
        elif c == "|" and not in_code:
            cells.append("".join(current).strip())
            current.clear()
            i += 1
            continue
        else:
            current.append(c)
            i += 1

    cells.append("".join(current).strip())
    return cells


def is_table_delimiter_row(line: str) -> tuple[bool, list[str]]:
    """Check if a line is a valid Markdown table delimiter row (:---, ---:, :---:).

    Returns (is_valid, list_of_alignments).
    """
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return False, []
    cells = parse_table_cells(stripped)
    if not cells:
        return False, []

    alignments: list[str] = []
    for c in cells:
        cell_str = c.replace(" ", "")
        if not _DELIM_CELL_RE.match(cell_str):
            return False, []
        if cell_str.startswith(":") and cell_str.endswith(":"):
            alignments.append("center")
        elif cell_str.endswith(":"):
            alignments.append("right")
        else:
            alignments.append("left")

    return True, alignments


def parse(text: str) -> Document:
    """Parse raw Markdown into an AST."""
    doc = Document()
    lines = text.splitlines(keepends=True)

    current_paragraph: Paragraph | None = None

    # RE2 Rigor: No lookarounds, purely DFA.
    heading_pattern = regex.compile(r"^(#{1,6})( +)([^\n]*)(\n?)")
    blank_pattern = regex.compile(r"^[ \t]*(?:\n|$)")

    i = 0
    num_lines = len(lines)
    while i < num_lines:
        line = lines[i]

        heading_match = heading_pattern.match(line)
        if heading_match:
            current_paragraph = None
            marker = heading_match.group(1)
            space = heading_match.group(2)
            content = heading_match.group(3)
            newline = heading_match.group(4)

            heading = Heading(
                level=len(marker),
                marker=marker,
                prefix_space=space,
            )
            heading.children.extend(parse_inline(content))
            if newline:
                heading.children.append(TextNode(text=newline))
            doc.children.append(heading)
            i += 1
            continue

        blank_match = blank_pattern.match(line)
        if blank_match:
            current_paragraph = None
            p = Paragraph()
            p.children.append(TextNode(text=line))
            doc.children.append(p)
            i += 1
            continue

        # Check for GFM Table: current line (header) + next line (delimiter)
        if i + 1 < num_lines and "|" in line:
            is_delim, alignments = is_table_delimiter_row(lines[i + 1])
            if is_delim:
                headers = parse_table_cells(line)
                if headers and len(headers) == len(alignments):
                    current_paragraph = None
                    table_node = TableNode(
                        headers=headers,
                        alignments=alignments,
                        line_no=i + 1,
                    )
                    header_cells = [
                        TableCell(
                            text=h,
                            align=alignments[idx],
                            is_header=True,
                            col_index=idx,
                            row_index=0,
                        )
                        for idx, h in enumerate(headers)
                    ]
                    table_node.rows.append(
                        TableRow(
                            cells=header_cells,
                            is_header=True,
                            row_index=0,
                            raw_line=line,
                        )
                    )
                    table_node.raw_lines.append(line)
                    table_node.raw_lines.append(lines[i + 1])
                    i += 2

                    # Consume subsequent data rows
                    while i < num_lines:
                        data_line = lines[i]
                        if (
                            blank_pattern.match(data_line)
                            or heading_pattern.match(data_line)
                            or ("|" not in data_line)
                        ):
                            break
                        data_cells = parse_table_cells(data_line)
                        if not data_cells:
                            break
                        row_idx = len(table_node.rows)
                        row_cells = [
                            TableCell(
                                text=c,
                                align=alignments[idx] if idx < len(alignments) else "left",
                                is_header=False,
                                col_index=idx,
                                row_index=row_idx,
                            )
                            for idx, c in enumerate(data_cells)
                        ]
                        table_node.rows.append(
                            TableRow(
                                cells=row_cells,
                                is_header=False,
                                row_index=row_idx,
                                raw_line=data_line,
                            )
                        )
                        table_node.raw_lines.append(data_line)
                        i += 1

                    doc.children.append(table_node)
                    continue

        if current_paragraph is None:
            current_paragraph = Paragraph()
            doc.children.append(current_paragraph)

        current_paragraph.children.extend(parse_inline(line))
        i += 1

    return doc


def parse_inline(text: str) -> list[Node]:
    """Parse inline elements using an O(N) linear scan (character-by-character state machine).

    Avoids regex backtracking entirely.
    """
    nodes: list[Node] = []
    i = 0
    n = len(text)
    text_buffer: list[str] = []

    def flush_text() -> None:
        if text_buffer:
            nodes.append(TextNode(text="".join(text_buffer)))
            text_buffer.clear()

    while i < n:
        c = text[i]

        # 1. Code span
        if c == "`":
            i += 1
            code_buffer: list[str] = []
            while i < n and text[i] != "`":
                code_buffer.append(text[i])
                i += 1
            if i < n and text[i] == "`":
                flush_text()
                nodes.append(CodeSpanNode(code="".join(code_buffer), marker="`"))
                i += 1
            else:
                text_buffer.append("`")
                text_buffer.extend(code_buffer)

        # 2. Link [text](url)
        elif c == "[":
            i += 1
            text_content: list[str] = []
            while i < n and text[i] != "]":
                text_content.append(text[i])
                i += 1

            if i < n and text[i] == "]":
                if i + 1 < n and text[i + 1] == "(":
                    i += 2
                    url_content: list[str] = []
                    while i < n and text[i] != ")":
                        url_content.append(text[i])
                        i += 1
                    if i < n and text[i] == ")":
                        flush_text()
                        link = LinkNode(url="".join(url_content))
                        link.children = parse_inline("".join(text_content))
                        nodes.append(link)
                        i += 1
                    else:
                        text_buffer.append("[")
                        text_buffer.extend(text_content)
                        text_buffer.append("](")
                        text_buffer.extend(url_content)
                else:
                    text_buffer.append("[")
                    text_buffer.extend(text_content)
                    text_buffer.append("]")
                    i += 1
            else:
                text_buffer.append("[")
                text_buffer.extend(text_content)

        # 3. Strong and Emphasis (* or _)
        elif c in ("*", "_"):
            marker = c
            if i + 1 < n and text[i + 1] == marker:
                i += 2
                content: list[str] = []
                while i + 1 < n and not (text[i] == marker and text[i + 1] == marker):
                    content.append(text[i])
                    i += 1
                if i + 1 < n and text[i] == marker and text[i + 1] == marker:
                    flush_text()
                    node = StrongNode(marker=marker * 2)
                    node.children = parse_inline("".join(content))
                    nodes.append(node)
                    i += 2
                else:
                    text_buffer.append(marker * 2)
                    text_buffer.extend(content)
            else:
                i += 1
                content = []
                while i < n and text[i] != marker:
                    content.append(text[i])
                    i += 1
                if i < n and text[i] == marker:
                    flush_text()
                    emp_node = EmphasisNode(marker=marker)
                    emp_node.children = parse_inline("".join(content))
                    nodes.append(emp_node)
                    i += 1
                else:
                    text_buffer.append(marker)
                    text_buffer.extend(content)
        else:
            text_buffer.append(c)
            i += 1

    flush_text()
    return nodes


def serialize(node: Node) -> str:
    """Serialize an AST back into exactly the original Markdown string."""
    if isinstance(node, TextNode):
        return node.text
    elif isinstance(node, CodeSpanNode):
        return f"{node.marker}{node.code}{node.marker}"
    elif isinstance(node, LinkNode):
        inner = "".join(serialize(child) for child in node.children)
        return f"[{inner}]({node.url})"
    elif isinstance(node, StrongNode):
        inner = "".join(serialize(child) for child in node.children)
        return f"{node.marker}{inner}{node.marker}"
    elif isinstance(node, EmphasisNode):
        inner = "".join(serialize(child) for child in node.children)
        return f"{node.marker}{inner}{node.marker}"
    elif isinstance(node, Heading):
        res = f"{node.marker}{node.prefix_space}"
        for child in node.children:
            res += serialize(child)
        return res
    elif isinstance(node, TableNode):
        return "".join(node.raw_lines)
    elif isinstance(node, Paragraph | Document):
        res = ""
        for child in node.children:
            res += serialize(child)
        return res
    return ""
