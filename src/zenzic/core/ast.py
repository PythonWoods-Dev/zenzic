# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""AST Foundations for Zenzic deterministic Markdown rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from zenzic.core.regex import RegexPattern

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
# begins there.
#
# UPDATED 2026-09-18: this tracker now *does* carry container context, because
# indented code blocks (CommonMark 4.4) cannot be recognised without it. But
# `feed()` deliberately does not use it for fences, and the permissive
# indentation below stands unchanged. Two reasons, both measured:
#
#   * `feed()` decides which lines reach the credential scanner
#     (`scanner.py:_iter_content_lines` says so in its own comment). Tightening
#     it would remove lines from a security path, which is a tier change.
#   * The 942 conformant fences below would start failing against a column-zero
#     reading the specification does not use.
#
# The container context answers a *second* question instead --
# `in_indented_code` -- which consumers opt into one at a time.
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


#: What opens a container whose content is indented, and therefore shifts the
#: reference point CommonMark 4.4 measures four spaces from.
#:
#: The third alternative was found by measurement, not by reading: a first
#: version knew list markers and admonitions only, and misread **452 fences in
#: `zensical/docs` and 32 in ours** as indented code, because those sit inside
#: `=== "Tab"` content tabs (pymdownx.tabbed). The full test suite passed while
#: that was true.
#:
#: A tab marker is distinguished from a setext H1 underline (`===` alone) by
#: requiring content after the marker -- the two share a prefix, which is a
#: collision the setext work will meet again.
#: Leading whitespace is **unbounded**, deliberately. The column-zero "up to
#: three spaces" of the specification is measured from the *containing block*,
#: and a nested marker sits four or more columns in -- `??? info` inside a tab
#: is at 4 in our own `cli.md`. A first version used `{0,3}` here and never
#: recognised a nested container at all, which is the same mistake the fence
#: divergence above exists to avoid, repeated inside the component written to
#: fix it. Measured: it left 34 fences in `zensical/docs` and 2 in ours read as
#: indented code.
#: The container vocabulary moved to `core/extensions.py` on 2026-09-18: it is
#: declared per Markdown extension there, and resolved from what the project
#: actually enables. What stays here is the *structural* notion -- something
#: opens a container at an indentation, and lines below are measured from it.
#:
#: The incompleteness moved with it, and so did the asymmetry note: a missing
#: marker makes findings disappear (a corpus measurement finds that), a
#: spurious one makes them appear (nobody reports that).
#: A setext underline (CommonMark 4.2): a run of `=` or `-`, up to three spaces
#: of leading indentation, nothing else on the line. Whether it *is* an
#: underline rather than a thematic break depends on the line above, which is
#: why matching it is necessary and not sufficient.
_SETEXT_UNDERLINE_RE = _re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")


def _default_containers() -> RegexPattern:
    """The pattern for an engine with no configuration to read.

    Imported lazily: `core.extensions` is a leaf, and importing it at module
    scope would put a cycle between it and the AST it describes.
    """
    from zenzic.core.extensions import container_pattern

    return container_pattern()


#: Material's block extensions indent their content four columns from the
#: marker. List items do not -- their content starts where the marker ends,
#: which `_LIST_MARKER_RE` measures.
_CONTAINER_CONTENT_INDENT = 4
#: Matches the marker *and its trailing whitespace*, so `.end()` is the column
#: the item's content actually starts at.
_LIST_MARKER_RE = _re.compile(r"^[ \t]*(?:[-+*]|\d{1,9}[.)])[ \t]+")


class BlockTracker:
    """Line-by-line block state: fenced code (§4.5) and indented code (§4.4).

    Feed it one line at a time in document order. :meth:`feed` returns True when
    the line is *not* content the caller should look at -- either a fence
    delimiter itself or a line inside a fence.

    The distinction the previous toggles could not make::

        t = BlockTracker()
        for line in text.splitlines():
            if t.feed(line):
                continue          # fence delimiter, or inside a fence
            ...                   # real content

    :attr:`inside` exposes the state for callers that need it after the loop --
    an unclosed fence leaves it True, which is the specification's behaviour and
    not an error.
    """

    __slots__ = (
        "_char",
        "_containers",
        "_container_stack",
        "_frontmatter",
        "_len",
        "_line_no",
        "_paragraph_open",
        "_paragraph_text",
        "in_frontmatter",
        "in_indented_code",
        "inside",
        "setext_level",
    )

    def __init__(self, containers: RegexPattern | None = None) -> None:
        #: What opens a container, resolved **once** from the project's enabled
        #: extensions (`core/extensions.py`). Passed in rather than consulted:
        #: the tracker must never call back per line, which would be coupling
        #: without union -- the same reason fence state and container state
        #: live in one component instead of two.
        self._containers = containers if containers is not None else _default_containers()
        self.inside: bool = False
        self._char: str = ""
        self._len: int = 0
        #: True while the current line is content of an indented code block
        #: (CommonMark 4.4). A *second question*, not part of `feed()`'s
        #: verdict: consumers opt into it one at a time, and the credential
        #: path deliberately does not.
        self.in_indented_code: bool = False
        self._container_stack: list[int] = []
        self._paragraph_open: bool = False
        #: The text of the paragraph line immediately above -- a setext heading
        #: *is* that text, so a consumer needs it rather than the underline it
        #: just read.
        self._paragraph_text: str = ""
        #: 0, or 1 / 2 when the line just fed is a setext underline and the
        #: heading it closes is an H1 / H2. A **third question**, opt-in like
        #: `in_indented_code`: `feed()`'s verdict stays about fences.
        self.setext_level: int = 0
        #: Line counter and YAML frontmatter state. `---` closing a frontmatter
        #: block sits directly below YAML, which every line-local reading takes
        #: for an open paragraph -- so without this the closing delimiter
        #: becomes an H2. Measured 2026-09-18 before the rule was written.
        self._line_no: int = 0
        self._frontmatter: bool = False
        #: True while the line just fed belongs to the YAML frontmatter block,
        #: **including both delimiters**. A *fourth question*, and the one that
        #: lets a consumer stop carrying its own copy of the rule: thirteen of
        #: them did, they accepted only `---`, and a document closed with YAML's
        #: `...` marker therefore had its whole body treated as frontmatter --
        #: every content rule silent, exit 0, measured on the published v0.30.0.
        #:
        #: `_frontmatter` above is the *state between* the delimiters; this is
        #: the per-line verdict, which is what a caller's `continue` needs.
        self.in_frontmatter: bool = False

    def feed(self, line: str) -> bool:
        """Advance by one line; return True if the caller should skip it.

        The verdict is about **fences only**, and deliberately so -- see the
        block comment above `_FENCE_RE`. Container state is updated as a side
        effect, and answers `in_indented_code` instead.
        """
        self._update_blocks(line)
        if self.in_frontmatter:
            # Frontmatter is YAML, not Markdown: a line of backticks in it is a
            # string, not a fence opener. Returning False keeps this verdict
            # "about fences only" as the docstring says -- the caller skips the
            # line by asking `in_frontmatter`, which is the question that means
            # "not content".
            return False
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

    def _update_blocks(self, line: str) -> None:
        """Track container context and indented-code state for this line.

        CommonMark 4.4 measures a code block's four spaces **from its
        container**, and forbids it from interrupting a paragraph. Both matter,
        measured on two corpora 2026-09-18: of 1,280 lines at four-plus spaces
        in our own docs, 551 follow a list marker, 424 an admonition and 203
        continue a paragraph -- only 102 are candidates. Treating indentation
        alone as code would have silenced rules on 1,178 lines here and 608 in
        `zensical/docs`, trading one false positive for ten false negatives.
        """
        self._line_no += 1
        self.setext_level = 0

        if self.inside:
            # Inside a fence nothing else opens: fence state is an input to
            # this calculation, which is why the two live in one component
            # rather than in two that consult each other.
            self.in_indented_code = False
            return

        stripped = line.strip()

        # YAML frontmatter. `---` on the first line opens it; the next `---`
        # closes it. Nothing inside opens a paragraph, which is the whole point:
        # the closing delimiter sits directly below YAML, so a line-local
        # reading takes it for a setext underline and mints an H2 out of the
        # frontmatter's own terminator.
        self.in_frontmatter = False
        if self._frontmatter:
            self.in_frontmatter = True
            # `...` is YAML's document-end marker and closes frontmatter just as
            # `---` does. Thirteen line-skipping copies of this rule in
            # `content.py` and `governance.py` accept only `---`, so a document
            # closed with `...` has its entire body treated as frontmatter and
            # every content rule goes silent -- measured 2026-09-18 on the
            # published v0.30.0: two H1 headings, no `Z516`, exit 0.
            #
            # `scanner._skip_frontmatter` is the one copy that already accepts
            # both, which is why the credential scanner is unaffected: measured,
            # an AWS key below a `...` terminator still exits 2.
            if stripped in ("---", "..."):
                self._frontmatter = False
            return
        if self._line_no == 1 and stripped == "---":
            self._frontmatter = True
            self.in_frontmatter = True
            return

        # Setext underline (CommonMark 4.2). The disambiguation against a
        # thematic break (4.3) is *only* whether a paragraph is open above:
        # `---` after a blank line is a break, the same characters under a line
        # of text are an H2 underline. `_paragraph_open` already carried that
        # bit for indented code, which is why this needed no new state machine.
        if self._paragraph_open and _SETEXT_UNDERLINE_RE.match(line):
            self.setext_level = 1 if stripped[0] == "=" else 2
            self._paragraph_open = False
            self.in_indented_code = False
            return

        if not stripped:
            # A blank line does not close an indented block -- the next
            # indented line continues it -- but it does close a paragraph.
            self._paragraph_open = False
            self._paragraph_text = ""
            self.in_indented_code = False
            return

        indent = len(line) - len(line.lstrip(" \t"))

        if self._containers.match(line):
            # A marker opens a container whose content sits four columns in,
            # and that becomes the new reference point. Containers nest -- a
            # tab inside an admonition inside a tab is three deep in the
            # external corpus -- so this is a stack. A single integer left 34
            # fences there and 2 here misread as indented code, measured.
            # Where the container's content starts. For a list item it is the
            # end of the marker plus its trailing spaces -- `1. ` is three
            # columns, `- ` is two -- and assuming four instead popped the
            # container on every continuation line indented to the real
            # column, which left a fence in `navigation.md` read as code.
            # Material's block extensions (admonition, tab, definition list)
            # do use four by convention.
            marker = _LIST_MARKER_RE.match(line)
            reference = marker.end() if marker else indent + _CONTAINER_CONTENT_INDENT
            # Only deepen: two markers at the same level are siblings, not
            # nesting, and pushing both left the stack growing as [4, 4, ...].
            while self._container_stack and self._container_stack[-1] >= reference:
                self._container_stack.pop()
            self._container_stack.append(reference)
            self._paragraph_open = True
            self.in_indented_code = False
            return

        while self._container_stack and indent < self._container_stack[-1]:
            self._container_stack.pop()

        reference = self._container_stack[-1] if self._container_stack else 0

        if indent >= reference + 4:
            # Continues an open block, or opens one -- but only where no
            # paragraph is open: 4.4 forbids interrupting one, which is what
            # discards the 203 + 287 lazy continuations measured above.
            self.in_indented_code = self.in_indented_code or not self._paragraph_open
        else:
            self.in_indented_code = False
            self._paragraph_open = True
            self._paragraph_text = stripped

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


def setext_heading(tracker: BlockTracker) -> tuple[int, str] | None:
    """``(level, text)`` when the line just fed is a setext underline.

    One implementation for the rules that read headings, rather than the
    disambiguation copied into each: CommonMark 4.2 needs the line *above* the
    underline, and a rule matching only ``^#{1,6}`` cannot see it. The count
    that decided this: five independent heading recognisers across five modules,
    twelve call sites -- measured 2026-09-18, before the fix.

    **No line number is returned, deliberately.** §4.2 requires the underline to
    follow the paragraph line immediately, so the heading's text is always at
    the caller's ``i - 1``. Returning the tracker's own counter would have been
    wrong for the callers that skip frontmatter before feeding it, which are
    most of them -- a count kept in two places that advance differently.
    """
    if not tracker.setext_level:
        return None
    return tracker.setext_level, tracker._paragraph_text
