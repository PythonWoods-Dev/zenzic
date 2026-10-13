# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A `>` inside a quoted attribute value must not end the tag.

Both HTML and MDX permit an unescaped `>` inside a quoted attribute. Two tag
regexes used a bare negated-`>` region for the attribute span, so
`<a title="a > b" href="javascript:alert(1)">` stopped matching inside `title`
and `href` was never parsed.

The security consequence is the reason this is a test and not a tidy-up: the
forbidden-scheme check (`Z205`, exit 2, non-suppressible) never saw the href,
and the run finished at exit 1 with a suppressible `Z121`. A wrong finding at a
lower tier is worse than no finding, because the scanner looks like it engaged.

Every case here pairs the payload with a control that must keep its existing
behaviour, because a pattern that matches nothing at all would also make the
payload assertions pass.
"""

from __future__ import annotations

import pytest

from zenzic.core.rules import _HTML_HREF_ATTR_RE, _HTML_HREF_RE
from zenzic.core.validator import PolyglotExtractor


@pytest.fixture
def extractor() -> PolyglotExtractor:
    return PolyglotExtractor()


class TestSecurityTierSeesTheHref:
    """`validator.py`'s tag pattern feeds the forbidden-scheme check."""

    def test_gt_inside_a_double_quoted_attribute(self, extractor: PolyglotExtractor) -> None:
        nodes = list(extractor.extract('<a title="a > b" href="javascript:alert(1)">x</a>'))
        assert nodes, "the tag was not extracted at all"
        assert nodes[0].z205_scheme == "javascript:"

    def test_gt_inside_a_single_quoted_attribute(self, extractor: PolyglotExtractor) -> None:
        nodes = list(extractor.extract("<a title='a > b' href='javascript:alert(1)'>x</a>"))
        assert nodes, "the tag was not extracted at all"
        assert nodes[0].z205_scheme == "javascript:"

    def test_control_no_gt_still_detected(self, extractor: PolyglotExtractor) -> None:
        nodes = list(extractor.extract('<a href="javascript:alert(1)">x</a>'))
        assert nodes and nodes[0].z205_scheme == "javascript:"

    def test_control_a_benign_tag_is_still_extracted(self, extractor: PolyglotExtractor) -> None:
        nodes = list(extractor.extract('<img src="./x.png" alt="w > h">'))
        assert nodes, "a benign tag carrying a `>` in an attribute was dropped"
        assert nodes[0].z205_scheme is None

    def test_unbalanced_quotes_keep_their_previous_behaviour(
        self, extractor: PolyglotExtractor
    ) -> None:
        # A browser parses `title` as `unclosed href=` here, so the anchor has
        # no href and no scheme. The tag must still be seen -- dropping it
        # would trade a mis-tiered finding for a missing one.
        nodes = list(extractor.extract('<a title="unclosed href="javascript:alert(1)">x</a>'))
        assert nodes, "an unbalanced-quote tag must still be extracted"
        assert nodes[0].z205_scheme is None


class TestQualityTierSeesTheHref:
    """`rules.py`'s pattern feeds the broken-link check."""

    def test_gt_inside_an_attribute_before_href(self) -> None:
        text = '<a title="a > b" href="./missing.md">x</a>'
        m = _HTML_HREF_RE.search(text)
        assert m, "the tag was not matched, so the link is invisible to the link graph"
        attr = _HTML_HREF_ATTR_RE.search(m.group(0))
        assert attr and attr.group(1) == "./missing.md"

    def test_control_no_gt(self) -> None:
        m = _HTML_HREF_RE.search('<a href="./missing.md">x</a>')
        assert m is not None
        attr = _HTML_HREF_ATTR_RE.search(m.group(0))
        assert attr and attr.group(1) == "./missing.md"
