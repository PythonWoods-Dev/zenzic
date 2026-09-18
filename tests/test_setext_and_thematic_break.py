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
