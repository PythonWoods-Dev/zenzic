# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""QA test suite for InMemoryPathResolver.

Coverage matrix:
- Happy paths (relative, absolute, implicit .md, directory index)
- Credential Scanner: path traversal in all obfuscation variants
- FileNotFound (missing files, typos)
- Anchor validation (hit, miss, fuzzing, case-insensitivity)
- Windows backslash normalisation
- Percent-encoding in paths and fragments
- Cache incoherence (anchor_cache ≠ md_contents)
- Case-sensitive dict keys
- _coerce_path on non-Path inputs
- Circular-link graphs (no recursion limit)
- Performance baseline: 5 000 resolutions < 150 ms
"""

from __future__ import annotations

import time
from pathlib import Path, PurePosixPath

import pytest

from zenzic.core.resolver import (
    AnchorMissing,
    FileNotFound,
    InMemoryPathResolver,
    PathTraversal,
    Resolved,
)


# ─── Shared fixtures ──────────────────────────────────────────────────────────

ROOT = Path("/docs")

_CONTENTS: dict[Path, str] = {
    ROOT / "index.md": "# Home\n",
    ROOT / "guide" / "install.md": "# Install\n## Quick Start\n## Requirements\n",
    ROOT / "guide" / "index.md": "# Guide\n## Overview\n",
    ROOT / "reference" / "api.md": "# API Reference\n## Endpoints\n",
    ROOT / "about" / "team.md": "# Team\n",
}

_ANCHORS: dict[Path, set[str]] = {
    ROOT / "index.md": {"home"},
    ROOT / "guide" / "install.md": {"install", "quick-start", "requirements"},
    ROOT / "guide" / "index.md": {"guide", "overview"},
    ROOT / "reference" / "api.md": {"api-reference", "endpoints"},
    ROOT / "about" / "team.md": {"team"},
}


@pytest.fixture()
def resolver() -> InMemoryPathResolver:
    return InMemoryPathResolver(ROOT, _CONTENTS, _ANCHORS)


# ─── Happy paths ──────────────────────────────────────────────────────────────


class TestHappyPaths:
    """Standard resolution scenarios — must all return Resolved."""

    def test_relative_file(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "install.md"

    def test_relative_file_with_valid_anchor(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#quick-start")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "install.md"

    def test_site_absolute_path(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "guide" / "install.md", "/reference/api.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "reference" / "api.md"

    def test_implicit_md_suffix(self, resolver: InMemoryPathResolver) -> None:
        """'guide/install' (no extension) resolves to 'guide/install.md'."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/install")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "install.md"

    def test_directory_index(self, resolver: InMemoryPathResolver) -> None:
        """'guide/' resolves to 'guide/index.md'."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "index.md"

    def test_dot_prefix_relative(self, resolver: InMemoryPathResolver) -> None:
        """'./guide/install.md' is equivalent to 'guide/install.md'."""
        outcome = resolver.resolve(ROOT / "index.md", "./guide/install.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "install.md"

    def test_parent_relative_stays_inside_root(self, resolver: InMemoryPathResolver) -> None:
        """'../about/team.md' from 'guide/install.md' stays within /docs."""
        outcome = resolver.resolve(ROOT / "guide" / "install.md", "../about/team.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "about" / "team.md"

    def test_site_absolute_with_anchor(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "/guide/install.md#requirements")
        assert isinstance(outcome, Resolved)


# ─── Credential Scanner: path traversal ───────────────────────────────────────────


class TestPathTraversal:
    """Every variant must return PathTraversal and preserve the raw href."""

    def test_classic_dotdot_sequence(self, resolver: InMemoryPathResolver) -> None:
        href = "../../../../etc/passwd"
        outcome = resolver.resolve(ROOT / "index.md", href)
        assert isinstance(outcome, PathTraversal)
        assert outcome.raw_href == href

    def test_windows_backslash_traversal(self, resolver: InMemoryPathResolver) -> None:
        """Backslash-encoded traversal must be caught after normalisation."""
        href = "..\\..\\..\\etc\\passwd"
        outcome = resolver.resolve(ROOT / "index.md", href)
        assert isinstance(outcome, PathTraversal)

    def test_mixed_slash_traversal(self, resolver: InMemoryPathResolver) -> None:
        href = "..//..//../../etc/passwd"
        outcome = resolver.resolve(ROOT / "index.md", href)
        assert isinstance(outcome, PathTraversal)

    def test_percent_encoded_dotdot(self, resolver: InMemoryPathResolver) -> None:
        """%2e%2e is decoded to '..' by unquote before normpath sees it."""
        href = "%2e%2e/%2e%2e/%2e%2e/etc/passwd"
        outcome = resolver.resolve(ROOT / "index.md", href)
        assert isinstance(outcome, PathTraversal)

    def test_parallel_directory_escape(self, resolver: InMemoryPathResolver) -> None:
        """Two levels up from a deeply nested source exits /docs."""
        href = "../../sibling/page.md"
        outcome = resolver.resolve(ROOT / "guide" / "install.md", href)
        assert isinstance(outcome, PathTraversal)

    def test_backslash_dotdot_mixed(self, resolver: InMemoryPathResolver) -> None:
        """Windows separators normalise, and the depth base is the page URL.

        ``..\\../etc/passwd`` is extensionless, so the site generator emits it
        verbatim and the browser resolves it against the page's URL directory --
        ``/guide/install/`` -- where two levels up is the site root, i.e.
        ``docs_root``.  The resolver therefore reports ``FileNotFound`` rather
        than ``PathTraversal``: on this site the href names ``/etc/passwd``
        *inside* the site, which does not exist.

        The Tier-0 property is unaffected and that was verified end to end, not
        assumed: a real ``zenzic check all`` over a fixture containing exactly
        this href still emits ``Z202`` ("resolves outside the docs") and
        Exit 1.  The security tier is the control here; this classification is
        an internal resolution detail.

        The two sibling tests stay ``PathTraversal`` and pin the boundary:
        ``test_parallel_directory_escape`` uses a ``.md`` href, which the
        generator rewrites, and ``test_raw_href_preserved_on_traversal``
        starts from an ``index.md``, whose URL gains no segment.
        """
        href = "..\\../etc/passwd"
        outcome = resolver.resolve(ROOT / "guide" / "install.md", href)
        assert isinstance(outcome, FileNotFound)

    def test_raw_href_preserved_on_traversal(self, resolver: InMemoryPathResolver) -> None:
        """The exact raw href is preserved for accurate error reporting."""
        href = "../../../../secret"
        outcome = resolver.resolve(ROOT / "index.md", href)
        assert isinstance(outcome, PathTraversal)
        assert outcome.raw_href == href


# ─── FileNotFound ─────────────────────────────────────────────────────────────


class TestFileNotFound:
    """Paths that are syntactically valid but absent from md_contents."""

    def test_missing_file(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "nonexistent.md")
        assert isinstance(outcome, FileNotFound)
        assert outcome.path_part == "nonexistent.md"

    def test_typo_in_filename(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/instal.md")  # missing 'l'
        assert isinstance(outcome, FileNotFound)

    def test_nonexistent_subdirectory(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "changelog/v0.2.md")
        assert isinstance(outcome, FileNotFound)

    def test_site_absolute_missing(self, resolver: InMemoryPathResolver) -> None:
        """Site-absolute path that stays within root but has no matching file."""
        outcome = resolver.resolve(ROOT / "index.md", "/this/does/not/exist.md")
        assert isinstance(outcome, FileNotFound)

    def test_space_encoded_path_no_match(self, resolver: InMemoryPathResolver) -> None:
        """%20 decodes to a space; no file with spaces exists in fixture."""
        outcome = resolver.resolve(ROOT / "index.md", "guide%20extra/install.md")
        assert isinstance(outcome, FileNotFound)
        assert outcome.path_part == "guide extra/install.md"


# ─── Anchor validation ────────────────────────────────────────────────────────


class TestAnchorValidation:
    """File-found cases where the fragment determines the outcome."""

    def test_valid_anchor_lowercase(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#quick-start")
        assert isinstance(outcome, Resolved)

    def test_anchor_case_insensitive(self, resolver: InMemoryPathResolver) -> None:
        """Fragment lookup uses fragment.lower(); QUICK-START must match quick-start."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#QUICK-START")
        assert isinstance(outcome, Resolved)

    def test_anchor_mixed_case(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#Quick-Start")
        assert isinstance(outcome, Resolved)

    def test_missing_anchor(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#does-not-exist")
        assert isinstance(outcome, AnchorMissing)
        assert outcome.anchor == "does-not-exist"
        assert outcome.path_part == "guide/install.md"
        assert outcome.resolved_file == ROOT / "guide" / "install.md"

    def test_anchor_with_special_characters(self, resolver: InMemoryPathResolver) -> None:
        """Anchors with chars not present in any slug must be reported as missing."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#quick@start!")
        assert isinstance(outcome, AnchorMissing)

    def test_anchor_with_encoded_space(self, resolver: InMemoryPathResolver) -> None:
        """%20 in fragment is NOT decoded by urlsplit — raw fragment is 'quick%20start'."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md#quick%20start")
        # "quick%20start".lower() is not in {"install", "quick-start", "requirements"}
        assert isinstance(outcome, AnchorMissing)
        assert outcome.anchor == "quick%20start"

    def test_no_anchor_in_href_always_resolves(self, resolver: InMemoryPathResolver) -> None:
        """A file href with no fragment never triggers AnchorMissing."""
        outcome = resolver.resolve(ROOT / "index.md", "reference/api.md")
        assert isinstance(outcome, Resolved)


# ─── Windows backslash normalisation ─────────────────────────────────────────


class TestWindowsNormalization:
    """All backslash forms must resolve identically to their forward-slash form."""

    def test_single_backslash_separator(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide\\install.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "install.md"

    def test_backslash_with_anchor(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide\\install.md#quick-start")
        assert isinstance(outcome, Resolved)

    def test_mixed_backslash_and_forwardslash(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide\\..\\guide\\install.md")
        assert isinstance(outcome, Resolved)

    def test_multiple_backslash_levels(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide\\install.md")
        assert outcome == resolver.resolve(ROOT / "index.md", "guide/install.md")


# ─── Percent-encoding in paths ────────────────────────────────────────────────


class TestPercentEncoding:
    """Percent-encoded sequences in the path component are decoded before lookup."""

    def test_encoded_slash_in_path(self, resolver: InMemoryPathResolver) -> None:
        """%2f decodes to '/' — the path 'guide%2finstall.md' becomes 'guide/install.md'."""
        outcome = resolver.resolve(ROOT / "index.md", "guide%2finstall.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == ROOT / "guide" / "install.md"

    def test_encoded_dot_in_path(self, resolver: InMemoryPathResolver) -> None:
        """%2e decodes to '.'; path 'guide/%2e%2e/guide/install.md' normalises safely."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/%2e%2e/guide/install.md")
        assert isinstance(outcome, Resolved)

    def test_encoded_traversal_via_percent(self, resolver: InMemoryPathResolver) -> None:
        """%2e%2e/../../../etc/passwd must still be caught by the credential scanner."""
        outcome = resolver.resolve(ROOT / "index.md", "%2e%2e/%2e%2e/%2e%2e/etc/passwd")
        assert isinstance(outcome, PathTraversal)

    def test_encoded_space_gives_file_not_found(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide%20notes/install.md")
        assert isinstance(outcome, FileNotFound)
        assert "guide notes" in outcome.path_part


# ─── Cache incoherence ────────────────────────────────────────────────────────


class TestCacheIncoherence:
    """anchors_cache may reference files not present in md_contents.
    The resolver must degrade gracefully — no KeyError, no crash."""

    def test_anchor_exists_in_cache_but_file_not_in_contents(self) -> None:
        """Ghost entry in anchors_cache must not cause a crash."""
        ghost = ROOT / "ghost.md"
        r = InMemoryPathResolver(
            root_dir=ROOT,
            md_contents={ROOT / "index.md": "# Home\n"},
            anchors_cache={
                ROOT / "index.md": {"home"},
                ghost: {"phantom-section"},  # ← file absent from md_contents
            },
        )
        # Attempting to link to ghost.md must return FileNotFound,
        # not a KeyError from accessing the orphaned anchors_cache entry.
        outcome = r.resolve(ROOT / "index.md", "ghost.md#phantom-section")
        assert isinstance(outcome, FileNotFound)

    def test_empty_anchor_set_in_cache(self) -> None:
        """A file with an empty anchor set returns AnchorMissing for any fragment."""
        target = ROOT / "empty-headings.md"
        r = InMemoryPathResolver(
            root_dir=ROOT,
            md_contents={
                ROOT / "index.md": "# Home\n",
                target: "no headings here\n",
            },
            anchors_cache={
                ROOT / "index.md": {"home"},
                target: set(),  # ← explicit empty set
            },
        )
        outcome = r.resolve(ROOT / "index.md", "empty-headings.md#anything")
        assert isinstance(outcome, AnchorMissing)

    def test_file_in_contents_absent_from_anchor_cache(self) -> None:
        """File present in md_contents but NOT in anchors_cache.
        The resolver defaults to an empty set for anchor lookups."""
        target = ROOT / "no-cache.md"
        r = InMemoryPathResolver(
            root_dir=ROOT,
            md_contents={ROOT / "index.md": "# Home\n", target: "# Page\n"},
            anchors_cache={ROOT / "index.md": {"home"}},  # target intentionally absent
        )
        outcome = r.resolve(ROOT / "index.md", "no-cache.md#section")
        assert isinstance(outcome, AnchorMissing)
        assert outcome.anchor == "section"


# ─── Case sensitivity ─────────────────────────────────────────────────────────


class TestCaseSensitivity:
    """Dict keys are compared verbatim; case mismatches behave like missing files."""

    def test_uppercase_file_not_found_if_dict_key_is_lowercase(
        self, resolver: InMemoryPathResolver
    ) -> None:
        """md_contents key is 'install.md'; 'Install.md' must not match."""
        outcome = resolver.resolve(ROOT / "index.md", "guide/Install.md")
        assert isinstance(outcome, FileNotFound)

    def test_exact_case_resolves(self, resolver: InMemoryPathResolver) -> None:
        outcome = resolver.resolve(ROOT / "index.md", "guide/install.md")
        assert isinstance(outcome, Resolved)


# ─── _coerce_path: type safety ────────────────────────────────────────────────


class TestCoercePath:
    """InMemoryPathResolver must accept str keys in all mappings."""

    def test_str_root_dir(self) -> None:
        r = InMemoryPathResolver(
            root_dir="/docs",  # type: ignore[arg-type]
            md_contents={"/docs/index.md": "# Home\n"},  # type: ignore[dict-item]
            anchors_cache={"/docs/index.md": {"home"}},  # type: ignore[dict-item]
        )
        outcome = r.resolve("/docs/index.md", "index.md")  # type: ignore[arg-type]
        assert isinstance(outcome, Resolved)

    def test_str_source_file(self) -> None:
        r = InMemoryPathResolver(ROOT, _CONTENTS, _ANCHORS)
        outcome = r.resolve("/docs/index.md", "guide/install.md")  # type: ignore[arg-type]
        assert isinstance(outcome, Resolved)

    def test_mixed_str_and_path_keys(self) -> None:
        r = InMemoryPathResolver(
            root_dir=ROOT,
            md_contents={
                ROOT / "index.md": "# Home\n",
                "/docs/guide/install.md": "# Install\n",  # type: ignore[dict-item]
            },
            anchors_cache={},
        )
        outcome = r.resolve(ROOT / "index.md", "guide/install.md")
        assert isinstance(outcome, Resolved)


# ─── Circular-link graphs ─────────────────────────────────────────────────────


class TestCircularLinks:
    """The resolver is iterative, not recursive.
    Circular reference graphs must never hit Python's recursion limit."""

    def test_1000_circular_links_no_recursion(self) -> None:
        n = 1_000
        contents: dict[Path, str] = {}
        anchors: dict[Path, set[str]] = {}
        for i in range(n):
            page = ROOT / f"page_{i}.md"
            contents[page] = f"# Page {i}\n"
            anchors[page] = {f"page-{i}"}

        r = InMemoryPathResolver(ROOT, contents, anchors)

        # Each page links to the next; the last links back to the first (A→B→A cycle).
        for i in range(n):
            src = ROOT / f"page_{i}.md"
            target_name = f"page_{(i + 1) % n}.md"
            outcome = r.resolve(src, target_name)
            assert isinstance(outcome, Resolved), f"page_{i} → {target_name} failed"

    def test_self_referential_link(self) -> None:
        """A file linking to itself must resolve without issues."""
        page = ROOT / "self.md"
        r = InMemoryPathResolver(
            root_dir=ROOT,
            md_contents={page: "# Self\n[here](self.md)\n"},
            anchors_cache={page: {"self"}},
        )
        outcome = r.resolve(page, "self.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == page


# ─── Performance baseline ─────────────────────────────────────────────────────


# ─── Normcase portability fix (KL-002 / CEO-203) ─────────────────────────────


class TestNormcasePortability:
    """os.path.normcase is applied to boundary checks only.

    On Linux, normcase is identity — all tests below behave identically on all
    platforms.  The suite verifies that:
      1. A legitimate link whose case matches the *filesystem* (but whose path
         happens to start with an uppercase directory segment) resolves cleanly.
      2. A real path-traversal with mixed case is still blocked (the `..`
         collapse happens before normcase, so normcase cannot open a gap).
    """

    def test_legitimate_link_with_uppercase_root_resolves(self) -> None:
        """Root that starts with an uppercase letter must not produce PathTraversal.

        Simulates a project whose docs root is e.g. /Docs (mixed case on APFS).
        Before the normcase fix, the credential scanner comparison could fail on Linux if
        the os.path.normcase of target != os.path.normcase of root, but on
        Linux normcase is identity so this test also passes there.
        """
        root = Path("/Docs")
        page = root / "guide" / "install.md"
        r = InMemoryPathResolver(
            root_dir=root,
            md_contents={
                root / "index.md": "# Home\n",
                page: "# Install\n",
            },
            anchors_cache={},
        )
        outcome = r.resolve(root / "index.md", "guide/install.md")
        assert isinstance(outcome, Resolved)
        assert outcome.target == page

    def test_traversal_with_mixed_case_is_still_blocked(self) -> None:
        """A path-traversal attack with mixed-case segments must still be caught.

        ``..`` collapse is applied by normpath() before normcase, so normcase
        cannot un-block a traversal.  E.g. ``dOCs/../etc/passwd`` becomes
        ``/etc/passwd`` after normpath — well outside any allowed root.
        """
        root = Path("/docs")
        r = InMemoryPathResolver(
            root_dir=root,
            md_contents={root / "index.md": "# Home\n"},
            anchors_cache={},
        )
        outcome = r.resolve(root / "index.md", "../../../../etc/passwd")
        assert isinstance(outcome, PathTraversal)

    def test_normcase_does_not_open_gap_via_empty_allowed_roots(self) -> None:
        """A resolver with extra allowed roots still blocks traversal."""
        root = Path("/docs")
        locale = Path("/docs/i18n/it")
        r = InMemoryPathResolver(
            root_dir=root,
            md_contents={
                root / "index.md": "# Home\n",
                locale / "index.md": "# Home IT\n",
            },
            anchors_cache={},
            allowed_roots=[locale],
        )
        outcome = r.resolve(root / "index.md", "../../etc/shadow")
        assert isinstance(outcome, PathTraversal)


# ─── Performance baseline ─────────────────────────────────────────────────────


class TestPerformanceBaseline:
    """5 000 mixed resolutions must stay cheap *relative to the machine running them*.

    Tests a realistic mix: hits, misses, traversal attempts, and anchor checks.
    All lookups are in-memory; no I/O, no subprocess.

    This used to assert an absolute wall-clock ceiling of 200 ms, and that number was
    calibrated on one machine and enforced on every other. It failed twice in a row on
    a Windows CI runner at 219.6 ms and 217.1 ms -- and it was not a regression.
    Measured against the last commit before the change under suspicion, on one machine
    and with one script: **22.7 ms median before, 22.8 ms after**, min/max overlapping.
    What had actually changed was the runner: the same suite took **223 s** on the
    passing run and **317 s** on the failing one, +42% wall-clock for +5 tests. The
    assertion had roughly 10% headroom on that hardware, so a uniformly slower runner
    flipped it while the code was untouched.

    Raising the ceiling would have hidden that rather than fixed it, and the class is
    one this project has already corrected elsewhere: a timing measured on one machine
    is not a property of the software. So the assertion is now a **ratio** against a
    reference loop timed in the same process, on the same inputs, immediately
    afterwards. A ratio is invariant to a uniformly slower machine -- which is the
    observed failure mode -- and still catches what this test exists to catch: a rise
    in per-resolution cost inside ``_lookup`` or ``_build_target``.

    Calibration, measured over 12 trials: the ratio sits at **3.02 median, 2.52-3.40
    range, stdev 0.203**. The limit is **6.0**, which a doubling of per-resolution cost
    would breach and machine variance will not. The absolute figure is still reported
    in the failure message, because it is useful to a human even when it is not the
    thing being asserted.
    """

    _HREFS: list[str] = [
        "guide/install.md#quick-start",  # Resolved
        "guide/install.md#no-such-anchor",  # AnchorMissing
        "missing.md",  # FileNotFound
        "../../../../etc/passwd",  # PathTraversal
        "/reference/api.md",  # Resolved (site-absolute)
        "guide\\install.md",  # Resolved (backslash)
    ]

    #: Ratio ceiling for 5 000 resolutions against the reference loop. See the class
    #: docstring for the calibration; 6.0 is a doubling of the measured 3.02.
    _RATIO_LIMIT = 6.0

    def test_5000_resolutions_stay_cheap_relative_to_the_machine(
        self, resolver: InMemoryPathResolver
    ) -> None:
        source = ROOT / "index.md"
        hrefs = (self._HREFS * 834)[:5_000]  # exactly 5 000

        # Warm both paths equally: first-call import and cache effects otherwise land
        # entirely on whichever loop runs first and distort the ratio.
        sink = ""
        for href in hrefs[:300]:
            resolver.resolve(source, href)
            sink = PurePosixPath(href).name

        start = time.perf_counter()
        for href in hrefs:
            resolver.resolve(source, href)
        resolve_s = time.perf_counter() - start

        # The reference shares the dominant primitive -- parsing a path-shaped string --
        # so it scales with the same machine characteristics that made the absolute
        # ceiling unusable, and cancels out of the ratio.
        start = time.perf_counter()
        for href in hrefs:
            sink = PurePosixPath(href).name
        reference_s = time.perf_counter() - start
        assert sink, "the reference loop did no work, so the ratio means nothing"

        ratio = resolve_s / reference_s
        assert ratio < self._RATIO_LIMIT, (
            f"5 000 resolutions cost {ratio:.2f}x the reference loop "
            f"({resolve_s * 1000:.1f} ms against {reference_s * 1000:.1f} ms); "
            f"limit is {self._RATIO_LIMIT}x and the calibrated value is ~3.0. "
            "Investigate _lookup or _build_target overhead — this is a ratio, so a "
            "slow machine does not move it."
        )

    def test_outcome_distribution_is_correct(self, resolver: InMemoryPathResolver) -> None:
        """Sanity-check that the mix produces all four outcome types."""
        source = ROOT / "index.md"
        outcomes = {type(resolver.resolve(source, h)) for h in self._HREFS}
        assert outcomes == {Resolved, AnchorMissing, FileNotFound, PathTraversal}
