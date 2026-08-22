# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""AST Foundations for Zenzic deterministic Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """Base class for all AST nodes."""

    children: list[Node] = field(default_factory=list)


@dataclass
class BlockNode(Node):
    """Base class for block-level elements."""


@dataclass
class InlineNode(Node):
    """Base class for inline elements."""


@dataclass
class Document(BlockNode):
    """Root node of the AST."""


@dataclass
class Paragraph(BlockNode):
    """A paragraph block."""


@dataclass
class Heading(BlockNode):
    """A heading block (e.g. # Title)."""

    level: int = 1
    marker: str = "#"
    prefix_space: str = " "


@dataclass
class TextNode(InlineNode):
    """A plain text inline node."""

    text: str = ""


@dataclass
class LinkNode(InlineNode):
    """A Markdown link [text](url)."""

    url: str = ""
    # Structure to hold data extracted by PolyglotExtractor
    polyglot_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeSpanNode(InlineNode):
    """An inline code span `code`."""

    code: str = ""
    marker: str = "`"


@dataclass
class EmphasisNode(InlineNode):
    """An emphasized inline element *text* or _text_."""

    marker: str = "*"


@dataclass
class StrongNode(InlineNode):
    """A strongly emphasized inline element **text** or __text__."""

    marker: str = "**"


@dataclass
class TableCell(Node):
    """A table cell containing inline nodes and text."""

    text: str = ""
    align: str = "left"  # "left", "center", "right"
    is_header: bool = False
    col_index: int = 0
    row_index: int = 0


@dataclass
class TableRow(Node):
    """A row in a Markdown table."""

    cells: list[TableCell] = field(default_factory=list)
    is_header: bool = False
    row_index: int = 0
    raw_line: str = ""


@dataclass
class TableNode(BlockNode):
    """A GFM Markdown table block."""

    headers: list[str] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)
    alignments: list[str] = field(default_factory=list)
    line_no: int = 1


@dataclass(frozen=True)
class ExtractedLink:
    """Unified node representing any link candidate extracted from Markdown or HTML content.

    Captures Markdown inline links, Markdown reference links/definitions, and HTML href/src attributes.
    """

    url: str
    line_no: int
    is_html: bool
    node_type: str
    raw_text: str = ""
    col_start: int = 0
    suppressed: bool = False
    html_node: Any | None = None
