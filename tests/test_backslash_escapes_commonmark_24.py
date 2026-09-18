# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Backslash escapes, derived from CommonMark §2.4 rather than from the case found.

The measured defect was one line: `\\[text](./nowhere.md)` is not a link — the
backslash escapes the bracket — and the engine built one and reported it broken.
Fixing that line alone would have left every other escapable character wrong, so
the suite below is generated from the specification's own rule.

**§2.4, in full**: any ASCII punctuation character may be backslash-escaped. A
backslash before any other character — a letter, a digit, a newline, a non-ASCII
punctuation mark — is a literal backslash and escapes nothing.

The case that makes this a scan rather than a substitution is the double
backslash: `\\\\[text](url)` is a literal backslash followed by a **real** link,
so a fix that matches `\\[` anywhere deletes a link that exists.
"""

from __future__ import annotations

import string

import pytest

from zenzic.core.validator import mask_backslash_escapes


#: §2.4's own list. Written out rather than taken from `string.punctuation` so
#: that a future change to either is visible as a difference, not absorbed.
_ASCII_PUNCTUATION = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"


def test_the_escapable_set_is_ascii_punctuation() -> None:
    """The specification says ASCII punctuation; this pins that it is exactly that."""
    assert set(_ASCII_PUNCTUATION) == set(string.punctuation)
    assert len(_ASCII_PUNCTUATION) == 32


@pytest.mark.parametrize("char", list(_ASCII_PUNCTUATION))
def test_every_ascii_punctuation_character_is_escapable(char: str) -> None:
    """A backslash before any of the 32 is consumed with it."""
    assert mask_backslash_escapes(f"a\\{char}b") == "a  b"


@pytest.mark.parametrize("char", ["a", "Z", "0", " ", "\n", "è", "—", "→"])
def test_a_backslash_before_anything_else_is_literal(char: str) -> None:
    """§2.4 escapes ASCII punctuation and nothing else — the backslash survives."""
    assert mask_backslash_escapes(f"a\\{char}b") == f"a\\{char}b"


def test_offsets_and_newlines_are_preserved() -> None:
    """Callers report columns, so every mask in this module keeps length."""
    text = "line one \\[x\nline two \\*y\n"
    masked = mask_backslash_escapes(text)
    assert len(masked) == len(text)
    assert masked.count("\n") == text.count("\n")
    assert [len(x) for x in masked.split("\n")] == [len(x) for x in text.split("\n")]


# ── The double backslash, in both directions ─────────────────────────────────


def test_an_escaped_bracket_opens_no_link() -> None:
    assert "[" not in mask_backslash_escapes(r"\[text](./nowhere.md)")


def test_an_escaped_backslash_leaves_the_link_that_follows() -> None:
    """`\\\\[text](url)` is a literal backslash and then a real link."""
    assert mask_backslash_escapes(r"\\[text](./real.md)") == r"  [text](./real.md)"


def test_three_backslashes_escape_the_bracket_again() -> None:
    """Pairs are consumed left to right, so parity decides."""
    assert "[" not in mask_backslash_escapes(r"\\\[text](./nowhere.md)")


def test_four_backslashes_leave_the_link() -> None:
    assert mask_backslash_escapes(r"\\\\[text](./real.md)") == r"    [text](./real.md)"


# ── The extractor, end to end ────────────────────────────────────────────────

_DOC = "\n".join(
    [
        "# Escapes",
        "",
        r"Not a link: \[text](./escaped-away.md)",
        "",
        r"Literal backslash then a real link: \\[text](./still-a-link.md)",
        "",
        "Ordinary: [text](./ordinary.md)",
        "",
    ]
)


def test_the_extractor_honours_escapes_in_both_directions() -> None:
    """The proof the batch asks for: one disappears, the other two do not."""
    from zenzic.core.rules import _extract_inline_links_with_lines

    urls = [u for u, _n, _raw in _extract_inline_links_with_lines(_DOC, containers=None)]
    assert "./escaped-away.md" not in urls
    assert "./still-a-link.md" in urls
    assert "./ordinary.md" in urls


def test_the_single_source_of_truth_extractor_agrees() -> None:
    """`PolyglotExtractor.extract_all_links` describes itself as the one place; check it is."""
    from zenzic.core.validator import PolyglotExtractor

    urls = [link.url for link in PolyglotExtractor().extract_all_links(_DOC)]
    assert "./escaped-away.md" not in urls
    assert "./still-a-link.md" in urls
    assert "./ordinary.md" in urls
