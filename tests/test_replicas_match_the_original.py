# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every replica of external behaviour the core carries, compared to the original.

`Z102` needs the anchors `pymdownx.tabbed` mints for content tabs, so
`zenzic.core.validator.slug_tab_title` reimplements `pymdownx.slugs.slugify`.
The core must not import it — ADR-075, and it is not a runtime dependency — so
the implementation is a **replica of external behaviour**, and a replica
diverges in silence when the original changes.

A test is not the core. `pymdown-extensions` is declared in the `test`
dependency group for exactly this file, so the divergence surfaces here rather
than as a wrong finding on a user's corpus.

There is no `importorskip` on purpose: a check that disappears with its subject
is not a check (Rule 31). If this import fails, the dependency declaration is
what needs fixing.
"""

from __future__ import annotations

import markdown
import pytest
from pymdownx.slugs import slugify

from zenzic.core.validator import slug_tab_title, tab_anchors_in


_TITLES = [
    "Open me in a new tab ...",
    "... or me ...",
    "... or even me",
    "Hello, World!",
    "Tab   with   spaces",
    "Ünïcodé tàb",
    "A/B & C",
    "  leading and trailing  ",
    "CamelCase Tab",
    "tab_with_underscore",
    "1. Numbered",
    "",
    "---",
    "<em>markup</em> inside",
    "emoji :material-link: here",
]


@pytest.mark.parametrize("title", _TITLES)
def test_slug_tab_title_matches_pymdownx(title: str) -> None:
    """Character for character, against the installed `pymdownx`."""
    assert slug_tab_title(title) == slugify(case="lower")(title, "-")


def _render_ids(source: str, **options: object) -> list[str]:
    md = markdown.Markdown(
        extensions=["toc", "pymdownx.tabbed"],
        extension_configs={"pymdownx.tabbed": {"alternate_style": True, **options}},
    )
    return [chunk.split('"')[0] for chunk in md.convert(source).split('id="')[1:]]


_DOC = """### Anchor links

Intro.

=== "Open me in a new tab ..."

    First tab!

=== "... or me ..."

    Second tab!

=== "... or even me"

    Third tab!
"""


def test_combined_style_matches_what_pymdownx_renders() -> None:
    """`slugify` + `combine_header_slug` — the foreign corpus's configuration."""
    rendered = _render_ids(_DOC, slugify=slugify(case="lower"), combine_header_slug=True)
    tab_ids = [i for i in rendered if i != "anchor-links"]
    assert sorted(tab_anchors_in(_DOC, tabs="combined")) == sorted(tab_ids)


def test_slug_style_matches_what_pymdownx_renders() -> None:
    """`slugify` alone, with no header prefix."""
    rendered = _render_ids(_DOC, slugify=slugify(case="lower"))
    tab_ids = [i for i in rendered if i != "anchor-links"]
    assert sorted(tab_anchors_in(_DOC, tabs="slug")) == sorted(tab_ids)


def test_indexed_style_matches_what_pymdownx_renders() -> None:
    """Neither option — the counter form, and our own repository's configuration."""
    rendered = _render_ids(_DOC)
    tab_ids = [i for i in rendered if i != "anchor-links"]
    assert sorted(tab_anchors_in(_DOC, tabs="indexed")) == sorted(tab_ids)


# ── The second replica: heading slugs ─────────────────────────────────────────

_HEADINGS = [
    "Integrità",
    "Hello, World!",
    "Ünïcodé tàb",
    "A/B & C",
    "CamelCase",
    "1. Numbered",
    "Trailing ...",
    "  spaces  ",
    "under_score",
    "Ärger mit Umlauten",
    "日本語の見出し",
    "𝐀 styled",
    "C++ and C#",
    "",
]


@pytest.mark.parametrize("heading", _HEADINGS)
def test_slug_heading_matches_python_markdown_toc(heading: str) -> None:
    """`slug_heading` replicates `markdown.extensions.toc.slugify` — check it still does.

    This replica is older and far more consequential than the tab one: every
    `Z102` and `Z107` verdict rests on it. It had no declared version and no
    comparison until the tab replica's own divergence made the class visible.

    It passes today on every case tried, including CJK and styled codepoints.
    That is the point of pinning it: nothing would have told us when it stopped.
    """
    from markdown.extensions.toc import slugify as toc_slugify

    from zenzic.core.validator import slug_heading

    assert slug_heading(heading) == toc_slugify(heading, "-")
