# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The sentence-closer set is written once, and the regex that mirrors it agrees.

`core/content.py` declares `_SENTENCE_CLOSERS` and, immediately below it,
`_SENTENCE_END_RE` — whose character class repeats the same characters by hand.
The comment between them says they are "kept beside the character set it mirrors
so the two cannot drift apart".

Proximity is not a binding. The regex is not built from the constant, nothing
imported one into the other, and no test compared them: measured on 2026-09-21,
the two sets were identical and the guarantee was a hope. Adding a closing
character to the constant — a new quotation mark, a bracket some locale uses —
would leave the regex behind, and the line-level pre-filter would stop seeing
sentences the character-level rule accepts.

This is the shape the structural tests in this directory exist for: a set
declared in one place and restated in another, agreeing today, with nothing
holding them together. The claim is prose; the set is checkable.
"""

from __future__ import annotations

from zenzic.core.content import _SENTENCE_CLOSERS, _SENTENCE_END_RE


def _closers_in_pattern(pattern: str) -> str:
    """Return the character class that follows the sentence-terminator class.

    Parsed rather than matched with a regex of its own: the class contains an
    escaped ``]``, which a naive `[^\\]]*` truncates at — that mistake was made
    while writing this test and reported a false divergence.
    """
    marker = "[.!?;]"
    start = pattern.index(marker) + len(marker)
    assert pattern[start] == "[", "the pattern no longer opens a class where this test expects one"
    out: list[str] = []
    i = start + 1
    while i < len(pattern):
        if pattern[i] == "\\":
            out.append(pattern[i + 1])
            i += 2
            continue
        if pattern[i] == "]":
            break
        out.append(pattern[i])
        i += 1
    return "".join(out)


def test_the_regex_mirrors_the_declared_closers() -> None:
    """Both directions: no closer missing from the regex, none invented in it."""
    in_regex = _closers_in_pattern(_SENTENCE_END_RE.pattern)
    missing = sorted(set(_SENTENCE_CLOSERS) - set(in_regex))
    extra = sorted(set(in_regex) - set(_SENTENCE_CLOSERS))
    assert not missing, (
        f"_SENTENCE_END_RE does not accept {missing!r}, which _SENTENCE_CLOSERS declares. "
        "The line-level pre-filter would stop seeing sentences the character-level rule ends."
    )
    assert not extra, (
        f"_SENTENCE_END_RE accepts {extra!r}, which _SENTENCE_CLOSERS does not declare."
    )


def test_the_parser_finds_a_non_empty_class() -> None:
    """Positive control: an extractor returning nothing would pass the test above."""
    in_regex = _closers_in_pattern(_SENTENCE_END_RE.pattern)
    assert len(in_regex) >= 5, (
        f"extracted only {in_regex!r} — the extractor, not the code, is wrong"
    )
    assert "]" in in_regex, "the escaped ']' must survive extraction; truncating there hides drift"
