# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the RE2 Anti-Corruption Layer (`zenzic.core.regex`).

The ACL is a Tier-0 invariant (RE2 Discipline / ADR Regex ACL): every governed
regex in the codebase goes through this module rather than stdlib ``re``, so
that catastrophic-backtracking constructs are rejected rather than silently
accepted. Until now the module had no dedicated tests of its own — it was only
ever exercised incidentally, through callers that happen to use it, which left
its own guard rails (unsupported-flag rejection, RE2 syntax rejection, the
stdlib end-anchor translation) unverified.
"""

from __future__ import annotations

import re as stdlib_re

import pytest

from zenzic.core import regex as re


class TestRE2SyntaxRestrictions:
    """The whole point of the ACL: unsupported constructs must raise, not pass."""

    @pytest.mark.parametrize(
        "pattern",
        [
            r"(?=foo)bar",  # lookahead
            r"(?!foo)bar",  # negative lookahead
            r"(?<=foo)bar",  # lookbehind
            r"(?<!foo)bar",  # negative lookbehind
            r"(\w+)\1",  # backreference
        ],
    )
    def test_backtracking_constructs_are_rejected(self, pattern: str) -> None:
        """RE2 cannot express these; the ACL must surface an error, never fall
        back to stdlib `re`, which would silently reintroduce the catastrophic
        backtracking the invariant exists to prevent.
        """
        with pytest.raises(stdlib_re.error):
            re.compile(pattern)

    def test_error_is_the_stdlib_error_type(self) -> None:
        """`re.error` is re-exported so callers can catch it without importing
        stdlib `re` themselves (which the invariant forbids in Core).
        """
        assert re.error is stdlib_re.error


class TestFlagHandling:
    def test_unsupported_flag_raises(self) -> None:
        """A flag outside the supported set must be rejected explicitly rather
        than silently ignored — silently dropping it would change matching
        semantics without telling anyone.
        """
        bogus_flag = 1 << 20
        with pytest.raises(stdlib_re.error, match="Unsupported regex flags"):
            re.compile(r"abc", bogus_flag)

    def test_ignorecase(self) -> None:
        assert re.search(r"hello", "HELLO", re.IGNORECASE) is not None
        assert re.search(r"hello", "HELLO") is None

    def test_multiline(self) -> None:
        assert re.findall(r"^b", "a\nb", re.MULTILINE) == ["b"]

    def test_dotall(self) -> None:
        assert re.search(r"a.b", "a\nb", re.DOTALL) is not None
        assert re.search(r"a.b", "a\nb") is None

    def test_verbose_is_rejected_with_the_acl_error_not_an_re2_parse_error(self) -> None:
        """RE2 has no ``(?x)`` operator, so VERBOSE cannot be honoured. It was
        previously listed as supported and translated anyway, so every use died
        with ``invalid perl operator: (?x`` from deep inside RE2. It must now
        fail with the ACL's own explicit message instead.
        """
        with pytest.raises(stdlib_re.error, match="Unsupported regex flags"):
            re.compile(r"a b", re.VERBOSE)

    def test_ascii_flag_accepted_for_stdlib_compatibility(self) -> None:
        """ASCII is accepted but has no RE2 equivalent — documented as a
        deliberate no-op, so the contract is that it does not raise.
        """
        assert re.search(r"\w+", "abc", re.ASCII) is not None

    def test_flags_combine(self) -> None:
        assert re.search(r"^b.c", "a\nB\nc", re.IGNORECASE | re.MULTILINE | re.DOTALL) is not None


class TestStdlibEndAnchorTranslation:
    def test_uppercase_Z_anchor_is_translated(self) -> None:
        r"""``fnmatch.translate()`` emits stdlib's ``\Z`` end-anchor, which RE2
        spells ``\z``. The ACL rewrites it; without that, every fnmatch-derived
        exclusion pattern would fail to compile.
        """
        assert re.compile(r"abc\Z").search("abc") is not None


class TestApiSurface:
    """Each re-exported entry point delegates to the RE2 engine."""

    def test_search(self) -> None:
        m = re.search(r"(\d+)", "abc 123")
        assert m is not None and m.group(1) == "123"

    def test_match_anchors_at_start(self) -> None:
        assert re.match(r"abc", "abcdef") is not None
        assert re.match(r"def", "abcdef") is None

    def test_fullmatch(self) -> None:
        assert re.fullmatch(r"abc", "abc") is not None
        assert re.fullmatch(r"abc", "abcdef") is None

    def test_sub(self) -> None:
        assert re.sub(r"\d+", "N", "a1b22c") == "aNbNc"

    def test_findall(self) -> None:
        assert re.findall(r"\d+", "a1b22c") == ["1", "22"]

    def test_finditer(self) -> None:
        assert [m.group(0) for m in re.finditer(r"\d+", "a1b22c")] == ["1", "22"]


class TestCompileCaching:
    def test_identical_pattern_and_flags_return_the_same_object(self) -> None:
        """`compile()` is lru_cached. The cache key is (pattern, flags) only —
        a pure function of its inputs, so it carries no staleness risk.
        """
        assert re.compile(r"x+") is re.compile(r"x+")

    def test_differing_flags_are_cached_separately(self) -> None:
        assert re.compile(r"x+") is not re.compile(r"x+", re.IGNORECASE)
