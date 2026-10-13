# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Property-based tests (Hypothesis) for Zenzic core pure functions.

These tests assert *invariants* — properties that must hold for **any** input,
not just handcrafted examples.  They complement the deterministic unit tests in
``test_validator.py``, ``test_rules.py``, and ``test_scanner.py``.

Target modules:
- ``zenzic.core.validator`` — link extraction, anchor slugging
- ``zenzic.core.rules``     — ``CustomRule.check()``
- ``zenzic.core.scanner``   — ``check_placeholder_content()``
- ``zenzic.core.resolver``  — ``InMemoryPathResolver.resolve()``
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings, strategies as st

from zenzic.core.resolver import (
    AnchorMissing,
    FileNotFound,
    InMemoryPathResolver,
    PathTraversal,
    Resolved,
)
from zenzic.core.rules import CustomRule, RuleFinding
from zenzic.core.validator import (
    LinkInfo,
    _build_ref_map,
    anchors_in_file,
    extract_links,
    extract_ref_links,
    slug_heading,
)


# ── Strategies ────────────────────────────────────────────────────────────────

# Markdown-ish text that exercises link extraction edge cases.
_md_text = st.text(
    alphabet=st.sampled_from(list("abcdefghijABCDEF 0123456789\n\t[]()!#`~_*>-./:\\\"'{}|@&=?+%^")),
    min_size=0,
    max_size=500,
)

# Heading text: printable characters without newlines.
_heading_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z"), exclude_characters="\n\r\x00"),
    min_size=0,
    max_size=200,
)

# File paths for rule/scanner inputs.
_md_filename = st.from_regex(r"[a-z][a-z0-9_]{0,20}\.md", fullmatch=True)

# Regex patterns that are guaranteed to compile (simple word patterns).
_safe_pattern = st.from_regex(r"[a-zA-Z]{1,10}", fullmatch=True)


# ── extract_links — Invariants ───────────────────────────────────────────────


class TestExtractLinksProperties:
    """extract_links() must never crash, always return LinkInfo, and respect line numbers."""

    @given(text=_md_text)
    @settings()
    def test_never_crashes(self, text: str) -> None:
        """extract_links must return a list (possibly empty) for any input."""
        result = extract_links(text)
        assert isinstance(result, list)

    @given(text=_md_text)
    @settings()
    def test_returns_linkinfo(self, text: str) -> None:
        """Every element must be a LinkInfo with valid fields."""
        for link in extract_links(text):
            assert isinstance(link, LinkInfo)
            assert isinstance(link.url, str)
            assert isinstance(link.lineno, int)
            assert link.lineno >= 1

    @given(text=_md_text)
    @settings()
    def test_line_numbers_in_range(self, text: str) -> None:
        """Line numbers must not exceed the number of lines in the input."""
        n_lines = text.count("\n") + 1
        for link in extract_links(text):
            assert 1 <= link.lineno <= n_lines

    def test_empty_string(self) -> None:
        """Empty input → no links."""
        assert extract_links("") == []


# ── extract_ref_links — Invariants ───────────────────────────────────────────


class TestExtractRefLinksProperties:
    """extract_ref_links() must be robust against arbitrary text and ref_maps."""

    @given(text=_md_text)
    @settings()
    def test_never_crashes_empty_map(self, text: str) -> None:
        """With an empty ref_map, always returns a list (likely empty)."""
        result = extract_ref_links(text, {})
        assert isinstance(result, list)

    @given(text=_md_text)
    @settings()
    def test_never_crashes_populated_map(self, text: str) -> None:
        """With a populated ref_map, never crashes."""
        ref_map = {"example": "https://example.com", "id": "page.md"}
        result = extract_ref_links(text, ref_map)
        assert isinstance(result, list)
        for link in result:
            assert isinstance(link, LinkInfo)


# ── _build_ref_map — Invariants ──────────────────────────────────────────────


class TestBuildRefMapProperties:
    """_build_ref_map() returns a dict[str, str] for any input."""

    @given(text=_md_text)
    @settings()
    def test_never_crashes(self, text: str) -> None:
        result = _build_ref_map(text)
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, str)


# ── slug_heading — Invariants ────────────────────────────────────────────────


class TestSlugHeadingProperties:
    """slug_heading() must always return a string, never crash on Unicode."""

    @given(heading=_heading_text)
    @settings()
    def test_returns_string(self, heading: str) -> None:
        result = slug_heading(heading)
        assert isinstance(result, str)

    @given(heading=_heading_text)
    @settings()
    def test_no_uppercase(self, heading: str) -> None:
        """Slugs must be lowercase."""
        result = slug_heading(heading)
        assert result == result.lower()

    @given(heading=_heading_text)
    @settings()
    def test_no_leading_trailing_hyphens(self, heading: str) -> None:
        """Slugs should not have leading or trailing hyphens."""
        result = slug_heading(heading)
        if result:
            assert not result.startswith("-")
            assert not result.endswith("-")

    @given(heading=_heading_text)
    @settings()
    def test_no_spaces(self, heading: str) -> None:
        """Slugs must not contain spaces (whitespace is collapsed to hyphens)."""
        result = slug_heading(heading)
        assert " " not in result

    @given(heading=_heading_text)
    @settings()
    def test_idempotent(self, heading: str) -> None:
        """Slugging an already-slugged heading should produce the same result."""
        first = slug_heading(heading)
        second = slug_heading(first)
        assert first == second


# ── anchors_in_file — Invariants ─────────────────────────────────────────────


class TestAnchorsInFileProperties:
    """anchors_in_file() must always return a set of strings."""

    @given(text=_md_text)
    @settings()
    def test_returns_set_of_strings(self, text: str) -> None:
        result = anchors_in_file(text, tabs=None)
        assert isinstance(result, set)
        for anchor in result:
            assert isinstance(anchor, str)

    @given(text=_md_text)
    @settings()
    def test_all_anchors_are_lowercase(self, text: str) -> None:
        """Every anchor slug must be lowercase (consistent with slug_heading)."""
        for anchor in anchors_in_file(text, tabs=None):
            assert anchor == anchor.lower()


# ── CustomRule.check — Invariants ────────────────────────────────────────────


class TestCustomRuleProperties:
    """CustomRule.check() must never crash on arbitrary text."""

    @given(text=_md_text)
    @settings()
    def test_never_crashes(self, text: str) -> None:
        rule = CustomRule(
            id="test-prop",
            pattern=r"\bTODO\b",
            message="Found TODO",
            severity="warning",
        )
        result = rule.check(Path("test.md"), text)
        assert isinstance(result, list)
        for finding in result:
            assert isinstance(finding, RuleFinding)

    @given(text=_md_text, pattern=_safe_pattern)
    @settings()
    def test_with_random_pattern(self, text: str, pattern: str) -> None:
        """A random alphabetic pattern must not crash."""
        rule = CustomRule(
            id="rand-prop",
            pattern=pattern,
            message="match",
            severity="info",
        )
        result = rule.check(Path("test.md"), text)
        assert isinstance(result, list)

    @given(text=_md_text)
    @settings()
    def test_col_start_in_range(self, text: str) -> None:
        """col_start must be within the matched line."""
        rule = CustomRule(
            id="col-prop",
            pattern=r"\bTODO\b",
            message="Found TODO",
            severity="warning",
        )
        for finding in rule.check(Path("test.md"), text):
            assert finding.col_start >= 0
            if finding.matched_line:
                assert finding.col_start < len(finding.matched_line)

    def test_empty_text_no_findings(self) -> None:
        """Empty text → no findings."""
        rule = CustomRule(id="e", pattern=r"TODO", message="m")
        assert rule.check(Path("t.md"), "") == []


# ── InMemoryPathResolver.resolve — Invariants ────────────────────────────────


class TestResolverProperties:
    """InMemoryPathResolver.resolve() must return a valid outcome type for any href."""

    _VALID_OUTCOMES = (PathTraversal, FileNotFound, AnchorMissing, Resolved)

    @staticmethod
    def _make_resolver() -> InMemoryPathResolver:
        root = Path("/docs")
        files = {
            root / "index.md": "# Home\n## Quick Start\n",
            root / "guide.md": "# Guide\n## Install\n## Usage\n",
            root / "sub" / "page.md": "# Sub Page\n",
        }
        anchors = {p: anchors_in_file(c, tabs=None) for p, c in files.items()}
        return InMemoryPathResolver(root, files, anchors)

    # Strategy: href-like strings with path chars.
    _href = st.text(
        alphabet=st.sampled_from(list("abcdefghijklmnop./\\#?&=_-%0123456789")),
        min_size=0,
        max_size=100,
    )

    @given(href=_href)
    @settings()
    def test_always_returns_valid_outcome(self, href: str) -> None:
        """resolve() must always return one of the four outcome types."""
        resolver = self._make_resolver()
        result = resolver.resolve(Path("/docs/index.md"), href)
        assert isinstance(result, self._VALID_OUTCOMES)

    @given(href=st.from_regex(r"\.\./(\.\./){0,5}[a-z]+", fullmatch=True))
    @settings()
    def test_traversal_detection(self, href: str) -> None:
        """Path traversal attempts must be caught (PathTraversal or FileNotFound)."""
        resolver = self._make_resolver()
        result = resolver.resolve(Path("/docs/index.md"), href)
        # Traversal hrefs should either be caught as PathTraversal or resolve
        # to FileNotFound — never to a file outside the root.
        assert isinstance(result, self._VALID_OUTCOMES)
        if isinstance(result, Resolved):
            # If somehow resolved, the target must be under root.
            assert str(result.target).startswith("/docs")

    def test_known_good_link(self) -> None:
        """A known internal link must resolve."""
        resolver = self._make_resolver()
        result = resolver.resolve(Path("/docs/index.md"), "guide.md")
        assert isinstance(result, Resolved)

    def test_known_anchor(self) -> None:
        """A valid anchor must resolve."""
        resolver = self._make_resolver()
        result = resolver.resolve(Path("/docs/index.md"), "guide.md#install")
        assert isinstance(result, Resolved)

    def test_missing_anchor(self) -> None:
        """A missing anchor must return AnchorMissing."""
        resolver = self._make_resolver()
        result = resolver.resolve(Path("/docs/index.md"), "guide.md#nonexistent")
        assert isinstance(result, AnchorMissing)

    def test_missing_file(self) -> None:
        """A missing file must return FileNotFound."""
        resolver = self._make_resolver()
        result = resolver.resolve(Path("/docs/index.md"), "missing.md")
        assert isinstance(result, FileNotFound)
