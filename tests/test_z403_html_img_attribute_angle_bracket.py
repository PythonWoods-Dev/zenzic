# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""An ``<img>`` carrying ``alt=`` is not reported as missing it.

``_RE_HTML_IMG`` matched ``<img\\b[^>]*>``, which ends at the first ``>`` in the
tag -- including one inside an attribute *value*. A tag whose ``src`` or
``title`` contains ``>`` before ``alt=`` was therefore truncated before the
alt attribute was ever seen, and both Z403 (missing alt) and Z514 (generic alt)
read the truncated text.

Measured on the real engine before the fix: ``src="a.png?q=<x>"`` and
``title="a > b"`` with a perfectly good ``alt`` were both reported as having no
alt text; the same tag with the ``>`` *after* ``alt=`` was clean. Position, not
content, was the trigger -- so it is not about SVG or data URIs, which is how it
was first seen.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.rules import MissingAltTextRule


def _codes(text: str) -> list[str]:
    return [f.rule_id for f in MissingAltTextRule().check(Path("docs/index.md"), text)]


class TestAngleBracketInAnAttributeValue:
    def test_a_gt_in_src_before_alt_does_not_hide_the_alt(self) -> None:
        text = '<img src="a.png?q=<x>" alt="a real description">\n'
        assert _codes(text) == [], "alt= is present; the tag was truncated at the > in src"

    def test_a_gt_in_title_before_alt_does_not_hide_the_alt(self) -> None:
        text = '<img src="a.png" title="a > b" alt="a real description">\n'
        assert _codes(text) == [], "alt= is present; the tag was truncated at the > in title"

    def test_an_svg_data_uri_src_does_not_hide_the_alt(self) -> None:
        """The form this was first seen in, kept as the reported case."""
        text = (
            '<img src="data:image/svg+xml,<svg/onload=alert(1)>" '
            'alt="SVG injection via data: URI">\n'
        )
        assert _codes(text) == []


class TestStillReportsWhatItMust:
    """Negative controls: the fix must not silence a real missing alt."""

    def test_a_tag_with_no_alt_is_still_reported(self) -> None:
        assert _codes('<img src="b.png">\n') == ["Z403"]

    def test_a_tag_with_an_empty_alt_is_still_reported(self) -> None:
        assert _codes('<img src="b.png" alt="">\n') == ["Z403"]

    def test_a_tag_with_no_alt_and_a_gt_in_src_is_still_reported(self) -> None:
        assert _codes('<img src="b.png?q=<x>">\n') == ["Z403"]

    def test_a_plain_tag_with_alt_stays_clean(self) -> None:
        assert _codes('<img src="a.png" alt="described">\n') == []
