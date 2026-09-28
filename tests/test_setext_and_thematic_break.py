# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Setext headings and thematic breaks, derived from CommonMark §4.2 and §4.3.

The measured defect was two lines: two ATX `H1`s fire `Z516`, a setext `H1`
plus an ATX one does not, because the rule counted one. The positive control
ran in the same scan, so "no finding" could not be read as "rule off".

§4.2 — a setext heading is a paragraph line followed by an underline of `=`
(H1) or `-` (H2), the underline indented at most three spaces.
§4.3 — a thematic break is three or more `-`, `_` or `*`, and needs no
paragraph above it.

**They coincide on `---`, and only the line above decides.** That bit already
existed in `BlockTracker` for indented code, which is why this needed no second
state machine.
"""

from __future__ import annotations

import pytest

from zenzic.core.ast import BlockTracker, setext_heading


def _setexts(doc: str) -> list[tuple[int, str]]:
    tracker = BlockTracker()
    found = []
    for line in doc.splitlines():
        tracker.feed(line)
        h = setext_heading(tracker)
        if h is not None:
            found.append(h)
    return found


# ── §4.2: what is a setext heading ───────────────────────────────────────────


@pytest.mark.parametrize(
    "underline,level", [("=", 1), ("==", 1), ("=" * 40, 1), ("-", 2), ("--", 2), ("-" * 40, 2)]
)
def test_a_run_of_either_character_underlines_a_paragraph(underline: str, level: int) -> None:
    assert _setexts(f"Titolo\n{underline}\n") == [(level, "Titolo")]


@pytest.mark.parametrize("indent", ["", " ", "  ", "   "])
def test_up_to_three_spaces_of_indentation_is_still_an_underline(indent: str) -> None:
    assert _setexts(f"Titolo\n{indent}===\n") == [(1, "Titolo")]


def test_four_spaces_is_not_an_underline() -> None:
    """Four spaces is an indented code block, not a heading."""
    assert _setexts("Titolo\n    ===\n") == []


def test_trailing_whitespace_is_allowed() -> None:
    assert _setexts("Titolo\n===   \n") == [(1, "Titolo")]


def test_other_characters_on_the_line_disqualify_it() -> None:
    for line in ("=== x", "x ===", "=-=", "== =="):
        assert _setexts(f"Titolo\n{line}\n") == [], line


# ── §4.3: the thematic break, and the boundary ───────────────────────────────


def test_a_break_after_a_blank_line_is_not_a_heading() -> None:
    """The whole disambiguation: no paragraph above, so `---` is a break."""
    assert _setexts("Testo.\n\n---\n\nAltro.\n") == []


def test_the_same_characters_under_text_are_a_heading() -> None:
    assert _setexts("Testo.\n---\n") == [(2, "Testo.")]


def test_a_break_at_the_start_of_a_document_is_not_a_heading() -> None:
    assert _setexts("***\n\nTesto.\n") == []


def test_asterisks_and_underscores_are_breaks_and_never_underlines() -> None:
    """§4.2 allows only `=` and `-`; §4.3 allows three characters."""
    for ch in ("***", "___"):
        assert _setexts(f"Testo.\n{ch}\n") == [], ch


# ── Frontmatter, which is neither ────────────────────────────────────────────


@pytest.mark.parametrize("terminator", ["---", "..."])
def test_a_frontmatter_terminator_is_not_a_heading(terminator: str) -> None:
    """Both YAML terminators close the block; neither mints an H2 from it."""
    doc = f"---\ntitle: x\nauthor: y\n{terminator}\n\nTesto.\n"
    assert _setexts(doc) == []


@pytest.mark.parametrize("terminator", ["---", "..."])
def test_the_body_after_either_terminator_is_content(terminator: str) -> None:
    """The defect this closes: with `...`, the whole body was frontmatter."""
    doc = f"---\ntitle: x\n{terminator}\n\nTitolo\n======\n"
    assert _setexts(doc) == [(1, "Titolo")]


def test_a_fence_inside_frontmatter_does_not_open() -> None:
    """Frontmatter is YAML: a line of backticks in it is a string."""
    tracker = BlockTracker()
    for line in "---\nesempio: |\n  ```py\n  x\n  ```\n---\n\nTesto.\n".splitlines():
        tracker.feed(line)
    assert tracker.inside is False


# ── Inside a fence, nothing is a heading ─────────────────────────────────────


def test_an_underline_inside_a_fence_is_code() -> None:
    assert _setexts("```\nTitolo\n======\n```\n") == []


# ── End to end, both directions ──────────────────────────────────────────────


def test_a_setext_h1_and_an_atx_h1_together_fire_z516(tmp_path) -> None:
    """The batch's own measurement, as a test."""
    from zenzic.core.content import check_multiple_h1_headings

    doc = "Primo\n=====\n\nTesto.\n\n# Secondo\n\nAltro.\n"
    findings = check_multiple_h1_headings(tmp_path / "d.md", doc, containers=None)
    assert [f.rule_id for f in findings] == ["Z516"]


def test_two_atx_h1_still_fire_z516(tmp_path) -> None:
    """The positive control: the rule is on, so the assertion above means something."""
    from zenzic.core.content import check_multiple_h1_headings

    doc = "# Primo\n\nTesto.\n\n# Secondo\n\nAltro.\n"
    findings = check_multiple_h1_headings(tmp_path / "d.md", doc, containers=None)
    assert [f.rule_id for f in findings] == ["Z516"]


def test_one_setext_h1_alone_fires_nothing(tmp_path) -> None:
    """The other direction: recognising the construct must not invent a finding."""
    from zenzic.core.content import check_multiple_h1_headings

    doc = "Primo\n=====\n\nTesto.\n\n## Secondo\n\nAltro.\n"
    assert check_multiple_h1_headings(tmp_path / "d.md", doc, containers=None) == []


def test_the_finding_points_at_the_text_line_not_the_underline(tmp_path) -> None:
    """§4.2 puts the heading on two lines; the reader is pointed at the words."""
    from zenzic.core.content import check_multiple_h1_headings

    doc = "# Primo\n\nTesto.\n\nSecondo\n=======\n"
    findings = check_multiple_h1_headings(tmp_path / "d.md", doc, containers=None)
    assert len(findings) == 1
    assert findings[0].line_no == 5


# ── §5.1: a block quote is not a paragraph ───────────────────────────────────


def test_an_underline_outside_a_quote_does_not_close_a_paragraph_inside_it() -> None:
    """The regression this component introduced on the day it learned setext.

    `> **Bold note**` followed by a line of dashes read as an `H2` whose text was
    the whole block quote, marker included — and `Z512` then reported it as a
    heading section with no body. Measured against this file's parent commit:
    the same input produced nothing there, so the defect was mine and new.

    CommonMark §5.1: `>` opens a block quote. A setext underline outside it
    cannot close a paragraph inside it.
    """
    assert _setexts("> **Scope Clarification — a bold note**\n---\n") == []


def test_a_setext_heading_inside_a_quote_is_recognised_without_its_marker() -> None:
    """Both lines quoted: a real setext heading, and its text is the content."""
    assert _setexts("> Titolo citato\n> ---\n") == [(2, "Titolo citato")]


def test_an_underline_inside_a_quote_does_not_close_a_paragraph_outside_it() -> None:
    """The mirror of the first: the levels must agree in both directions."""
    assert _setexts("Testo non citato\n> ---\n") == []


# ── The message quotes a heading, not an essay ───────────────────────────────


def test_a_long_heading_is_bounded_in_the_message(tmp_path) -> None:
    """A heading is a line; a message that quotes one must not print a paragraph.

    The bound was added because the defect above printed an entire block quote
    as a title. The defect is fixed; the bound stays, because a legitimately
    long heading should not do the same to a terminal.
    """
    from zenzic.core.content import check_empty_sections

    long_title = "Un titolo legittimo ma molto molto lungo che supera abbondantemente la soglia"
    doc = f"# T\n\ntesto\n\n## {long_title}\n\n## Altra\n\ncorpo\n"
    findings = check_empty_sections(tmp_path / "d.md", doc, containers=None)
    assert len(findings) == 1
    assert long_title not in findings[0].message
    assert "…" in findings[0].message


def test_a_short_heading_is_quoted_whole(tmp_path) -> None:
    """The positive control: the bound must not truncate what fits."""
    from zenzic.core.content import check_empty_sections

    doc = "# T\n\ntesto\n\n## Breve\n\n## Altra\n\ncorpo\n"
    findings = check_empty_sections(tmp_path / "d.md", doc, containers=None)
    assert len(findings) == 1
    assert "'Breve'" in findings[0].message
    assert "…" not in findings[0].message
