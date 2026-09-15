# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Z511's sentence splitter must treat a terminator closed by markup as a boundary.

``_split_sentences`` only accepted ``[.!?;]`` as a sentence boundary when the very
next character was whitespace or end-of-text. A sentence ending *inside* Markdown
emphasis therefore never terminated::

    *Note: ... grammar parsing.* Another sentence follows here.

The period is immediately followed by the italic-closing ``*``, so the two
sentences merged into one and their word counts summed. Because Z511 fires on
sentences longer than ``max_words``, that merge produced a **false positive** on
prose that was genuinely within the limit — the harmful direction for an
editorial warning.

The same construction occurs with ``**bold.**``, ``` `code.` ```, and ordinary
closing brackets/quotes (``(like this.)``), which additionally were splitting the
closer onto the *following* sentence.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.content import _split_sentences, check_sentence_lengths


class TestMarkdownEmphasisBoundaries:
    def test_italic_closing_asterisk_terminates_a_sentence(self) -> None:
        """The exact construction from the discovery."""
        got = _split_sentences("*Note: this relies on grammar parsing.* Another one here.")
        assert got == ["*Note: this relies on grammar parsing.*", "Another one here."]

    def test_bold_closing_asterisks_terminate_a_sentence(self) -> None:
        got = _split_sentences("**Bold claim.** Follow-up sentence.")
        assert got == ["**Bold claim.**", "Follow-up sentence."]

    def test_closing_backtick_terminates_a_sentence(self) -> None:
        got = _split_sentences("Run `zenzic check all.` Then read the report.")
        assert got == ["Run `zenzic check all.`", "Then read the report."]


class TestClosingPunctuation:
    def test_closing_paren_stays_with_its_own_sentence(self) -> None:
        """The closer belongs to the sentence it closes, not to the next one."""
        got = _split_sentences("(See the note below.) The gate still runs.")
        assert got == ["(See the note below.)", "The gate still runs."]

    def test_closing_quote_stays_with_its_own_sentence(self) -> None:
        got = _split_sentences('He said "it is deterministic." Nobody disagreed.')
        assert got == ['He said "it is deterministic."', "Nobody disagreed."]


class TestNoRegression:
    def test_plain_whitespace_boundary_still_splits(self) -> None:
        got = _split_sentences("First sentence. Second sentence! Third one?")
        assert got == ["First sentence.", "Second sentence!", "Third one?"]

    def test_decimals_are_not_boundaries(self) -> None:
        got = _split_sentences("Pi is 3.14 exactly. Done.")
        assert got == ["Pi is 3.14 exactly.", "Done."]

    def test_ellipsis_behaviour_is_unchanged(self) -> None:
        """Pre-existing behaviour, pinned so this fix cannot alter it.

        An ellipsis already split at its final period (the first two are followed
        by another period, not whitespace). That is arguably wrong, but it is
        orthogonal to the emphasis bug and deliberately left alone.
        """
        got = _split_sentences("It trailed off... then resumed. Fine.")
        assert got == ["It trailed off...", "then resumed.", "Fine."]

    def test_abbreviation_behaviour_is_unchanged(self) -> None:
        """Pre-existing behaviour, deliberately not altered by this fix."""
        assert _split_sentences("Use e.g. this one.") == ["Use e.g.", "this one."]

    def test_terminator_followed_by_a_letter_is_not_a_boundary(self) -> None:
        assert _split_sentences("zenzic.dev is the site.") == ["zenzic.dev is the site."]


class TestZ511EndToEnd:
    def test_emphasis_merge_no_longer_produces_a_false_positive(self, tmp_path: Path) -> None:
        """Two in-limit sentences must not be reported as one over-limit sentence."""
        first = "*Note: " + " ".join(f"w{i}" for i in range(28)) + " parsing.*"
        second = " ".join(f"x{i}" for i in range(28)) + "."
        findings = check_sentence_lengths(tmp_path / "p.md", f"{first} {second}\n", max_words=40)
        assert findings == [], (
            "two sentences of ~29 words each were merged across the italic-closing "
            f"asterisk and reported as one long sentence: {[f.message for f in findings]}"
        )

    def test_a_genuinely_long_sentence_is_still_reported(self, tmp_path: Path) -> None:
        """The fix must not silence real findings."""
        long_one = "*Note: " + " ".join(f"w{i}" for i in range(60)) + " parsing.*"
        findings = check_sentence_lengths(tmp_path / "p.md", long_one + "\n", max_words=40)
        assert [f.rule_id for f in findings] == ["Z511"]


class TestTrailingBufferIsChecked:
    """A second, independent defect found while fixing the splitter.

    ``check_sentence_lengths`` carried a ``# Flush any remaining buffer at EOF``
    comment above a bare ``return findings`` — the flush itself was missing. Its
    line-level pre-filter shared the splitter's blind spot, so a document whose
    last paragraph ended in markup-closed punctuation never satisfied the filter
    *and* never got flushed: Z511 simply did not run on it. That is a false
    negative — an entire trailing paragraph escaping the check unreported.
    """

    def test_final_paragraph_ending_in_emphasis_is_checked(self, tmp_path: Path) -> None:
        text = "*Note: " + " ".join(f"w{i}" for i in range(60)) + " parsing.*\n"
        assert [f.rule_id for f in check_sentence_lengths(tmp_path / "p.md", text)] == ["Z511"]

    def test_final_paragraph_with_no_terminator_at_all_is_checked(self, tmp_path: Path) -> None:
        text = " ".join(f"w{i}" for i in range(60)) + "\n"
        assert [f.rule_id for f in check_sentence_lengths(tmp_path / "p.md", text)] == ["Z511"]

    def test_short_trailing_paragraph_still_reports_nothing(self, tmp_path: Path) -> None:
        """The new flush must not invent findings on ordinary short prose."""
        assert check_sentence_lengths(tmp_path / "p.md", "A short closing note.*\n") == []
