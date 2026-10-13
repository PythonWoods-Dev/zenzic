# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""BlockTracker against CommonMark 0.31.2 §4.5.

Derived from the specification's clauses, not from the defects that prompted
the rewrite. That is the point: the previous model was built case by case from
whatever corpus had just broken it, which is why each new corpus found another.

Each test names the clause it enforces. The one deliberate divergence
(indentation) has its own section and its own reasoning.
"""

from __future__ import annotations

import pytest

from zenzic.core.ast import BlockTracker


def content_lines(text: str) -> list[str]:
    """Every line the tracker says is real content."""
    t = BlockTracker()
    return [ln for ln in text.split("\n") if not t.feed(ln)]


# ── "at least three consecutive backtick characters or tildes" ────────────────


@pytest.mark.parametrize("delim", ["```", "~~~", "````", "~~~~~~"])
def test_three_or_more_opens_a_fence(delim: str) -> None:
    assert content_lines(f"a\n{delim}\nHIDDEN\n{delim}\nb") == ["a", "b"]


@pytest.mark.parametrize("delim", ["``", "~~", "`", "~"])
def test_fewer_than_three_is_not_a_fence(delim: str) -> None:
    assert "HIDDEN" in content_lines(f"a\n{delim}\nHIDDEN\n{delim}\nb")


# ── "with at least as many backticks or tildes as the opening code fence" ─────


def test_a_shorter_closer_does_not_close() -> None:
    """The nested-fence defect, stated as the clause it violates."""
    assert content_lines("````\nHIDDEN\n```\nSTILL HIDDEN\n````\nafter") == ["after"]


def test_a_longer_closer_does_close() -> None:
    assert content_lines("```\nHIDDEN\n`````\nafter") == ["after"]


def test_an_equal_closer_closes() -> None:
    assert content_lines("````\nHIDDEN\n````\nafter") == ["after"]


# ── "Tildes and backticks cannot be mixed" ────────────────────────────────────


def test_a_tilde_does_not_close_a_backtick_fence() -> None:
    assert content_lines("```\nHIDDEN\n~~~\nSTILL HIDDEN\n```\nafter") == ["after"]


def test_a_backtick_does_not_close_a_tilde_fence() -> None:
    assert content_lines("~~~\nHIDDEN\n```\nSTILL HIDDEN\n~~~\nafter") == ["after"]


# ── "Closing code fences cannot have info strings" ────────────────────────────


def test_a_closer_with_an_info_string_does_not_close() -> None:
    assert content_lines("```\nHIDDEN\n``` yaml\nSTILL HIDDEN\n```\nafter") == ["after"]


def test_a_closer_followed_only_by_spaces_still_closes() -> None:
    """ "may be followed only by spaces or tabs, which are ignored"."""
    assert content_lines("```\nHIDDEN\n```   \nafter") == ["after"]


# ── "it may not contain any backtick characters" (backtick openers only) ──────


def test_a_backtick_opener_with_a_backtick_in_its_info_is_not_a_fence() -> None:
    assert "HIDDEN" in content_lines("a\n``` see `x`\nHIDDEN\nb")


def test_a_tilde_opener_may_carry_backticks_in_its_info() -> None:
    """The clause is scoped to backtick fences; tildes are unrestricted."""
    assert content_lines("a\n~~~ see `x`\nHIDDEN\n~~~\nb") == ["a", "b"]


# ── "If the end of the containing block (or document) is reached ..." ─────────


def test_an_unclosed_fence_runs_to_end_of_document() -> None:
    assert content_lines("before\n```\nHIDDEN\nALSO HIDDEN") == ["before"]


def test_the_tracker_reports_being_inside_after_an_unclosed_fence() -> None:
    t = BlockTracker()
    for ln in "a\n```\nb".split("\n"):
        t.feed(ln)
    assert t.inside is True


# ── The deliberate divergence: indentation stays permissive ───────────────────
#
# CommonMark allows an opener "preceded by up to three spaces", measured from
# the *containing block*, not column zero. A fence inside an admonition or list
# continuation starts four or more columns from the margin and is conformant.
# This tracker is line-based and has no container context, so the column-zero
# rule would measure from a reference the specification does not use.
# Measured 2026-09-14: 942/1308 fences in zensical/docs and 196 in ours sit at
# 4+ columns.


@pytest.mark.parametrize("indent", ["", " ", "   ", "    ", "        "])
def test_indentation_is_permissive_by_decision(indent: str) -> None:
    text = f"a\n{indent}```yaml\n{indent}HIDDEN\n{indent}```\nb"
    assert content_lines(text) == ["a", "b"], f"indent={len(indent)}"


def test_an_indented_closer_closes_an_unindented_opener() -> None:
    """The closer's indentation is independent of the opener's."""
    assert content_lines("```\nHIDDEN\n   ```\nafter") == ["after"]


# ── The shape the whole rewrite exists to fix ─────────────────────────────────


def test_the_nested_documenting_fence() -> None:
    """A corpus that teaches Markdown by showing it -- the real-world case."""
    text = (
        "intro\n"
        '```` markdown title="Code block with annotation"\n'
        "``` yaml\n"
        "# Code block content\n"
        "```\n"
        "\n"
        "1.  Look ma, less line noise!\n"
        "````\n"
        "after"
    )
    assert content_lines(text) == ["intro", "after"]
