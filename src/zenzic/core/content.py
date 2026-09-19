# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Deterministic Semantic Linting & Readability Metrics engine for Zenzic.

Provides mathematical content quality evaluation for Markdown/MDX graphs,
enforcing heading hierarchy (Z510), sentence length limits (Z511),
empty section detection (Z512), duplicate headings (Z513), generic alt text (Z514),
bare URLs in prose (Z515), multiple H1 headings (Z516), and heading punctuation (Z517)
with strict line-number fidelity.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import zenzic.core.regex as re
from zenzic.core.ast import BlockTracker, setext_heading
from zenzic.core.codes import code_severity


if TYPE_CHECKING:
    from zenzic.core.regex import RegexPattern
    from zenzic.core.rules import RuleFinding


# WHY THESE FUNCTIONS TAKE A PATTERN AND NOT A CONTEXT
# -----------------------------------------------------
# Which containers open an indented block is a fact about the *run* -- which
# extensions the project enables -- and it has one answer for the whole
# execution. `ResolutionContext` is per-file by construction, so carrying the
# vocabulary there would have built an object per file to transport a value
# that never varies. The run-scoped carrier is `AdaptiveRuleEngine`, which is
# built once per run and already has a tripwire guarding it against caching.
#
# `containers` is keyword-only and has **no default** at every one of the
# thirteen functions below. That is deliberate: a default would be reachable by
# omitting one keyword at one call site, and it would silently restore the full
# four-marker vocabulary to a project that enables only `admonition` -- exactly
# the defect the extension contract exists to remove. `None` still means "use
# the declared default vocabulary", but now only a caller who writes it can ask
# for that.
# ATX Heading regex matching # to ######
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")

# Characters that may legitimately close a sentence *after* its terminator:
# Markdown emphasis and inline-code markers, plus ordinary closing brackets and
# quotes. A sentence ending inside `*italics*` puts the closer between the period
# and the following space (``...parsing.* Next``), so a boundary test that only
# accepts whitespace immediately after the terminator never fires there and
# silently merges the two sentences into one.
_SENTENCE_CLOSERS = "*_`)]}\"'’”»"

# Same rule in regex form, for the line-level pre-filter below. Kept beside the
# character set it mirrors so the two cannot drift apart.
_SENTENCE_END_RE = re.compile(r"[.!?;][*_`)\]}\"'’”»]*(?:\s|$)")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences deterministically in O(N) time without regex lookaround."""
    sentences: list[str] = []
    current: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        current.append(char)
        if char in ".!?;":
            # Look past any run of closing markup/punctuation. The closers belong
            # to the sentence they close, so they are consumed into it rather
            # than left to start the next one.
            j = i + 1
            while j < n and text[j] in _SENTENCE_CLOSERS:
                j += 1
            if j == n or text[j].isspace():
                current.extend(text[i + 1 : j])
                i = j - 1
                sent = "".join(current).strip()
                if sent:
                    sentences.append(sent)
                current.clear()
                while i + 1 < n and text[i + 1].isspace():
                    i += 1
        i += 1
    if current:
        trailing = "".join(current).strip()
        if trailing:
            sentences.append(trailing)
    return sentences


def check_heading_hierarchy(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z510: Detect skipped heading levels (e.g. H3 immediately following H1)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)
    prev_level = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if _fence.feed(line) or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is not None:
            level, _raw_title, _hline, _hraw = _h
            if prev_level > 0 and level > prev_level + 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z510",
                        severity=code_severity("Z510"),
                        file_path=file_path,
                        line_no=_hline,
                        message=(
                            f"Heading level H{level} skips previous level H{prev_level} "
                            f"(expected H{prev_level + 1} or lower)."
                        ),
                        matched_line=_hraw,
                    )
                )
            prev_level = level

    return findings


#: An inline code span. Tags named inside one are prose about HTML, not HTML.
_CODE_SPAN_RE = re.compile(r"``[^`\n]+``|`[^`\n]+`")

#: CommonMark 4.6 type 1: these run to their closing tag, and a blank line
#: inside one does not end the block.
_TYPE1_TAGS = frozenset({"pre", "script", "style", "textarea"})

_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "base",
    "basefont",
    "blockquote",
    "body",
    "caption",
    "center",
    "col",
    "colgroup",
    "dd",
    "details",
    "dialog",
    "dir",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "frame",
    "frameset",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "header",
    "hr",
    "html",
    "iframe",
    "legend",
    "li",
    "link",
    "main",
    "menu",
    "menuitem",
    "nav",
    "noframes",
    "ol",
    "optgroup",
    "option",
    "p",
    "param",
    "pre",
    "script",
    "search",
    "section",
    "style",
    "summary",
    "table",
    "tbody",
    "td",
    "textarea",
    "tfoot",
    "th",
    "thead",
    "title",
    "tr",
    "track",
    "ul",
}
_VOID_TAGS = {
    "area",
    "base",
    "basefont",
    "br",
    "col",
    "embed",
    "frame",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


#: These three are bare ``[^>]`` on purpose, and the purpose is written here because
#: the same shape was a real defect in four other patterns this cycle (Z205 mis-tiered
#: as Z121, Z403 on a tag that has alt, Z516 on a truncated title, Z405 on a referenced
#: image). They mask rather than read: a tag cut short at a ``>`` inside a quoted value
#: leaves the tail as prose instead of swallowing it, which is the safe direction —
#: masking too little shows text that is there, masking too much hides text that is.
#: Measured with a control pair rather than argued: ``<span title="a > b">TODO: ... bare
#: URL</span>`` and the same line with ``title="a b"`` report the same two findings
#: (Z501, Z515), differing only in the column the caret lands on.
#: Attribute-aware: a bare ``[^>]*`` ends the tag at the first ``>`` anywhere
#: in it, including one inside a quoted attribute value, which then leaves the
#: rest of the tag unmasked as prose. Same class as the four already fixed.
_OPEN_TAG_RE = re.compile(r"""<([a-zA-Z1-6]+)\b((?:[^>"']|"[^"]*"|'[^']*')*)/?>""", re.IGNORECASE)
_CLOSE_TAG_RE = re.compile(r"</([a-zA-Z1-6]+)\s*>", re.IGNORECASE)
_TAG_MASK_RE = re.compile(r"""<(?:[^>"']|"[^"]*"|'[^']*')+>""")


def _mask_html_blocks(text: str) -> str:
    """Mask raw HTML block elements and tags with spaces of equal length, preserving line breaks."""
    if "<" not in text:
        return text

    lines = text.split("\n")
    result: list[str] = []
    html_depth = 0

    in_type1 = False

    for raw_line in lines:
        # CommonMark 4.6 type 6 ends at the first **blank line**, not at the
        # matching close tag. Closing on tag depth masked everything between the
        # blank line and the eventual `</div>` -- measured 2026-09-18: 139 of
        # 141 HTML blocks in this repository's docs have that shape, hiding
        # 1,348 lines of prose, and 75 of 86 blocks with 590 lines on the
        # external corpus. The divergence was one-sided: zero lines the
        # specification masks and we did not.
        #
        # Type 1 (`script`, `style`, `pre`, `textarea`) is the exception the
        # specification itself makes: it runs to its closing tag and a blank
        # line inside it means nothing.
        if html_depth > 0 and not in_type1 and not raw_line.strip():
            html_depth = 0
            result.append(raw_line)
            continue
        # Inline code first. A documentation tool's own pages write `<div>` in
        # backticks constantly, and without this the mention opened a block that
        # never closed, hiding the rest of the file from Z511. Measured
        # 2026-09-18: 7 files and 533 lines here, 3 files and 850 lines on the
        # external corpus. The blanking is length-preserving, so the line the
        # caller gets back keeps its offsets.
        line = (
            _CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), raw_line)
            if "`" in raw_line
            else raw_line
        )
        if "<" not in line:
            result.append(" " * len(raw_line) if html_depth > 0 else raw_line)
            continue

        opens = []
        for m in _OPEN_TAG_RE.finditer(line):
            tag = m.group(1).lower()
            full_match = m.group(0)
            if tag in _BLOCK_TAGS and tag not in _VOID_TAGS and not full_match.endswith("/>"):
                opens.append(tag)

        closes = [
            m.group(1).lower()
            for m in _CLOSE_TAG_RE.finditer(line)
            if m.group(1).lower() in _BLOCK_TAGS
        ]
        net_change = len(opens) - len(closes)

        if html_depth > 0 or opens:
            result.append(" " * len(raw_line))
            html_depth = max(0, html_depth + net_change)
            if html_depth == 0:
                in_type1 = False
            if opens and not in_type1:
                in_type1 = any(t in _TYPE1_TAGS for t in opens)
        else:
            result.append(_TAG_MASK_RE.sub(lambda m: " " * len(m.group(0)), raw_line))

    return "\n".join(result)


def check_sentence_lengths(
    file_path: Path, text: str, max_words: int = 40, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z511: Detect sentences exceeding max_words readability threshold."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    text_masked = _mask_html_blocks(text)
    lines = text_masked.splitlines()
    _fence = BlockTracker(containers)

    current_sentence_parts: list[str] = []
    current_start_line = 1

    def _flush_and_check(parts: list[str], start_line: int) -> None:
        if not parts:
            return
        full_sent = " ".join(parts)
        raw_sentences = _split_sentences(full_sent)
        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            words = s_clean.split()
            if len(words) > max_words:
                preview = s_clean[:50] + "..." if len(s_clean) > 50 else s_clean
                findings.append(
                    RuleFinding(
                        rule_id="Z511",
                        severity=code_severity("Z511"),
                        file_path=file_path,
                        line_no=start_line,
                        message=f"Sentence of {len(words)} words exceeds maximum limit of {max_words} words.",
                        match_text=preview,
                        col_start=_col_of(lines[start_line - 1], s_clean[:24])
                        if 0 < start_line <= len(lines)
                        else 0,
                    )
                )
        parts.clear()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Frontmatter and code blocks: both are "not content", and the tracker
        # is the one place that decides either.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            _flush_and_check(current_sentence_parts, current_start_line)
            continue

        if _fence.inside:
            continue

        # Skip headings, blockquotes, tables, HTML comments
        is_bullet = bool(re.match(r"^(\*|-|\d+\.)\s+", stripped))
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("<!--")
            or stripped.startswith("|")
            or stripped.startswith(">")
            or is_bullet
        ):
            _flush_and_check(current_sentence_parts, current_start_line)
            if not is_bullet:
                continue

        if not current_sentence_parts:
            current_start_line = i

        current_sentence_parts.append(stripped)

        # Check if line contains sentence terminators
        if _SENTENCE_END_RE.search(stripped):
            _flush_and_check(current_sentence_parts, current_start_line)

    # Flush any remaining buffer at EOF. Without this, a document whose final
    # paragraph never satisfies the line-level test above — one ending in
    # ``*emphasis.*`` or with no terminator at all — was silently never checked.
    _flush_and_check(current_sentence_parts, current_start_line)
    return findings


def check_empty_sections(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z512: Detect headings with zero body content before next heading or EOF."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)

    current_heading: str | None = None
    current_heading_line: int = 0
    current_heading_depth: int | None = None
    has_body_content = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Frontmatter and code blocks are both "not content"; the tracker
        # decides either, so this loop no longer carries the rule.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            if current_heading is not None:
                has_body_content = True
            continue

        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is not None:
            depth, _raw_title, _hline, _hraw = _h
            # A heading whose next heading is deeper is a grouping label: it
            # introduces its subsections structurally and the content lives one
            # level down. Flagging it would push authors to write a sentence
            # restating the heading, which is the filler Z512 exists to discourage.
            # A sibling or shallower heading has no subsection to delegate to, so
            # that section is genuinely empty and still fires.
            groups_subsections = current_heading_depth is not None and depth > current_heading_depth
            if current_heading is not None and not has_body_content and not groups_subsections:
                findings.append(
                    RuleFinding(
                        rule_id="Z512",
                        severity=code_severity("Z512"),
                        file_path=file_path,
                        line_no=current_heading_line,
                        message=f"Heading section '{_short_heading(current_heading)}' contains no body content "
                        "before next section or EOF.",
                        match_text=current_heading,
                        col_start=_col_of(lines[current_heading_line - 1], current_heading),
                    )
                )
            current_heading = _raw_title
            current_heading_line = _hline
            current_heading_depth = depth
            has_body_content = False
            continue

        # Check if line constitutes body content
        if stripped and not stripped.startswith("<!--"):
            if current_heading is not None:
                has_body_content = True

    # Evaluate final heading section at EOF
    if current_heading is not None and not has_body_content:
        findings.append(
            RuleFinding(
                rule_id="Z512",
                severity=code_severity("Z512"),
                file_path=file_path,
                line_no=current_heading_line,
                message=f"Heading section '{_short_heading(current_heading)}' contains no body content "
                "before next section or EOF.",
                match_text=current_heading,
                col_start=_col_of(lines[current_heading_line - 1], current_heading),
            )
        )

    return findings


# ─── Z513, Z514, Z515, Z516, Z517 ─────────────────────────────────────────────


#: A heading is a line, not a paragraph, so a message that quotes one should not
#: be able to print an essay. The bound exists because a defect in the heading
#: recogniser printed an entire block quote as a title -- the message made the
#: defect obvious, which is worth keeping, but a legitimately long heading
#: should not do the same to a terminal.
_HEADING_QUOTE_MAX = 60


def _short_heading(title: str) -> str:
    """The heading text as a message should quote it: one line, bounded."""
    collapsed = " ".join(title.split())
    if len(collapsed) <= _HEADING_QUOTE_MAX:
        return collapsed
    return collapsed[: _HEADING_QUOTE_MAX - 1].rstrip() + "…"


def _heading_here(
    stripped: str,
    line: str,
    i: int,
    lines: list[str],
    tracker: BlockTracker,
) -> tuple[int, str, int, str] | None:
    """``(level, text, line_no, raw_line)`` for the heading on this line, or None.

    **One recogniser for the seven rules below.** Before this, each matched
    `^#{1,6}` on its own, and a setext heading (CommonMark 4.2) was therefore
    invisible to all seven: two ATX H1s fired `Z516`, a setext H1 plus an ATX
    one did not, because the rule had counted one. Measured with its positive
    control 2026-09-18 -- the control proves the rule is on, so that "no
    finding" cannot be read as "no defect".

    The setext branch reports the **text** line (`i - 1`) and that line's raw
    content, not the underline's: 4.2 requires the underline to follow the
    paragraph immediately, and the reader is pointed at the words.

    The disambiguation against a thematic break (4.3) is not here. It is
    `BlockTracker`'s, because it depends on whether a paragraph is open above --
    state the tracker already carried for indented code, which is why this
    needed no second state machine.
    """
    sx = setext_heading(tracker)
    if sx is not None:
        return sx[0], sx[1], i - 1, lines[i - 2] if i >= 2 else line
    m = _ATX_HEADING_RE.match(stripped)
    if m:
        return len(m.group(1)), m.group(2).strip(), i, line
    return None


_HEADING_ANCHOR_STRIP_RE = re.compile(r"\s*\{#[^}]+\}\s*$")
_WS_COLLAPSE_RE = re.compile(r"\s+")
_TRAILING_INVALID_PUNCT = {".", ":", ";"}
#: Attribute-aware: the bare ``[^>]*`` this replaced ended the tag at the first
#: ``>`` anywhere in it, including inside a quoted attribute value, so
#: ``<h1 title="a > b">Second Title</h1>`` reported its title as
#: ``b">Second Title`` -- a heading the document does not contain, in the
#: message, in ``match_text`` and in everything downstream that reads them.
#: Measured with a control pair: the same heading with ``title="a b"`` was clean.
_HTML_H1_RE = re.compile(r"""<h1\b(?:[^>"']|"[^"]*"|'[^']*')*>(.*?)</h1>""", re.IGNORECASE)

_GENERIC_ALT_SET = frozenset(
    {
        "image",
        "screenshot",
        "picture",
        "photo",
        "icon",
        "graphic",
        "logo",
        "img",
        "figure",
        "thumbnail",
        "untitled",
    }
)

_GENERIC_ALT_PREFIXES = (
    "image of",
    "picture of",
    "photo of",
    "screenshot of",
    "graphic of",
    "icon of",
    "logo of",
    "thumbnail of",
    "figure of",
)

_BARE_URL_RE = re.compile(r"https?://[^\s<>`\"'\[\]\(\)]+")
#: Bare ``[^>]`` deliberately, same reasoning as the masking patterns above: this one
#: strips tags out of prose before the content rules read it, so cutting a tag short
#: leaves text rather than eating it.
#: Attribute-aware, for the reason ``_OPEN_TAG_RE`` above is. This one masks
#: tags before Z515, Z518 and Z519 read the line, so a truncated match left
#: attribute text visible to them as prose.
_HTML_TAG_RE = re.compile(r"""<(?:[^>"']|"[^"]*"|'[^']*')+>""")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
#: An autolink is *defined* as ending at the first ``>``: CommonMark forbids ``>``
#: inside one, so here the bare class is the specification, not a shortcut.
_AUTOLINK_RE = re.compile(r"<https?://[^>]+>")
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\([^)]+\)")


def _blank(pattern: re.RegexPattern, text: str) -> str:
    """Mask every match of *pattern* with spaces of the same width.

    A mask that shrinks a span to one space shifts every column after it,
    and a caret computed on the masked line then points beside the word it
    names. Width-preserving masking keeps ``m.start()`` a column of the
    raw line.
    """
    return str(pattern.sub(lambda m: " " * len(m.group(0)), text))


def _col_of(line: str, text: str) -> int:
    """Column at which *text* starts in *line*; 0 when it is not on the line.

    Every content rule used to construct its finding without ``col_start``,
    so the reporter, the SARIF ``startColumn`` and the LSP range all said
    column 0 for 1,629 of 1,629 findings measured on 2026-09-17.
    """
    idx = line.find(text) if text else -1
    return idx if idx >= 0 else 0


# A leading caret marks a footnote definition (`[^1]: prose`), not a link
# reference. Accepting it turned the first word of the footnote text into a URL:
# 17 phantom Z101 on `zensical/docs`. This is the fourth copy of one decision --
# validator.py, rules.py, scanner.py and content.py each carry the pattern, and
# only validator.py had the guard. Consolidation is tracked; the guard is here now.
# At most three spaces of indentation (CommonMark 4.7): four or more is indented
# code or a paragraph continuation, and `^\s*` used to exempt both as definitions.
_MARKDOWN_REF_DEF_RE = re.compile(r"^ {0,3}\[[^^\]][^\]]*\]:\s*\S+")
# Indented code (CommonMark 4.4): four spaces or a tab, and only where a blank line
# precedes it -- indented code cannot interrupt a paragraph.
_INDENTED_CODE_RE = re.compile(r"^(?: {4}|\t)")


def _is_generic_alt(alt: str) -> bool:
    """Check if alt text contains generic filler words or phrases."""
    clean = alt.strip().lower()
    if not clean:
        return False
    clean = re.sub(r"^[\s_.:-]+|[\s_.:-]+$", "", clean).strip()
    if clean in _GENERIC_ALT_SET:
        return True
    if any(clean.startswith(prefix) for prefix in _GENERIC_ALT_PREFIXES):
        return True
    words = clean.split()
    if len(words) == 2 and words[0] in _GENERIC_ALT_SET and words[1].isdigit():
        return True
    return False


def check_duplicate_headings(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z513: Emit if two headings in the same document resolve to the exact same text."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)
    seen_headings: dict[str, int] = {}

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is not None:
            _level, raw_title, _hline, _hraw = _h
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()
            norm_title = _WS_COLLAPSE_RE.sub(" ", clean_title).lower()
            if not norm_title:
                continue

            if norm_title in seen_headings:
                first_line = seen_headings[norm_title]
                findings.append(
                    RuleFinding(
                        rule_id="Z513",
                        severity=code_severity("Z513"),
                        file_path=file_path,
                        line_no=_hline,
                        message=f"Duplicate heading '{_short_heading(clean_title)}' found "
                        f"(first occurrence at line {first_line}).",
                        match_text=clean_title,
                        col_start=_col_of(_hraw, clean_title),
                        matched_line=_hraw,
                    )
                )
            else:
                seen_headings[norm_title] = i

    return findings


def check_generic_image_alt_text(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z514: Emit if an image tag (![]() or <img>) uses generic filler words as alt text."""
    from zenzic.core.rules import RuleFinding
    from zenzic.core.scanner import _INLINE_CODE_RE, _RE_HTML_ALT, _RE_HTML_IMG, _RE_IMAGE_INLINE

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)

    for i, line in enumerate(lines, start=1):
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        if "![" not in line and "<img" not in line and "<IMG" not in line:
            continue

        clean = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line)

        # 1. Inline Markdown images
        for m in _RE_IMAGE_INLINE.finditer(clean):
            alt_text = m.group(1)
            url = m.group(2)
            if _is_generic_alt(alt_text):
                findings.append(
                    RuleFinding(
                        rule_id="Z514",
                        severity=code_severity("Z514"),
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Image '{url}' uses generic alt text '{alt_text.strip()}'. "
                            "Provide descriptive alt text for accessibility."
                        ),
                        match_text=alt_text.strip(),
                        col_start=_col_of(line, alt_text.strip()),
                        matched_line=line,
                    )
                )

        # 2. HTML <img> tags
        for img_match in _RE_HTML_IMG.finditer(clean):
            tag = img_match.group()
            alt_match = _RE_HTML_ALT.search(tag)
            if alt_match is not None:
                alt_text = alt_match.group(1) or alt_match.group(2) or alt_match.group(3) or ""
                if _is_generic_alt(alt_text):
                    findings.append(
                        RuleFinding(
                            rule_id="Z514",
                            severity=code_severity("Z514"),
                            file_path=file_path,
                            line_no=i,
                            message=(
                                f"HTML <img> tag uses generic alt text '{alt_text.strip()}'. "
                                "Provide descriptive alt text for accessibility."
                            ),
                            match_text=alt_text.strip(),
                            col_start=_col_of(line, alt_text.strip()),
                            matched_line=line,
                        )
                    )

    return findings


def check_bare_urls(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z515: Detect raw URLs in prose that are not wrapped in Markdown link syntax."""
    from zenzic.core.rules import RuleFinding
    from zenzic.core.scanner import _INLINE_CODE_RE

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)

    for i, line in enumerate(lines, start=1):
        prev_blank = i > 1 and not lines[i - 2].strip()
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        if "http://" not in line and "https://" not in line:
            continue

        if _MARKDOWN_REF_DEF_RE.match(line):
            continue

        if prev_blank and _INDENTED_CODE_RE.match(line):
            continue

        masked = line
        masked = _HTML_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), masked)
        masked = _AUTOLINK_RE.sub(lambda m: " " * len(m.group(0)), masked)
        masked = _MARKDOWN_LINK_RE.sub(lambda m: " " * len(m.group(0)), masked)
        masked = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), masked)
        masked = _HTML_TAG_RE.sub(lambda m: " " * len(m.group(0)), masked)

        for m in _BARE_URL_RE.finditer(masked):
            raw_url = m.group(0)
            url = raw_url.rstrip(".,;:!?")
            if not url:
                continue
            findings.append(
                RuleFinding(
                    rule_id="Z515",
                    severity=code_severity("Z515"),
                    file_path=file_path,
                    line_no=i,
                    message=(
                        f"Bare URL '{url}' detected in prose. Wrap in angle brackets '<{url}>' "
                        f"or Markdown link syntax '[text]({url})'."
                    ),
                    match_text=url,
                    col_start=_col_of(line, url),
                    matched_line=line,
                )
            )

    return findings


def check_multiple_h1_headings(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z516: Emit if a document contains more than one H1 heading (# or <h1>)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)
    h1_count = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is not None and _h[0] == 1:
            _level, raw_title, _hline, _hraw = _h
            h1_count += 1
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()
            if h1_count > 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z516",
                        severity=code_severity("Z516"),
                        file_path=file_path,
                        line_no=_hline,
                        message=(
                            f"Multiple H1 headings detected in document ('{_short_heading(clean_title)}'). "
                            "Documents must have exactly one H1 title."
                        ),
                        match_text=clean_title,
                        col_start=_col_of(_hraw, clean_title),
                        matched_line=_hraw,
                    )
                )
            continue
        if _h is not None:
            continue

        # A `<h1>` named inside backticks is prose about HTML, not a heading.
        # Same shape as the tag-in-a-code-span defect closed in the slugifier.
        m_html = _HTML_H1_RE.search(_CODE_SPAN_RE.sub(lambda mm: " " * len(mm.group(0)), line))
        if m_html:
            h1_count += 1
            html_title = m_html.group(1).strip()
            if h1_count > 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z516",
                        severity=code_severity("Z516"),
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Multiple H1 headings detected in document ('{html_title}'). "
                            "Documents must have exactly one H1 title."
                        ),
                        match_text=html_title,
                        col_start=_col_of(line, html_title),
                        matched_line=line,
                    )
                )

    return findings


def check_heading_punctuation(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z517: Emit if a heading ends with invalid trailing punctuation (., :, ;)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is not None:
            _level, raw_title, _hline, _hraw = _h
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()
            if clean_title and clean_title[-1] in _TRAILING_INVALID_PUNCT:
                trailing = clean_title[-1]
                findings.append(
                    RuleFinding(
                        rule_id="Z517",
                        severity=code_severity("Z517"),
                        file_path=file_path,
                        line_no=_hline,
                        message=(
                            f"Heading '{clean_title}' ends with invalid trailing punctuation '{trailing}'. "
                            "Headings should not end with periods, colons, or semicolons."
                        ),
                        match_text=clean_title,
                        col_start=_col_of(_hraw, clean_title),
                        matched_line=_hraw,
                    )
                )

    return findings


def check_all_heading_rules(
    file_path: Path,
    text: str,
    anchors_out: dict[Path, set[str]] | None = None,
    *,
    containers: RegexPattern | None,
) -> list[RuleFinding]:
    """Combined single-pass check for Z510, Z513, Z516, Z517.

    Eliminates 3 redundant ``text.splitlines()`` + line-iteration passes that
    would occur when the 4 individual heading rules run sequentially.

    When *anchors_out* is provided, heading anchors are collected as a side
    effect, allowing :func:`anchors_in_file` to be skipped in the VSM pass.
    """
    from zenzic.core.rules import RuleFinding

    if anchors_out is not None:
        from zenzic.core.validator import (
            _EXPLICIT_ANCHOR_RE as _EXP_ANC_RE,
            _FN_DEF_RE as _FN_RE,
            _HTML_ID_RE as _HTML_RE,
            _INLINE_CODE_RE as _IC_RE,
            slug_heading,
        )

        anchors: set[str] = set()

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)
    prev_level = 0
    seen_headings: dict[str, int] = {}
    h1_count = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue
        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is not None:
            level, raw_title, _hline, _hraw = _h
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()

            # Collect heading anchor slug as side effect (if requested)
            if anchors_out is not None:
                anchors.add(slug_heading(raw_title))

            # Z510: skipped heading level
            if prev_level > 0 and level > prev_level + 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z510",
                        severity=code_severity("Z510"),
                        file_path=file_path,
                        line_no=_hline,
                        message=(
                            f"Heading level H{level} skips previous level H{prev_level} "
                            f"(expected H{prev_level + 1} or lower)."
                        ),
                        matched_line=_hraw,
                    )
                )
            prev_level = level

            # Z513: duplicate heading
            norm_title = _WS_COLLAPSE_RE.sub(" ", clean_title).lower()
            if norm_title:
                if norm_title in seen_headings:
                    findings.append(
                        RuleFinding(
                            rule_id="Z513",
                            severity=code_severity("Z513"),
                            file_path=file_path,
                            line_no=_hline,
                            message=f"Duplicate heading '{clean_title}' found (first occurrence at line {seen_headings[norm_title]}).",
                            match_text=clean_title,
                            col_start=_col_of(_hraw, clean_title),
                            matched_line=_hraw,
                        )
                    )
                else:
                    seen_headings[norm_title] = i

            # Z516: multiple H1
            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    findings.append(
                        RuleFinding(
                            rule_id="Z516",
                            severity=code_severity("Z516"),
                            file_path=file_path,
                            line_no=_hline,
                            message=(
                                f"Multiple H1 headings detected in document ('{_short_heading(clean_title)}'). "
                                "Documents must have exactly one H1 title."
                            ),
                            match_text=clean_title,
                            col_start=_col_of(_hraw, clean_title),
                            matched_line=_hraw,
                        )
                    )

            # Z517: trailing punctuation
            if clean_title and clean_title[-1] in _TRAILING_INVALID_PUNCT:
                findings.append(
                    RuleFinding(
                        rule_id="Z517",
                        severity=code_severity("Z517"),
                        file_path=file_path,
                        line_no=_hline,
                        message=(
                            f"Heading '{clean_title}' ends with invalid trailing punctuation '{clean_title[-1]}'. "
                            "Headings should not end with periods, colons, or semicolons."
                        ),
                        match_text=clean_title,
                        col_start=_col_of(_hraw, clean_title),
                        matched_line=_hraw,
                    )
                )

        else:
            # Z516: HTML <h1> tags. A `<h1>` named inside backticks is prose
            # about HTML, not a heading -- same shape as the tag-in-a-code-span
            # defect closed in the slugifier.
            m_html = _HTML_H1_RE.search(_CODE_SPAN_RE.sub(lambda mm: " " * len(mm.group(0)), line))
            if m_html:
                h1_count += 1
                html_title = m_html.group(1).strip()
                if h1_count > 1:
                    findings.append(
                        RuleFinding(
                            rule_id="Z516",
                            severity=code_severity("Z516"),
                            file_path=file_path,
                            line_no=_hline,
                            message=(
                                f"Multiple H1 headings detected in document ('{html_title}'). "
                                "Documents must have exactly one H1 title."
                            ),
                            match_text=html_title,
                            col_start=_col_of(_hraw, html_title),
                            matched_line=_hraw,
                        )
                    )

            # Collect non-heading anchors as side effect (if requested)
            if anchors_out is not None:
                _cl = _IC_RE.sub("", line)
                for _m in _EXP_ANC_RE.finditer(_cl):
                    anchors.add(_m.group(1).lower())
                _fn = _FN_RE.match(_cl)
                if _fn:
                    anchors.add(f"fn:{_fn.group(1).strip()}")
                for _m in _HTML_RE.finditer(_cl):
                    anchors.add(_m.group(1).lower())

    if anchors_out is not None:
        anchors_out[file_path] = anchors

    return findings


_PASSIVE_VOICE_RE = re.compile(
    r"(?i)\b(is|are|was|were|be|been|being)\s+([a-z]+(?:ed|en)|done|seen|made|found|built|written|read|set|put|known|taken|chosen|given|held|left|sent)\b"
)
_INLINE_CODE_SPAN_RE = re.compile(r"`[^`]+`")
#: Words the second group of _PASSIVE_VOICE_RE accepts that are not past
#: participles. Measured on 2026-09-17 over 1,629 findings on this
#: repository's docs: `is often` x11, `is open` x2, `between` x2, `even`,
#: `then`, `when`, `green` -- 19 findings, every one a word ending in -en.
_NOT_A_PARTICIPLE: frozenset[str] = frozenset(
    {
        "often",
        "open",
        "even",
        "seven",
        "eleven",
        "between",
        "when",
        "then",
        "green",
        "sudden",
        "wooden",
        "golden",
        "oxygen",
        "kitchen",
        "garden",
        "linen",
        "amen",
        "need",
        "red",
        "indeed",
        "embed",
        "speed",
        "hundred",
        "bed",
        "fed",
        "shed",
        "wed",
    }
)


def check_passive_voice(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z518: Heuristic RE2 detection of passive voice constructs in prose (opt-in)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)

    for i, line in enumerate(lines, start=1):
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        # Mask inline code, HTML tags/comments, and link targets
        masked = _blank(_INLINE_CODE_SPAN_RE, line)
        masked = _blank(_HTML_COMMENT_RE, masked)
        masked = _blank(_HTML_TAG_RE, masked)
        masked = _blank(_MARKDOWN_LINK_RE, masked)

        for match in _PASSIVE_VOICE_RE.finditer(masked):
            matched_text = match.group(0)
            # RE2 has no lookaround, so the two exclusions are checked here:
            # a word that merely ends in -en/-ed (`is often`, `is open`) and a
            # participle that is the head of a hyphenated compound (`read-only`).
            if match.group(2).lower() in _NOT_A_PARTICIPLE:
                continue
            if masked[match.end() : match.end() + 1] == "-":
                continue
            findings.append(
                RuleFinding(
                    rule_id="Z518",
                    severity=code_severity("Z518"),
                    file_path=file_path,
                    line_no=i,
                    message=(
                        f"Passive voice construct '{matched_text}' detected. "
                        "Consider using active voice for clearer technical writing."
                    ),
                    match_text=matched_text,
                    col_start=match.start(),
                    matched_line=line,
                )
            )

    return findings


def check_weasel_words(
    file_path: Path,
    text: str,
    weasel_words: list[str] | None = None,
    *,
    containers: RegexPattern | None,
) -> list[RuleFinding]:
    """Z519: Detect weasel words in technical prose based on configured weasel_words list (opt-in)."""
    from zenzic.core.rules import RuleFinding

    if not weasel_words:
        return []

    escaped = [re.escape(w.strip()) for w in weasel_words if w.strip()]
    if not escaped:
        return []

    pattern = re.compile(rf"(?i)\b({'|'.join(escaped)})\b")

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)

    for i, line in enumerate(lines, start=1):
        # The tracker answers "is this frontmatter", so this loop no longer
        # carries its own copy of the rule. Thirteen copies did; they accepted
        # only `---` and not YAML's `...` document-end marker, and they skipped
        # lines *before* feeding the tracker, which left it computing container
        # and paragraph state on an amputated document.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            continue

        if _fence.inside:
            continue

        masked = _blank(_INLINE_CODE_SPAN_RE, line)
        masked = _blank(_HTML_COMMENT_RE, masked)
        masked = _blank(_HTML_TAG_RE, masked)
        masked = _blank(_MARKDOWN_LINK_RE, masked)

        for match in pattern.finditer(masked):
            matched_word = match.group(0)
            findings.append(
                RuleFinding(
                    rule_id="Z519",
                    severity=code_severity("Z519"),
                    file_path=file_path,
                    line_no=i,
                    message=(
                        f"Weasel word '{matched_word}' detected. "
                        "Consider using direct, precise language instead."
                    ),
                    match_text=matched_word,
                    col_start=match.start(),
                    matched_line=line,
                )
            )

    return findings


_LIST_MARKER_PREFIX_RE = re.compile(r"^(\*|-|\+|\d+\.|\d+\))\s+")
_CONJUNCTION_START_RE = re.compile(r"^(and|or|but|nor|so|yet)\s+", re.IGNORECASE)


def check_malformed_lists(
    file_path: Path, text: str, *, containers: RegexPattern | None
) -> list[RuleFinding]:
    """Z520: Detect malformed/fake lists in paragraphs lacking Markdown list markers."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    _fence = BlockTracker(containers)
    in_html_script = False
    in_html_style = False

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # The tracker decides what is frontmatter; this loop asks it. Its index
        # is zero-based, which is why its copy read `i == 0` -- the same rule,
        # not a divergence, and now not a copy either.
        if _fence.feed(line) or _fence.in_frontmatter or _fence.in_indented_code:
            i += 1
            continue

        if _fence.inside or not stripped:
            i += 1
            continue

        if "<script" in stripped.lower():
            in_html_script = True
        if in_html_script:
            if "</script>" in stripped.lower():
                in_html_script = False
            i += 1
            continue

        if "<style" in stripped.lower():
            in_html_style = True
        if in_html_style:
            if "</style>" in stripped.lower():
                in_html_style = False
            i += 1
            continue

        # Check for consecutive run of 3+ lines ending with ';' or ','
        run_indices: list[int] = []
        open_parens = 0
        j = i
        while j < n:
            curr_line = lines[j]
            curr_stripped = curr_line.strip()
            if not curr_stripped:
                break
            if (
                curr_stripped.startswith("```")
                or curr_stripped.startswith("~~~")
                or curr_stripped.startswith("#")
                or curr_stripped.startswith("|")
                or _LIST_MARKER_PREFIX_RE.match(curr_stripped)
            ):
                break

            open_parens += curr_stripped.count("(") - curr_stripped.count(")")
            if open_parens > 0 or curr_stripped.startswith("(") or curr_stripped.endswith(")"):
                break

            if curr_stripped.endswith(";") or curr_stripped.endswith(","):
                if curr_stripped.endswith(",") and _CONJUNCTION_START_RE.match(curr_stripped):
                    break
                run_indices.append(j)
                j += 1
            elif (
                len(run_indices) >= 2
                and curr_stripped.endswith(".")
                and not _CONJUNCTION_START_RE.match(curr_stripped)
            ):
                run_indices.append(j)
                j += 1
                break
            else:
                break

        punct_count = sum(
            1
            for idx in run_indices
            if lines[idx].strip().endswith(";") or lines[idx].strip().endswith(",")
        )
        if len(run_indices) >= 3 and punct_count >= 3:
            first_line_no = run_indices[0] + 1
            matched_snippet = "\n".join(lines[idx] for idx in run_indices)
            findings.append(
                RuleFinding(
                    rule_id="Z520",
                    severity=code_severity("Z520"),
                    file_path=file_path,
                    line_no=first_line_no,
                    message=(
                        f"Malformed list detected at line {first_line_no}: paragraph contains "
                        f"{len(run_indices)} consecutive lines formatted as a list with semicolons/commas "
                        "without proper Markdown list markers ('- ', '* ', '1. ')."
                    ),
                    match_text=matched_snippet,
                    col_start=len(lines[run_indices[0]]) - len(lines[run_indices[0]].lstrip()),
                    matched_line=lines[run_indices[0]],
                )
            )
            i = j
        else:
            i += 1

    return findings


def check_required_table_columns(
    file_path: Path,
    text: str,
    required_table_columns: dict[str, list[str]],
) -> list[RuleFinding]:
    """Z521: Detect Markdown tables missing required column headers."""
    if not required_table_columns:
        return []

    from zenzic.core.ast import Heading, TableNode
    from zenzic.core.parser import parse
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    ast = parse(text)
    current_heading = ""

    for child in ast.children:
        if isinstance(child, Heading):
            current_heading = "".join(getattr(c, "text", "") for c in child.children).strip()
            continue

        if isinstance(child, TableNode):
            table_headers = [h.strip() for h in child.headers]
            lower_headers = {h.lower() for h in table_headers}

            for ctx_pattern, req_cols in required_table_columns.items():
                applies = False
                if ctx_pattern == "*":
                    applies = True
                elif current_heading:
                    with contextlib.suppress(Exception):
                        if re.search(ctx_pattern, current_heading):
                            applies = True

                if applies:
                    for req_col in req_cols:
                        if req_col.lower() not in lower_headers:
                            findings.append(
                                RuleFinding(
                                    rule_id="Z521",
                                    severity=code_severity("Z521"),
                                    file_path=file_path,
                                    line_no=child.line_no,
                                    message=(
                                        f"Table missing required column '{req_col}' "
                                        f"(declared in [policies].required_table_columns under context '{ctx_pattern}')."
                                    ),
                                    matched_line=child.raw_lines[0] if child.raw_lines else "",
                                )
                            )

    return findings


def check_table_cell_enums(
    file_path: Path,
    text: str,
    table_cell_enums: dict[str, list[str]],
) -> list[RuleFinding]:
    """Z522: Detect table cells containing values outside allowed enum lists."""
    if not table_cell_enums:
        return []

    from zenzic.core.ast import TableNode
    from zenzic.core.parser import parse
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    ast = parse(text)

    # Normalize enum map: lower_col_name -> (original_col_name, set_of_lower_allowed_values, original_allowed_list)
    enum_map: dict[str, tuple[str, set[str], list[str]]] = {}
    for col_name, allowed_vals in table_cell_enums.items():
        norm_vals = {v.strip("`'\" ").lower() for v in allowed_vals}
        enum_map[col_name.lower()] = (col_name, norm_vals, allowed_vals)

    for child in ast.children:
        if not isinstance(child, TableNode):
            continue

        # Match columns
        matched_cols: list[tuple[int, str, set[str], list[str]]] = []
        for idx, h in enumerate(child.headers):
            h_clean = h.strip().lower()
            if h_clean in enum_map:
                orig_name, norm_vals, orig_list = enum_map[h_clean]
                matched_cols.append((idx, orig_name, norm_vals, orig_list))

        if not matched_cols:
            continue

        for row in child.rows:
            if row.is_header:
                continue

            for col_idx, orig_name, norm_vals, orig_list in matched_cols:
                if col_idx < len(row.cells):
                    cell = row.cells[col_idx]
                    cell_val = cell.text.strip("`'\" ")
                    if cell_val and cell_val.lower() not in norm_vals:
                        line_no = child.line_no + row.row_index + 1
                        findings.append(
                            RuleFinding(
                                rule_id="Z522",
                                severity=code_severity("Z522"),
                                file_path=file_path,
                                line_no=line_no,
                                message=(
                                    f"Table cell value '{cell.text}' in column '{orig_name}' is not in allowed "
                                    f"enum list {orig_list} (declared in [policies].table_cell_enums)."
                                ),
                                matched_line=row.raw_line,
                            )
                        )

    return findings


def check_heading_order(
    file_path: Path,
    text: str,
    required_heading_order: list[str],
    *,
    containers: RegexPattern | None,
) -> list[RuleFinding]:
    """Z523: Detect headings that violate the required sequential order."""
    if not required_heading_order:
        return []

    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()

    compiled_patterns = []
    for idx, pat in enumerate(required_heading_order):
        with contextlib.suppress(Exception):
            compiled_patterns.append((idx, pat, re.compile(pat)))

    if not compiled_patterns:
        return []

    max_idx_seen = -1
    last_matched_pat = ""
    _fence = BlockTracker(containers)

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if _fence.feed(line) or _fence.in_indented_code:
            continue
        if _fence.inside:
            continue

        _h = _heading_here(stripped, line, i, lines, _fence)
        if _h is None:
            continue

        _level, heading_title, _hline, _hraw = _h

        # Check if heading_title matches any pattern in required_heading_order
        for p_idx, p_str, p_re in compiled_patterns:
            if p_re.search(heading_title):
                if p_idx < max_idx_seen:
                    findings.append(
                        RuleFinding(
                            rule_id="Z523",
                            severity=code_severity("Z523"),
                            file_path=file_path,
                            line_no=_hline,
                            message=(
                                f"Heading '{heading_title}' matches pattern '{p_str}' (order position {p_idx + 1}) "
                                f"but appears after heading matching '{last_matched_pat}' (order position {max_idx_seen + 1}). "
                                "Headings must appear in strictly ascending sequential order."
                            ),
                            matched_line=_hraw,
                        )
                    )
                else:
                    max_idx_seen = p_idx
                    last_matched_pat = p_str
                break

    return findings
