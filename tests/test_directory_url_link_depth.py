# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Relative links MkDocs does not rewrite resolve against URL depth, not tree depth.

MkDocs rewrites a relative link only when its **literal** path exists in the
source tree: ``../../target/page.md`` becomes a correct URL, and so does an
asset path.  Every other relative spelling -- extensionless, trailing-slash,
``.html`` -- is emitted into the HTML verbatim (measured against a real
``mkdocs build``, not assumed).

With ``use_directory_urls`` (MkDocs' default), a page ``a/b/leaf.md`` is served
at ``/a/b/leaf/``.  That URL carries one segment more than the source directory
``a/b/``, so a verbatim relative link needs one ``..`` more than the source tree
would suggest.  Index pages are exempt: ``a/b/index.md`` serves at ``/a/b/`` and
gains no segment.

Before this was fixed the two verdicts were inverted -- the spelling that 404s
resolved cleanly, and the spelling that works was reported as ``PathTraversal``,
a security finding.  161 broken links across 66 pages of this project's own
documentation passed ``zenzic check links`` as a result.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from zenzic.core.resolver import (
    FileNotFound,
    InMemoryPathResolver,
    PathTraversal,
    Resolved,
)
from zenzic.core.rules import (
    ResolutionContext,
    Violation,
    VSMBrokenLinkRule,
    _extract_inline_links_with_lines,
)
from zenzic.models.vsm import Route


def _resolver(*, use_directory_urls: bool = True) -> InMemoryPathResolver:
    md = {
        Path("/docs/index.md"): "# Home\n",
        Path("/docs/a/b/leaf.md"): "# Leaf\n",
        Path("/docs/a/b/index.md"): "# B Index\n",
        Path("/docs/target/page.md"): "# Target\n",
        Path("/docs/target/index.md"): "# Target Index\n",
    }
    return InMemoryPathResolver(
        root_dir=Path("/docs"),
        md_contents=md,
        anchors_cache={p: set() for p in md},
        use_directory_urls=use_directory_urls,
    )


# ── The .md control: rewritten by MkDocs, must keep working unchanged ─────────


def test_md_link_is_unaffected_because_mkdocs_rewrites_it() -> None:
    """``.md`` links are rewritten to a correct URL, so tree depth is right."""
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), "../../target/page.md")
    assert isinstance(out, Resolved), f"the .md control regressed: {out!r}"
    assert out.target == Path("/docs/target/page.md")


# ── The defect, both directions ───────────────────────────────────────────────


def test_extensionless_link_short_by_one_level_is_reported() -> None:
    """``../../target/page`` from ``/a/b/leaf/`` reaches ``/a/target/page``: 404."""
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), "../../target/page")
    assert isinstance(out, FileNotFound), (
        "a link the browser 404s on must be reported, not resolved via the "
        f"suffix-stripped alias; got {out!r}"
    )


def test_extensionless_link_with_correct_url_depth_still_resolves() -> None:
    """``../../../target/page`` is what the browser needs — it must pass."""
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), "../../../target/page")
    assert isinstance(out, Resolved), (
        "the spelling that works on the live site must not be reported — and "
        f"must never be reported as a security finding; got {out!r}"
    )
    assert out.target == Path("/docs/target/page.md")


def test_directory_link_short_by_one_level_is_reported() -> None:
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), "../../target/")
    assert isinstance(out, FileNotFound), f"got {out!r}"


def test_directory_link_with_correct_url_depth_resolves() -> None:
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), "../../../target/")
    assert isinstance(out, Resolved), f"got {out!r}"
    assert out.target == Path("/docs/target/index.md")


# ── Index pages gain no URL segment, so they are exempt ──────────────────────


def test_index_page_has_no_off_by_one() -> None:
    """``a/b/index.md`` serves at ``/a/b/`` — tree depth already equals URL depth."""
    out = _resolver().resolve(Path("/docs/a/b/index.md"), "../../target/page")
    assert isinstance(out, Resolved), f"index pages must be unaffected; got {out!r}"
    assert out.target == Path("/docs/target/page.md")


# ── The correction is conditional on the setting that causes the divergence ───


def test_flat_urls_have_no_off_by_one() -> None:
    """With ``use_directory_urls=False`` there is no extra segment to account for."""
    out = _resolver(use_directory_urls=False).resolve(
        Path("/docs/a/b/leaf.md"), "../../target/page"
    )
    assert isinstance(out, Resolved), (
        f"a flat-URL site must keep source-tree arithmetic; got {out!r}"
    )


def test_real_traversal_is_still_caught_under_the_correction() -> None:
    """The correction must not open an escape from the docs root."""
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), "../../../../../../etc/passwd")
    assert isinstance(out, PathTraversal), f"got {out!r}"


@pytest.mark.parametrize("href", ["/target/page", "/target/page.md"])
def test_root_relative_links_are_unaffected(href: str) -> None:
    """A leading ``/`` resolves against docs_root — no page-relative depth at all."""
    out = _resolver().resolve(Path("/docs/a/b/leaf.md"), href)
    assert isinstance(out, Resolved), f"{href}: got {out!r}"


# ── Fence tracking: a closing fence carries no info string ───────────────────
# The link extractor tracked fences with a naive toggle: any line matching
# ``^(`{3,}|~{3,})`` flipped the state.  A page embedding a transcript of
# Zenzic's own terminal output contains fence markers inside its fenced block,
# so the toggle desynchronised and the extractor believed it was inside a fence
# for the rest of the file -- silently extracting **no links at all** from that
# point on.  70 of this project's own 161 broken links were invisible for this
# reason, on the example-gallery pages that quote real output.
#
# CommonMark: a closing fence must use the same character, be at least as long
# as the opener, and carry **no info string**.  `suppressions.py` and
# `mutator.py` already implement exactly that; the extractor did not.


_TRANSCRIPT_PAGE = """\
# Example

```text
$ zenzic check all
some output
```text
more output that begins with a fence-looking line
```

Prose between blocks.

```text
another block
```

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
"""


def test_a_closer_with_an_info_string_does_not_close_the_fence() -> None:
    """The link after the transcript must still be extracted."""
    urls = [u for u, _, _ in _extract_inline_links_with_lines(_TRANSCRIPT_PAGE)]
    assert "../../../reference/checks" in urls, (
        f"the extractor stopped seeing links after an embedded fence marker; extracted {urls!r}"
    )


def test_links_inside_a_real_fence_are_still_skipped() -> None:
    """The control: fenced content must stay out of the link graph."""
    page = "# T\n\n```text\n[not a link](./nope)\n```\n\n[real](./yes)\n"
    urls = [u for u, _, _ in _extract_inline_links_with_lines(page)]
    assert urls == ["./yes"], f"fenced links must not be extracted; got {urls!r}"


def test_tilde_fences_and_longer_closers_behave() -> None:
    page = "# T\n\n~~~~text\n[skip](./no)\n~~~~\n\n[keep](./yes)\n"
    urls = [u for u, _, _ in _extract_inline_links_with_lines(page)]
    assert urls == ["./yes"], f"got {urls!r}"


# ── The locale fallback must require an actual locale ─────────────────────────
# VSMBrokenLinkRule retried a missing route by stripping the source file's first
# path segment, treating it as an i18n locale code.  Nothing checked that the
# segment *was* a locale: for `docs/tutorials/...` the "locale" is `tutorials`,
# so `/tutorials/reference/checks/` fell back to `/reference/checks/`, which
# exists -- and the broken link was silently accepted.  This project has **no
# locales configured at all** (`get_locale_source_roots() == []`) and the
# fallback still fired, masking 70 of the 161 broken links.


class _Route:
    """Minimal stand-in for a VSM Route: the rule reads only these two fields."""

    status = "REACHABLE"
    source = "reference/checks.md"


_VSM = {"/reference/checks/": _Route(), "/it/reference/checks/": _Route()}

_PAGE = "# Page\n\n[Checks Reference](../../../reference/checks) — spec.\n"


def _violations(*, locales: frozenset[str]) -> list[Violation]:
    docs = Path("/docs")
    src = docs / "tutorials" / "examples" / "z5xx-content" / "z501-placeholder.md"
    ctx = ResolutionContext(
        docs_root=docs,
        source_file=src,
        use_directory_urls=True,
        locale_names=locales,
    )
    return VSMBrokenLinkRule().check_vsm(src, _PAGE, cast("Mapping[str, Route]", _VSM), {}, ctx)


def test_a_top_level_directory_is_not_a_locale() -> None:
    """`tutorials` is a directory, not a language — no fallback, so Z101."""
    vio = _violations(locales=frozenset())
    assert len(vio) == 1, (
        f"the locale fallback stripped `tutorials` and accepted a broken link; got {vio!r}"
    )
    assert vio[0].code == "Z101"


def test_a_real_locale_still_falls_back() -> None:
    """The control: a genuinely localised page keeps the fallback."""
    docs = Path("/docs")
    src = docs / "it" / "reference" / "deep" / "page.md"
    ctx = ResolutionContext(
        docs_root=docs,
        source_file=src,
        use_directory_urls=True,
        locale_names=frozenset({"it"}),
    )
    # /it/reference/deep/page/ + ../../checks -> /it/reference/checks/ (present)
    page = "# P\n\n[c](../../checks)\n"
    assert (
        VSMBrokenLinkRule().check_vsm(src, page, cast("Mapping[str, Route]", _VSM), {}, ctx) == []
    )
