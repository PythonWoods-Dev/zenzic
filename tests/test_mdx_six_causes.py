# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The six causes behind 142 false positives on a 421-file MDX corpus.

One test pair per cause: the construct is no longer reported, and the near-miss
still is. The second half is the point -- a mask that silenced everything would
pass the first half and remove coverage, which is how a fix becomes a defect.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.content import check_bare_urls, check_malformed_lists
from zenzic.core.rules import CircularAnchorRule, MissingAltTextRule
from zenzic.core.validator import _extract_empty_link_texts


def _lists(text: str) -> list[int]:
    return [f.line_no for f in check_malformed_lists(Path("d.mdx"), text, containers=None)]


def _urls(text: str) -> list[int]:
    return [f.line_no for f in check_bare_urls(Path("d.mdx"), text, containers=None)]


# ── Cause 1: MDX's embedded JavaScript is not prose ──────────────────────────


def test_an_mdx_import_block_is_not_a_malformed_list() -> None:
    doc = "# T\n\nimport A from './A.astro';\nimport B from './B.astro';\nimport C from './C.astro';\n"
    assert _lists(doc) == []


def test_a_multi_line_export_is_not_a_malformed_list() -> None:
    """The Docusaurus shape: the finding landed in the body, not on the export."""
    doc = (
        "# T\n\n"
        "export const Highlight = ({children, color}) => (\n"
        "  <span\n"
        "    style={{\n"
        "      backgroundColor: color,\n"
        "      borderRadius: '20px',\n"
        "      color: '#fff',\n"
        "    }}>\n"
        "    {children}\n"
        "  </span>\n"
        ");\n"
    )
    assert _lists(doc) == []


def test_a_real_fake_list_is_still_reported() -> None:
    doc = "# T\n\nthe first requirement;\nthe second requirement;\nthe third requirement;\n"
    assert _lists(doc) == [3]


def test_prose_beginning_with_the_word_import_is_still_prose() -> None:
    """`import` alone is not an ESM statement; no `from "..."`, no brace."""
    doc = (
        "# T\n\nimport statements are useful;\nthey declare a dependency;\nand they are hoisted;\n"
    )
    assert _lists(doc) == [3]


# ── Cause 2: Z403 consults the fence tracker ─────────────────────────────────


def _alt(text: str) -> list[int]:
    return [f.line_no for f in MissingAltTextRule().check(Path("d.mdx"), text)]


def test_an_image_inside_a_fence_is_an_example() -> None:
    assert _alt('# T\n\n```astro\n<img src="/b.png" />\n```\n') == []
    assert _alt("# T\n\n```\n![](/c.png)\n```\n") == []


def test_an_image_in_prose_without_alt_is_still_reported() -> None:
    assert _alt("# T\n\n![](/a.png)\n") == [3]


# ── Cause 3: the JSX attribute mask spans lines ──────────────────────────────


def test_a_url_in_a_multi_line_jsx_attribute_is_not_prose() -> None:
    doc = '# T\n\n<LinkCard href="https://example.com/b"\n  title="x" />\n'
    assert _urls(doc) == []


def test_a_url_on_a_bare_attribute_continuation_line_is_not_prose() -> None:
    """5 of 16 sat on an `href="..."` line carrying neither `<` nor `>`.

    The shape is taken from the corpus rather than invented. An earlier version
    used `<a href="...">` inside a `<Card>`, which passed at the parent commit
    too -- that line closes its own tag, so `_HTML_TAG_RE` already masked it.
    The case that was actually failing has the element opening on one line and
    the URL on the next, with the closing `>` further down still.
    """
    doc = (
        "# T\n\n"
        '<LinkCard title="Migrating from Gatsby to Astro"\n'
        '  href="https://example.com/c"\n'
        '  description="A blog post" />\n'
    )
    assert _urls(doc) == []


def test_a_bare_url_in_prose_is_still_reported() -> None:
    doc = "# T\n\nVisit https://example.com/real for the list.\n"
    assert _urls(doc) == [3]


# ── Cause 4: Z107's section guard ────────────────────────────────────────────


def _anchors(text: str) -> list[int]:
    return [f.line_no for f in CircularAnchorRule().check(Path("d.mdx"), text)]


def test_a_link_before_the_first_heading_is_not_a_self_loop() -> None:
    """There is no enclosing section, so the link cannot navigate to itself."""
    doc = "Astro provides [scoped styles](#scoped-styles) and more.\n\n## Scoped Styles\n\nText.\n"
    assert _anchors(doc) == []


def test_a_link_inside_the_section_it_names_is_still_a_self_loop() -> None:
    doc = "# T\n\n## Scoped Styles\n\nAs [scoped styles](#scoped-styles) shows, this loops.\n"
    assert _anchors(doc) == [5]


# ── Cause 5: a URI scheme is not a site path ─────────────────────────────────


def test_a_custom_scheme_is_not_a_site_path() -> None:
    # Imported inside the test because the symbol is new: at the parent commit
    # the module has no `has_uri_scheme`, and a module-level import would stop
    # the whole file from collecting instead of failing this one cause.
    from zenzic.core.validator import has_uri_scheme

    for url in ("cursor://anysphere/mcp/install", "vscode:mcp/install", "raycast://x"):
        assert has_uri_scheme(url), url


def test_a_site_path_and_a_windows_drive_are_not_schemes() -> None:
    """A single-letter scheme is legal in RFC 3986 and would eat `C:/Users/...`."""
    from zenzic.core.validator import has_uri_scheme

    for url in ("/guides/example/", "./a.md", "a.md", "#frag", "C:/Users/x"):
        assert not has_uri_scheme(url), url


# ── Cause 6: the HTML <code> element, and a label containing a code span ─────


def test_a_type_inside_an_html_code_element_is_not_an_empty_link() -> None:
    doc = '# T\n\n**Type:** <code><a href="#routepart">RoutePart</a>[][]</code>\n'
    assert list(_extract_empty_link_texts(doc)) == []


def test_a_genuinely_empty_link_is_still_reported() -> None:
    doc = "# T\n\nSee []( ./x.md ) for details.\n"
    assert len(list(_extract_empty_link_texts(doc))) == 1
