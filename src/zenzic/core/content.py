# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Deterministic Semantic Linting & Readability Metrics engine for Zenzic.

Provides mathematical content quality evaluation for Markdown/MDX graphs,
enforcing heading hierarchy (Z510), sentence length limits (Z511), and
empty section detection (Z512) with strict line-number fidelity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from zenzic.core.rules import RuleFinding

# ATX Heading regex matching # to ######
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
# Sentence delimiter matching ., !, or ? followed by whitespace or end of string
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


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


def check_sentence_lengths(file_path: Path, text: str, max_words: int = 40) -> list[RuleFinding]:
    """Z511: Detect sentences exceeding max_words readability threshold."""
    from zenzic.core.rules import RuleFinding

    findings: list[RuleFinding] = []
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = False

    # Collect prose sentences line by line, preserving starting line number
    current_sentence_parts: list[str] = []
    current_start_line = 1

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
            # Flush existing sentence accumulator on code block boundary
            if current_sentence_parts:
                full_sent = " ".join(current_sentence_parts)
                words = full_sent.split()
                if len(words) > max_words:
                    preview = full_sent[:50] + "..." if len(full_sent) > 50 else full_sent
                    findings.append(
                        RuleFinding(
                            rule_id="Z511",
                            severity="warning",
                            file_path=file_path,
                            line_no=current_start_line,
                            message=f"Sentence of {len(words)} words exceeds maximum limit of {max_words} words.",
                            match_text=preview,
                        )
                    )
                current_sentence_parts.clear()
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
            if current_sentence_parts:
                full_sent = " ".join(current_sentence_parts)
                words = full_sent.split()
                if len(words) > max_words:
                    preview = full_sent[:50] + "..." if len(full_sent) > 50 else full_sent
                    findings.append(
                        RuleFinding(
                            rule_id="Z511",
                            severity="warning",
                            file_path=file_path,
                            line_no=current_start_line,
                            message=f"Sentence of {len(words)} words exceeds maximum limit of {max_words} words.",
                            match_text=preview,
                        )
                    )
                current_sentence_parts.clear()
            
            if not is_bullet:
                continue

        if not current_sentence_parts:
            current_start_line = i

        current_sentence_parts.append(stripped)

        # Check if line contains sentence terminators
        if re.search(r"[.!?](?:\s+|$)", stripped):
            full_sent = " ".join(current_sentence_parts)
            # Split into individual sentences if multiple exist in accumulated buffer
            raw_sentences = _SENTENCE_SPLIT_RE.split(full_sent)
            for s in raw_sentences:
                words = s.split()
                if len(words) > max_words:
                    preview = s[:50] + "..." if len(s) > 50 else s
                    findings.append(
                        RuleFinding(
                            rule_id="Z511",
                            severity="warning",
                            file_path=file_path,
                            line_no=current_start_line,
                            message=f"Sentence of {len(words)} words exceeds maximum limit of {max_words} words.",
                            match_text=preview,
                        )
                    )
            current_sentence_parts.clear()

    # Flush any remaining buffer at EOF
    if current_sentence_parts:
        full_sent = " ".join(current_sentence_parts)
        words = full_sent.split()
        if len(words) > max_words:
            preview = full_sent[:50] + "..." if len(full_sent) > 50 else full_sent
            findings.append(
                RuleFinding(
                    rule_id="Z511",
                    severity="warning",
                    file_path=file_path,
                    line_no=current_start_line,
                    message=f"Sentence of {len(words)} words exceeds maximum limit of {max_words} words.",
                    match_text=preview,
                )
            )

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
