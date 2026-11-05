# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A tag named inside an inline code span is prose, not a tag.

Three surfaces stripped HTML from a line without first protecting inline code:
the heading slugifier, the multiple-`<h1>` check and link extraction. Each test
below asserts both directions -- the code span is left alone *and* the real tag
is still handled -- because a masker that silences everything would pass a
one-directional test and remove coverage.

A fourth site, ``validator.slug_tab_title``, is deliberately excluded: it is a
byte-for-byte replica of ``pymdownx.slugs``' own pattern, which does not mask
either, and matching the renderer is that function's whole contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.content import check_multiple_h1_headings
from zenzic.core.governance import _extract_links
from zenzic.core.validator import slug_heading


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("`<Image />`", "image"),
        ("`<Picture />`", "picture"),
        ("``<a `b` c>``", "a-b-c"),
        ("<Image />", ""),
        ("Plain Heading", "plain-heading"),
        ("`code` and <b>bold</b>", "code-and-bold"),
    ],
)
def test_slug_heading_treats_a_code_span_as_text(heading: str, expected: str) -> None:
    """The slug is what Python-Markdown's ``toc`` produces, verified against it."""
    assert slug_heading(heading) == expected


def _rendered_anchor(heading: str) -> str:
    markdown = pytest.importorskip("markdown")
    md = markdown.Markdown(extensions=["toc"])
    md.convert(f"# {heading}")
    anchors = [t["id"] for t in md.toc_tokens]
    return anchors[0] if anchors else ""


@pytest.mark.parametrize("heading", ["`<Image />`", "`<Picture />`", "Plain Heading", "`code`"])
def test_slug_heading_matches_the_renderer(heading: str) -> None:
    """The contract is the renderer's output, so assert against the renderer."""
    assert slug_heading(heading) == _rendered_anchor(heading)


def test_an_empty_slug_is_where_the_two_still_diverge() -> None:
    """A real tag as the whole heading leaves nothing to slugify.

    Recorded rather than hidden: ``slug_heading`` returns the empty string and
    Python-Markdown substitutes a positional fallback (``_1``). The divergence
    predates the code-span fix and is unaffected by it -- a heading that is
    nothing but an HTML tag has no text either way -- but a test asserting
    agreement across the board would have had to exclude this case silently.
    """
    assert slug_heading("<Image />") == ""
    assert _rendered_anchor("<Image />") == "_1"


def test_an_h1_named_in_backticks_is_not_an_h1() -> None:
    """Documentation about HTML writes `<h1>` constantly; it is not a heading.

    The shape is taken from the corpus file that reported it rather than
    invented: a tutorial with a real `#` heading and a complete `<h1>...</h1>`
    quoted as an example inside a JSX block. An earlier version of this test
    used an *unclosed* `<h1>` and passed against the defect, because the
    pattern requires the closing tag -- the test was wrong, not the fix.
    """
    in_prose = (
        "# Tutorial\n\n"
        "<Box>\n"
        "  <Option>\n"
        "    use a standard HTML element with static text (e.g `<h1>Home Page</h1>`)\n"
        "  </Option>\n"
        "</Box>\n"
    )
    assert check_multiple_h1_headings(Path("doc.mdx"), in_prose, containers=None) == []


def test_a_real_html_h1_is_still_counted() -> None:
    """The other direction: masking must not blind the check to a live tag."""
    two_headings = "# Tutorial\n\n<h1>A second, real one</h1>\n"
    assert len(check_multiple_h1_headings(Path("doc.md"), two_headings, containers=None)) == 1


def test_a_link_shown_as_an_example_is_not_followed() -> None:
    """An `<a href>` displayed in backticks is a code sample, not an edge."""
    assert _extract_links('Write `<a href="./x.md">text</a>` to link.') == []


def test_a_real_link_is_still_extracted() -> None:
    """The other direction, on the same shape."""
    assert _extract_links('<a href="./x.md">text</a>') == ["./x.md"]
