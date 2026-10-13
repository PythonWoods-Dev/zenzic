# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""HTML blocks, derived from CommonMark §4.6 rather than from the defects found.

§4.6 defines seven block types with different opening and closing conditions.
Two of them decide what `_mask_html_blocks` hides from the content rules:

* **Type 1** — `pre`, `script`, `style`, `textarea` — runs to its closing tag.
  A blank line inside one means nothing.
* **Type 6** — a block-level tag name at the start of a line — ends at the
  **first blank line**, not at the matching close tag.

The engine closed every block on tag depth, so everything between a blank line
and the eventual `</div>` was hidden. Measured before the change: 139 of 141
HTML blocks in this repository's documentation have that shape, and the fix made
**3,620 lines across 85 files** visible again with **zero** newly hidden.

The other five types are not modelled here, and that is stated rather than
implied: types 2 to 5 are reached by the comment and tag masking elsewhere in
the chain, and type 7 — any complete tag on a line of its own — has no
representation, so a custom element opens no block. Each is a decision about
consequence, not about completeness.
"""

from __future__ import annotations

import pytest

from zenzic.core.content import _BLOCK_TAGS, _TYPE1_TAGS, _VOID_TAGS, _mask_html_blocks


def _visible(text: str) -> list[str]:
    return [line.strip() for line in _mask_html_blocks(text).splitlines() if line.strip()]


# ── The tag lists against the specification ──────────────────────────────────

#: §4.6's own type-1 list.
_SPEC_TYPE1 = {"pre", "script", "style", "textarea"}

#: §4.6's own type-6 list, written out so a change to either side is a visible
#: difference rather than something absorbed.
_SPEC_TYPE6 = {
    "address",
    "article",
    "aside",
    "base",
    "basefont",
    "blockquote",
    "body",
    "caption",
    "center",
    "col",
    "colgroup",
    "dd",
    "details",
    "dialog",
    "dir",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "frame",
    "frameset",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "header",
    "hr",
    "html",
    "iframe",
    "legend",
    "li",
    "link",
    "main",
    "menu",
    "menuitem",
    "nav",
    "noframes",
    "ol",
    "optgroup",
    "option",
    "p",
    "param",
    "search",
    "section",
    "summary",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "title",
    "tr",
    "track",
    "ul",
}


def test_the_tag_list_is_exactly_the_specification() -> None:
    """It was a hand-compiled subset: 36 of the 66 names were missing.

    One of them, `textarea`, is a type-1 tag — so a `<textarea>` opened no block
    at all. The rest were type 6. Nothing was ever present that the
    specification does not name, so the list was short rather than wrong.
    """
    assert _BLOCK_TAGS == _SPEC_TYPE1 | _SPEC_TYPE6


def test_type1_is_the_four_the_specification_names() -> None:
    assert _TYPE1_TAGS == _SPEC_TYPE1


def test_the_void_elements_never_open_a_block() -> None:
    """A void element has no closing tag, so treating one as an opener would
    mask everything after it to the end of the document."""
    for tag in ("hr", "br", "img", "link", "base", "col", "param", "track", "basefont", "frame"):
        assert tag in _VOID_TAGS, tag
        assert _visible(f"# T\n\n<{tag}>\n\nDopo.\n") == ["# T", "Dopo."]


# ── Type 6: the blank line closes it ─────────────────────────────────────────


def test_a_blank_line_closes_a_type6_block() -> None:
    """The measured defect: prose after the blank line was hidden."""
    doc = '# T\n\n<div class="n">\nDentro.\n\nFuori, secondo §4.6.\n\n</div>\n\nFine.\n'
    assert "Fuori, secondo §4.6." in _visible(doc)


def test_a_type6_block_without_a_blank_line_stays_closed_by_its_tag() -> None:
    """The positive control: the previous behaviour is correct where it applied."""
    doc = "# T\n\n<div>\nDentro.\n</div>\n\nFuori.\n"
    visible = _visible(doc)
    assert "Dentro." not in visible
    assert "Fuori." in visible


@pytest.mark.parametrize("tag", ["div", "section", "table", "ul", "figure", "details"])
def test_every_type6_tag_opens_a_block(tag: str) -> None:
    doc = f"# T\n\n<{tag}>\nNascosto.\n</{tag}>\n\nVisibile.\n"
    visible = _visible(doc)
    assert "Nascosto." not in visible
    assert "Visibile." in visible


# ── Type 1: the blank line means nothing ─────────────────────────────────────


@pytest.mark.parametrize("tag", sorted(_SPEC_TYPE1))
def test_a_blank_line_does_not_close_a_type1_block(tag: str) -> None:
    """§4.6's own exception, and the reason type 6's rule could not be applied
    to everything."""
    doc = f"# T\n\n<{tag}>\nprima\n\ndopo la riga vuota\n</{tag}>\n\nFuori.\n"
    visible = _visible(doc)
    assert "dopo la riga vuota" not in visible, tag
    assert "Fuori." in visible, tag


def test_an_unclosed_type1_block_runs_to_the_end() -> None:
    """§4.6: type 1 ends at its closing tag or at the end of the document."""
    assert _visible("# T\n\n<script>\nvar a = 1;\n\nvar b = 2;\n") == ["# T"]


# ── A tag named in prose is not a tag ────────────────────────────────────────


@pytest.mark.parametrize("tag", ["div", "script", "table", "html"])
def test_a_tag_inside_an_inline_code_span_opens_nothing(tag: str) -> None:
    """A documentation tool writes these in backticks constantly.

    Before this, the mention opened a block that never closed and hid the rest
    of the file from `Z511` — measured at 7 files and 533 lines here, 3 files and
    850 lines on the external corpus.
    """
    doc = f"# T\n\nIl tag `<{tag}>` si usa cosi.\n\nQuesta riga resta prosa.\n"
    assert "Questa riga resta prosa." in _visible(doc)


def test_a_real_tag_outside_backticks_still_opens_a_block() -> None:
    """The positive control for the one above."""
    doc = "# T\n\n<div>\nNascosto.\n</div>\n\nVisibile.\n"
    assert "Nascosto." not in _visible(doc)


# ── What is not modelled, pinned so the limit stays visible ──────────────────


def test_type7_is_not_modelled_and_the_limit_is_pinned() -> None:
    """A custom element on a line of its own is §4.6 type 7 and opens no block.

    Recorded rather than fixed: type 7 would make every unknown tag hide the
    lines after it, and the consequence of *not* modelling it is that such text
    is scanned as prose — findings appear rather than disappear, which is the
    direction that gets noticed.
    """
    doc = '# T\n\n<custom-el attr="x">\nTesto subito sotto.\n\nDopo.\n'
    assert "Testo subito sotto." in _visible(doc)


def test_a_single_line_comment_is_masked_incidentally() -> None:
    """Type 2 is not modelled here, and a one-line comment is still blanked.

    Not by design: `_OPEN_TAG_RE` requires a letter after the angle bracket, so
    `<!--` never opens a block — but the inline tag mask matches the comment
    end to end and blanks it anyway. Measured rather than assumed; the first
    version of this test asserted the opposite and was wrong.
    """
    assert _visible("# T\n\n<!-- un commento -->\n\nDopo.\n") == ["# T", "Dopo."]


def test_a_comment_spanning_lines_is_not_masked_here() -> None:
    """And that is the limit the incidental masking leaves.

    A comment broken across lines matches neither the block opener nor the
    inline mask, so its text reaches the content rules. Type 2 is handled by the
    comment maskers in the polyglot chain, which this function is not part of.
    Pinned so the gap is visible rather than discovered.
    """
    doc = "# T\n\n<!-- apre\ncorpo del commento\nchiude -->\n\nDopo.\n"
    assert "corpo del commento" in _visible(doc)
