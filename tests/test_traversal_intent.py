# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Traversal intent is a fact about the href, not about where it resolves.

Before this, the traversal verdict was computed from the *resolved* target:
an href was a traversal when source-tree arithmetic put it outside
``docs_root``.  That coupled a Tier-0 security decision to two things it should
not depend on -- the depth convention of the URL scheme, and the contents of the
repository -- and it produced both errors at once:

* the **correct** spelling of an ordinary deep link (``../../../../reference/checks``
  from a four-deep page) resolved outside ``docs_root`` under tree arithmetic and
  raised ``Z202``, a non-suppressible finding with a Security Override; and
* once the base was corrected for directory URLs, ``..\\../etc/passwd`` resolved
  *inside* ``docs_root`` and raised **nothing at all** -- DQS 96/100, Gate Passed,
  exit 0, on a link to ``/etc/passwd``.

The second is the partition failure the enclosing comment in ``incremental.py``
warns about: ``rules.py`` skips an href whose intent is "suspicious", deferring
to the security tier, while the security tier declines because the target now
lands inside the docs root.  Two guards pointing at each other.

``traversal_intent`` is evaluated first and unconditionally, and either claims
the href or does not -- so there is no second branch computing an overlapping
condition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.resolver import page_url_depth, traversal_intent


# ── Signal 1: more `..` hops than the page URL can absorb ────────────────────


# ── Signal 2: the href names a system path, wherever it resolves ─────────────


@pytest.mark.parametrize(
    "href",
    [
        "..\\../etc/passwd",  # Windows separator
        "../../../../etc/passwd",  # classic
        "../../%2e%2e/etc/passwd",  # percent-encoded
        "../../ETC/passwd",  # case variant
    ],
)
def test_system_paths_are_claimed_whatever_the_depth(href: str) -> None:
    """A system path is claimed wherever it would land."""
    assert traversal_intent(href, page_url_depth=2) == "system"


@pytest.mark.parametrize(
    "href",
    [
        "../../guide/usr/manual.md",  # a section named usr/ is not a traversal
        "../../../sibling-repo/README.md",  # boundary crossing, no OS intent
        "../reference/checks",
        "./adapter-api",
        "z111-config-schema-error",
    ],
)
def test_ordinary_links_are_not_claimed(href: str) -> None:
    assert traversal_intent(href, page_url_depth=3) is None


# ── The decision must not consult the filesystem ─────────────────────────────


def test_intent_is_text_only() -> None:
    """No stat, no resolve: the verdict cannot depend on repository contents."""
    import os
    from typing import Any

    calls = {"n": 0}
    real: Any = os.stat

    def counting(*a: Any, **k: Any) -> Any:
        calls["n"] += 1
        return real(*a, **k)

    os.stat = counting
    try:
        for href in ("../../etc/passwd", "../../../../reference/checks", "./x"):
            traversal_intent(href, page_url_depth=3)
    finally:
        os.stat = real
    assert calls["n"] == 0, f"traversal_intent made {calls['n']} filesystem call(s)"


# ── page_url_depth: what a page's own URL can absorb ─────────────────────────


@pytest.mark.parametrize(
    ("rel", "use_dir_urls", "expected"),
    [
        ("a/b/leaf.md", True, 3),  # served at /a/b/leaf/
        ("a/b/index.md", True, 2),  # served at /a/b/
        ("a/b/README.md", True, 2),
        ("index.md", True, 0),  # served at /
        ("a/b/leaf.md", False, 2),  # flat URLs: no extra segment
    ],
)
def test_page_url_depth(rel: str, use_dir_urls: bool, expected: int) -> None:
    docs = Path("/docs")
    assert page_url_depth(docs / rel, docs, use_directory_urls=use_dir_urls) == expected


# ── A local directory named like a system one is not a traversal ─────────────
# `docs/etc/`, `docs/usr/`, `docs/var/`, `docs/sys/` are ordinary sections. An
# href into one attempts to leave nothing, so the `system` signal must not
# consider it -- otherwise the security tier claims the href, broken-link
# checking skips it as "security's", and a broken link into a section named
# `etc/` is reported by nobody. That is the defect
# `tests/test_security_tier_reach.py` guards, and dropping the traversal-shape
# precondition reintroduced it.


@pytest.mark.parametrize("directory", ["dev", "bin", "var", "usr", "etc", "sys"])
def test_a_plain_relative_link_into_a_system_named_section_is_not_claimed(
    directory: str,
) -> None:
    assert traversal_intent(f"{directory}/missing.md", page_url_depth=3) is None
    assert traversal_intent(f"{directory}/", page_url_depth=3) is None


@pytest.mark.parametrize("href", ["../../etc/passwd", "/etc/passwd"])
def test_the_same_name_reached_by_leaving_is_claimed(href: str) -> None:
    """Leading `..` or a leading `/` is what makes it an attempt to leave."""
    assert traversal_intent(href, page_url_depth=3) == "system"


# ── Hop excess applies only to hrefs the generator emits verbatim ────────────
# The signal's premise is that the browser resolves the href against the page
# URL. That holds only for spellings the generator passes through; a rewritten
# href (`.md`, or an asset) is resolved by the generator itself, which computes
# the depth correctly, so counting hops against the page URL says nothing.
#
# It also cannot say anything when the URL is not derivable from the file path:
# the blog plugin serves `docs/blog/posts/2026-04-28-welcome.md` at
# `/blog/2026/04/28/welcome-to-the-zenzic-blog/`, five segments where the source
# path suggests three. `../../../../rss.xml` is correct there and was briefly
# reported Z202 -- a non-suppressible security finding on a working feed link.


def test_a_system_path_is_still_claimed_even_when_rewritten() -> None:
    """The `system` signal does not depend on the verbatim premise."""
    assert traversal_intent("../../../../etc/passwd.md", page_url_depth=3) == "system"
