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

from pathlib import Path
from typing import TYPE_CHECKING

import zenzic.core.regex as re


if TYPE_CHECKING:
    from zenzic.core.rules import RuleFinding

# ATX Heading regex matching # to ######
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


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
            if i + 1 == n or text[i + 1].isspace():
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


def check_heading_hierarchy(file_path: Path, text: str) -> list[RuleFinding]:
    """Z510: Detect skipped heading levels (e.g. H3 immediately following H1)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    prev_level = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        m = _ATX_HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            if prev_level > 0 and level > prev_level + 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z510",
                        severity="warning",
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Heading level H{level} skips previous level H{prev_level} "
                            f"(expected H{prev_level + 1} or lower)."
                        ),
                        matched_line=line,
                    )
                )
            prev_level = level

    return findings


_BLOCK_TAGS = {
    "div",
    "section",
    "article",
    "aside",
    "header",
    "footer",
    "nav",
    "figure",
    "figcaption",
    "details",
    "summary",
    "form",
    "fieldset",
    "table",
    "tbody",
    "thead",
    "tfoot",
    "tr",
    "td",
    "th",
    "pre",
    "script",
    "style",
    "main",
    "iframe",
    "blockquote",
    "p",
    "ul",
    "ol",
    "li",
}
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
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


def _mask_html_blocks(text: str) -> str:
    """Mask raw HTML block elements and tags with spaces of equal length, preserving line breaks."""
    lines = text.split("\n")
    result: list[str] = []
    html_depth = 0

    open_tag_re = re.compile(r"<([a-zA-Z1-6]+)\b([^>]*)/?>", re.IGNORECASE)
    close_tag_re = re.compile(r"</([a-zA-Z1-6]+)\s*>", re.IGNORECASE)

    for line in lines:
        opens = []
        for m in open_tag_re.finditer(line):
            tag = m.group(1).lower()
            full_match = m.group(0)
            if tag in _BLOCK_TAGS and tag not in _VOID_TAGS and not full_match.endswith("/>"):
                opens.append(tag)

        closes = [
            m.group(1).lower()
            for m in close_tag_re.finditer(line)
            if m.group(1).lower() in _BLOCK_TAGS
        ]
        net_change = len(opens) - len(closes)

        if html_depth > 0 or opens:
            result.append(" " * len(line))
            html_depth = max(0, html_depth + net_change)
        else:
            result.append(re.sub(r"<[^>]+>", lambda m: " " * len(m.group(0)), line))

    return "\n".join(result)


def check_sentence_lengths(file_path: Path, text: str, max_words: int = 40) -> list[RuleFinding]:
    """Z511: Detect sentences exceeding max_words readability threshold."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    text_masked = _mask_html_blocks(text)
    lines = text_masked.splitlines()
    in_code_block = False
    in_frontmatter = False

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
                        severity="warning",
                        file_path=file_path,
                        line_no=start_line,
                        message=f"Sentence of {len(words)} words exceeds maximum limit of {max_words} words.",
                        match_text=preview,
                    )
                )
        parts.clear()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Handle frontmatter
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        # Handle code blocks
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            _flush_and_check(current_sentence_parts, current_start_line)
            continue

        if in_code_block:
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
        if re.search(r"[.!?;](?:\s+|$)", stripped):
            _flush_and_check(current_sentence_parts, current_start_line)

    # Flush any remaining buffer at EOF
    return findings


def check_empty_sections(file_path: Path, text: str) -> list[RuleFinding]:
    """Z512: Detect headings with zero body content before next heading or EOF."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False

    current_heading: str | None = None
    current_heading_line: int = 0
    has_body_content = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            if current_heading is not None:
                has_body_content = True
            continue

        if in_code_block:
            continue

        m = _ATX_HEADING_RE.match(stripped)
        if m:
            # Entering a new heading — evaluate previous section
            if current_heading is not None and not has_body_content:
                findings.append(
                    RuleFinding(
                        rule_id="Z512",
                        severity="warning",
                        file_path=file_path,
                        line_no=current_heading_line,
                        message=f"Heading section '{current_heading}' contains no body content before next section or EOF.",
                        match_text=current_heading,
                    )
                )
            current_heading = m.group(2).strip()
            current_heading_line = i
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
                severity="warning",
                file_path=file_path,
                line_no=current_heading_line,
                message=f"Heading section '{current_heading}' contains no body content before next section or EOF.",
                match_text=current_heading,
            )
        )

    return findings


# ─── Z513, Z514, Z515, Z516, Z517 ─────────────────────────────────────────────

_HEADING_ANCHOR_STRIP_RE = re.compile(r"\s*\{#[^}]+\}\s*$")
_WS_COLLAPSE_RE = re.compile(r"\s+")
_TRAILING_INVALID_PUNCT = {".", ":", ";"}
_HTML_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.IGNORECASE)

_GENERIC_ALT_SET = frozenset({
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
})

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
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
_AUTOLINK_RE = re.compile(r"<https?://[^>]+>")
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\([^)]+\)")
_MARKDOWN_REF_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*\S+")


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


def check_duplicate_headings(file_path: Path, text: str) -> list[RuleFinding]:
    """Z513: Emit if two headings in the same document resolve to the exact same text."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False
    seen_headings: dict[str, int] = {}

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        m = _ATX_HEADING_RE.match(stripped)
        if m:
            raw_title = m.group(2).strip()
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()
            norm_title = _WS_COLLAPSE_RE.sub(" ", clean_title).lower()
            if not norm_title:
                continue

            if norm_title in seen_headings:
                first_line = seen_headings[norm_title]
                findings.append(
                    RuleFinding(
                        rule_id="Z513",
                        severity="warning",
                        file_path=file_path,
                        line_no=i,
                        message=f"Duplicate heading '{clean_title}' found (first occurrence at line {first_line}).",
                        match_text=clean_title,
                        matched_line=line,
                    )
                )
            else:
                seen_headings[norm_title] = i

    return findings


def check_generic_image_alt_text(file_path: Path, text: str) -> list[RuleFinding]:
    """Z514: Emit if an image tag (![]() or <img>) uses generic filler words as alt text."""
    from zenzic.core.rules import RuleFinding
    from zenzic.core.scanner import _INLINE_CODE_RE, _RE_HTML_ALT, _RE_HTML_IMG, _RE_IMAGE_INLINE

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
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
                        severity="warning",
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Image '{url}' uses generic alt text '{alt_text.strip()}'. "
                            "Provide descriptive alt text for accessibility."
                        ),
                        match_text=alt_text.strip(),
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
                            severity="warning",
                            file_path=file_path,
                            line_no=i,
                            message=(
                                f"HTML <img> tag uses generic alt text '{alt_text.strip()}'. "
                                "Provide descriptive alt text for accessibility."
                            ),
                            match_text=alt_text.strip(),
                            matched_line=line,
                        )
                    )

    return findings


def check_bare_urls(file_path: Path, text: str) -> list[RuleFinding]:
    """Z515: Detect raw URLs in prose that are not wrapped in Markdown link syntax."""
    from zenzic.core.rules import RuleFinding
    from zenzic.core.scanner import _INLINE_CODE_RE

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if _MARKDOWN_REF_DEF_RE.match(line):
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
                    severity="warning",
                    file_path=file_path,
                    line_no=i,
                    message=(
                        f"Bare URL '{url}' detected in prose. Wrap in angle brackets '<{url}>' "
                        f"or Markdown link syntax '[text]({url})'."
                    ),
                    match_text=url,
                    matched_line=line,
                )
            )

    return findings


def check_multiple_h1_headings(file_path: Path, text: str) -> list[RuleFinding]:
    """Z516: Emit if a document contains more than one H1 heading (# or <h1>)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False
    h1_count = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        m = _ATX_HEADING_RE.match(stripped)
        if m and len(m.group(1)) == 1:
            h1_count += 1
            raw_title = m.group(2).strip()
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()
            if h1_count > 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z516",
                        severity="error",
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Multiple H1 headings detected in document ('{clean_title}'). "
                            "Documents must have exactly one H1 title."
                        ),
                        match_text=clean_title,
                        matched_line=line,
                    )
                )
            continue

        m_html = _HTML_H1_RE.search(line)
        if m_html:
            h1_count += 1
            html_title = m_html.group(1).strip()
            if h1_count > 1:
                findings.append(
                    RuleFinding(
                        rule_id="Z516",
                        severity="error",
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Multiple H1 headings detected in document ('{html_title}'). "
                            "Documents must have exactly one H1 title."
                        ),
                        match_text=html_title,
                        matched_line=line,
                    )
                )

    return findings


def check_heading_punctuation(file_path: Path, text: str) -> list[RuleFinding]:
    """Z517: Emit if a heading ends with invalid trailing punctuation (., :, ;)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        m = _ATX_HEADING_RE.match(stripped)
        if m:
            raw_title = m.group(2).strip()
            clean_title = _HEADING_ANCHOR_STRIP_RE.sub("", raw_title).strip()
            if clean_title and clean_title[-1] in _TRAILING_INVALID_PUNCT:
                trailing = clean_title[-1]
                findings.append(
                    RuleFinding(
                        rule_id="Z517",
                        severity="warning",
                        file_path=file_path,
                        line_no=i,
                        message=(
                            f"Heading '{clean_title}' ends with invalid trailing punctuation '{trailing}'. "
                            "Headings should not end with periods, colons, or semicolons."
                        ),
                        match_text=clean_title,
                        matched_line=line,
                    )
                )

    return findings


_PASSIVE_VOICE_RE = re.compile(
    r"(?i)\b(is|are|was|were|be|been|being)\s+([a-z]+(?:ed|en)|done|seen|made|found|built|written|read|set|put|known|taken|chosen|given|held|left|sent)\b"
)
_INLINE_CODE_SPAN_RE = re.compile(r"`[^`]+`")


def check_passive_voice(file_path: Path, text: str) -> list[RuleFinding]:
    """Z518: Heuristic RE2 detection of passive voice constructs in prose (opt-in)."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Mask inline code, HTML tags/comments, and link targets
        masked = _INLINE_CODE_SPAN_RE.sub(" ", line)
        masked = _HTML_COMMENT_RE.sub(" ", masked)
        masked = _HTML_TAG_RE.sub(" ", masked)
        masked = _MARKDOWN_LINK_RE.sub(" ", masked)

        for match in _PASSIVE_VOICE_RE.finditer(masked):
            matched_text = match.group(0)
            findings.append(
                RuleFinding(
                    rule_id="Z518",
                    severity="warning",
                    file_path=file_path,
                    line_no=i,
                    message=(
                        f"Passive voice construct '{matched_text}' detected. "
                        "Consider using active voice for clearer technical writing."
                    ),
                    match_text=matched_text,
                    matched_line=line,
                )
            )

    return findings


def check_weasel_words(
    file_path: Path,
    text: str,
    weasel_words: list[str] | None = None,
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
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        masked = _INLINE_CODE_SPAN_RE.sub(" ", line)
        masked = _HTML_COMMENT_RE.sub(" ", masked)
        masked = _HTML_TAG_RE.sub(" ", masked)
        masked = _MARKDOWN_LINK_RE.sub(" ", masked)

        for match in pattern.finditer(masked):
            matched_word = match.group(0)
            findings.append(
                RuleFinding(
                    rule_id="Z519",
                    severity="warning",
                    file_path=file_path,
                    line_no=i,
                    message=(
                        f"Weasel word '{matched_word}' detected. "
                        "Consider using direct, precise language instead."
                    ),
                    match_text=matched_word,
                    matched_line=line,
                )
            )

    return findings

