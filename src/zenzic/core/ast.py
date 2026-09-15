# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""AST Foundations for Zenzic deterministic Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import zenzic.core.regex as _re


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

    Captures Markdown inline links, Markdown reference links/definitions, HTML
    href/src attributes, and the URL-bearing attributes of JSX components.
    """

    url: str
    line_no: int
    is_html: bool
    node_type: str
    raw_text: str = ""
    col_start: int = 0
    suppressed: bool = False
    html_node: Any | None = None


# ─── Fenced-code-block tracking (CommonMark 0.31.2 §4.5) ──────────────────────
#
# One implementation, because there were thirty-one. Six compared delimiter,
# length and info string correctly but were hand-copied five times; twenty-five
# were `in_code_block = not in_code_block` on any ``` or ~~~ line, which closes a
# four-backtick fence with a three-backtick one and lets a tilde close a backtick.
# A corpus that documents Markdown by showing it -- the only kind that nests
# fences -- leaked fenced content into the heading, list and link checks.
#
# WHAT IS ENFORCED, quoting the specification:
#
#   * "a sequence of at least three consecutive backtick characters or tildes.
#     (Tildes and backticks cannot be mixed.)"
#   * the closer must be "of the same type as the code block began with ... and
#     with at least as many backticks or tildes as the opening code fence."
#   * "Closing code fences cannot have info strings."
#   * "If the end of the containing block (or document) is reached and no closing
#     code fence has been found, the code block contains all of the lines after
#     the opening code fence until the end of the containing block."
#
# WHAT DIVERGES, deliberately, and this is a decision rather than an oversight:
#
# The specification allows an opener "preceded by up to three spaces of
# indentation" -- but that is measured relative to the *containing block*, not to
# column zero. A fence inside an admonition or a list continuation begins four
# or more columns from the margin and is fully conformant, because its container
# begins there. This tracker is line-based and has no container context, so
# applying the column-zero rule literally would not be strict; it would measure
# from a reference the specification does not use.
#
# Measured on 2026-09-14, both sides agreeing: 942 of 1308 fences in
# `zensical/docs` @ 6346cfd sit at 4+ columns, and 196 of ours. That is not a
# local habit, it is how Markdown is written inside containers, and
# `test_validate_snippets_python_indented` asserts it deliberately.
#
# So indentation is permissive. Every defect this replaced -- a tilde closing a
# backtick fence, a short fence closing a long one -- is in the enforced group,
# and none of those 942 lines depends on the permissive part.

# `.` excludes newline, and callers legitimately feed lines with their line
# ending attached (`splitlines(keepends=True)`), so anchoring the info string
# with `$` alone silently refused to match those lines at all -- every fence
# stayed closed and fenced content was handed to the caller as prose. Measured
# when it happened: 7998 extra lines reached the credential scanner on our own
# corpus. `[^\n]*` matches the info string proper; the trailing `\s*` absorbs
# the line ending, which the specification ignores anyway ("may be followed
# only by spaces or tabs, which are ignored").
_FENCE_RE = _re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)")


class FenceTracker:
    """Line-by-line fenced-code-block state, per CommonMark 0.31.2 §4.5.

    Feed it one line at a time in document order. :meth:`feed` returns True when
    the line is *not* content the caller should look at -- either a fence
    delimiter itself or a line inside a fence.

    The distinction the previous toggles could not make::

        t = FenceTracker()
        for line in text.splitlines():
            if t.feed(line):
                continue          # fence delimiter, or inside a fence
            ...                   # real content

    :attr:`inside` exposes the state for callers that need it after the loop --
    an unclosed fence leaves it True, which is the specification's behaviour and
    not an error.
    """

    __slots__ = ("_char", "_len", "inside")

    def __init__(self) -> None:
        self.inside: bool = False
        self._char: str = ""
        self._len: int = 0

    def feed(self, line: str) -> bool:
        """Advance by one line; return True if the caller should skip it."""
        m = _FENCE_RE.match(line)
        if not self.inside:
            if m is None:
                return False
            fence = m.group("fence")
            # A backtick opener may not carry a backtick in its info string
            # ("If the info string comes after a backtick fence, it may not
            # contain any backtick characters"), which is what distinguishes an
            # opener from inline code spanning a whole line.
            if fence[0] == "`" and "`" in m.group("info"):
                return False
            self.inside = True
            self._char = fence[0]
            self._len = len(fence)
            return True
        if m is not None:
            fence = m.group("fence")
            if fence[0] == self._char and len(fence) >= self._len and not m.group("info").strip():
                self.inside = False
                self._char = ""
                self._len = 0
        return True

    def opens(self, line: str) -> tuple[str, str] | None:
        """Return ``(fence, info)`` if *line* opens a fence from the outside.

        For callers that need the info string -- the untagged-code-block rule
        and the SDK's block extractor -- without duplicating the match.
        """
        if self.inside:
            return None
        m = _FENCE_RE.match(line)
        if m is None:
            return None
        fence = m.group("fence")
        if fence[0] == "`" and "`" in m.group("info"):
            return None
        return fence, m.group("info")
