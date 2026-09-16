# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""An HTML anchor target whose tag carries ``>`` in an earlier attribute still registers.

``_HTML_ID_RE`` matched ``<[^>]*\\bid=...>``, which ends at the first ``>`` in the
tag -- including one inside a quoted attribute *value*. A tag such as
``<span title="a > b" id="target">`` was therefore truncated before ``id=`` was
reached, the anchor never entered the target set, and a link to ``#target`` was
reported as ``Z102 ANCHOR_MISSING`` against a target that plainly exists.

Measured with a control pair before the fix: the same tag with the ``>`` placed
*after* ``id=`` was clean, and so was the tag without one. Position, not content.
Same family as the ``_RE_HTML_IMG`` truncation fixed alongside this, and the same
remedy ``validator.py`` already introduced for the security tier.
"""

from __future__ import annotations

from zenzic.core.validator import _HTML_ID_RE


def _ids(line: str) -> list[str]:
    return [m.group(1) for m in _HTML_ID_RE.finditer(line)]


class TestAngleBracketBeforeTheIdAttribute:
    def test_a_gt_in_an_earlier_attribute_does_not_hide_the_id(self) -> None:
        assert _ids('<span title="a > b" id="target">x</span>') == ["target"]

    def test_a_gt_in_an_earlier_single_quoted_attribute_does_not_hide_the_id(self) -> None:
        assert _ids("<span title='a > b' id='target'>x</span>") == ["target"]


class TestStillFindsWhatItMust:
    """Negative controls: the fix must not invent or lose ordinary ids."""

    def test_a_plain_tag_still_yields_its_id(self) -> None:
        assert _ids('<span id="target">x</span>') == ["target"]

    def test_a_gt_after_the_id_was_already_fine_and_stays_fine(self) -> None:
        assert _ids('<span id="target" title="a > b">x</span>') == ["target"]

    def test_a_tag_with_no_id_yields_nothing(self) -> None:
        assert _ids('<span class="x">y</span>') == []
