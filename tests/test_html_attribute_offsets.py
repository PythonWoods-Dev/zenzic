# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Attribute-level source positions for HTML findings (Z120-Z124).

Findings for these codes name one attribute in their message but used to mark
the entire opening tag, starting at column 0 — the message said one thing and
the caret pointed at everything, which is the opposite of caret-precise
diagnostics.

Fixing that at the reporting layer would have meant re-deriving each
attribute's position by searching the source line, which is guesswork in two
real cases: the same tag text twice on one line, and an attribute *name*
appearing inside an earlier attribute's *value*. Both are covered explicitly
below, because the parser now reports positions it actually knows rather than
positions something else re-discovers.

Offsets are columns within the node's own line, 0-based. They rest on the
extractor's existing masking invariant: comments, fences, inline code and math
are replaced character-for-character (newlines preserved), so an offset in the
masked buffer is the same offset in the original text.
"""

from __future__ import annotations

from zenzic.core.validator import PolyglotExtractor


def _nodes(text: str):
    return PolyglotExtractor().extract(text)


class TestTagColumn:
    def test_tag_at_line_start_has_column_zero(self) -> None:
        (node,) = _nodes('<a href="x.md">t</a>\n')
        assert node.col_start == 0

    def test_indented_tag_reports_its_real_column(self) -> None:
        text = 'Some prose <a href="x.md">t</a>\n'
        (node,) = _nodes(text)
        assert node.col_start == text.index("<a ")

    def test_tag_on_a_later_line_is_column_relative_not_absolute(self) -> None:
        text = 'first line\nsecond\n   <a href="x.md">t</a>\n'
        (node,) = _nodes(text)
        assert node.line_no == 3
        assert node.col_start == 3, "column must be within the line, not an offset into the file"


class TestAttributeColumns:
    def test_attribute_column_points_at_the_attribute_name(self) -> None:
        text = '<a href="x.md" hreflang="en">t</a>\n'
        (node,) = _nodes(text)
        assert node.attr_cols["hreflang"] == text.index("hreflang")

    def test_every_parsed_attribute_gets_a_column(self) -> None:
        text = '<a href="x.md" hreflang="en" ping="y">t</a>\n'
        (node,) = _nodes(text)
        for name in ("href", "hreflang", "ping"):
            assert name in node.attr_cols, f"{name} missing from attr_cols"
            assert node.attr_cols[name] == text.index(name + "=")

    def test_indented_tag_attribute_columns_include_the_tag_offset(self) -> None:
        text = 'prose here <a href="x.md" hreflang="en">t</a>\n'
        (node,) = _nodes(text)
        assert node.attr_cols["hreflang"] == text.index("hreflang")


class TestTheTwoCasesAHeuristicWouldHaveGuessed:
    """These are the reason the parser reports positions instead of the
    reporter re-deriving them."""

    def test_same_tag_text_twice_on_one_line_gets_distinct_columns(self) -> None:
        # A line-search heuristic would find the first occurrence for both.
        text = '<a href="x.md">a</a> and <a href="x.md">b</a>\n'
        first, second = _nodes(text)
        assert first.col_start == 0
        assert second.col_start == text.index("<a", 1)
        assert first.col_start != second.col_start
        assert first.attr_cols["href"] != second.attr_cols["href"]

    def test_attribute_name_appearing_inside_an_earlier_value_is_not_confused(self) -> None:
        # "onclick" appears first inside the *title value*, then as a real
        # attribute. A substring search would mark the value, not the attribute.
        text = '<a title="onclick demo" onclick="x()">t</a>\n'
        (node,) = _nodes(text)
        real_attr_col = text.index('onclick="x()"')
        inside_value_col = text.index("onclick demo")
        assert node.attr_cols["onclick"] == real_attr_col
        assert node.attr_cols["onclick"] != inside_value_col


class TestFindingsUseTheAttributeSpan:
    """End-to-end: the finding a user sees must mark the named attribute."""

    def test_z120_marks_the_attribute_not_the_whole_tag(self, tmp_path) -> None:
        from zenzic.core.adapters import get_adapter
        from zenzic.core.incremental import IncrementalAnalysisEngine
        from zenzic.models.config import BuildContext, ZenzicConfig
        from zenzic.models.vsm import VirtualSiteMap

        docs = tmp_path / "docs"
        docs.mkdir()
        line = '<a href="other.md" hreflang="en">link</a>'
        (docs / "index.md").write_text(f"# T\n\n{line}\n", encoding="utf-8")
        (docs / "other.md").write_text("# Other\n", encoding="utf-8")

        config = ZenzicConfig(docs_dir=docs.name, build_context=BuildContext(engine="standalone"))
        engine = IncrementalAnalysisEngine(
            config, None, get_adapter(config.build_context, docs, tmp_path), docs, tmp_path
        )
        found = engine._run_urp_checks(VirtualSiteMap(), docs / "index.md", f"# T\n\n{line}\n")
        z120 = [f for f in found if f.rule_id == "Z120"]
        assert z120, "fixture must produce a Z120 for the unknown attribute"
        f = z120[0]
        assert f.match_text == "hreflang", f"caret must span the attribute, got {f.match_text!r}"
        assert f.col_start == line.index("hreflang"), (
            f"caret must start at the attribute, got col {f.col_start}"
        )
