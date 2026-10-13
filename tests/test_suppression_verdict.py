# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``explain_suppression`` reports why a finding is suppressed, and changes nothing.

``is_suppressed`` answers only *whether*, and it answers by mutating: it consumes
the matching inline directive and marks governance policies used, both of which
feed ``Z603`` dead-suppression detection. An editor hover that wants to explain a
suppression therefore cannot call it — hovering would silently consume a directive
and make a legitimate ``Z603`` disappear.

So the decision is split rather than replaced. ``explain_suppression`` holds the
single decision tree and is free of side effects; ``is_suppressed`` calls it and
then applies the state changes its verdict implies. One tree, two entry points,
no possibility of the two disagreeing about the answer.

``is_suppressed`` deliberately keeps returning a plain ``bool``. Returning the
verdict instead would have broken ten existing assertions that compare against the
``True``/``False`` singletons (``assert suppressed is False``), which ``__bool__``
cannot satisfy, and would allocate an object per finding on the scanning hot path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.suppressions import SuppressionTracker, SuppressionVerdict


_IGNORE = "<!-- zenzic:ignore: Z101 -->"


def _tracker(text: str, **kwargs: object) -> SuppressionTracker:
    return SuppressionTracker(Path("docs/index.md"), text, **kwargs)  # type: ignore[arg-type]


class TestVerdictSources:
    def test_inline_directive(self) -> None:
        verdict = _tracker(f"[a](b.md) {_IGNORE}\n").explain_suppression(1, "Z101")
        assert verdict.suppressed is True
        assert verdict.source == "inline"
        assert verdict.pattern is None

    def test_directory_policy_carries_its_glob(self) -> None:
        tracker = _tracker("text\n", globally_suppressed_codes={"Z101": ["archive/**"]})
        verdict = tracker.explain_suppression(1, "Z101")
        assert verdict.suppressed is True
        assert verdict.source == "directory-policy"
        assert verdict.pattern == "archive/**"

    def test_adr_093_outranks_a_directory_policy_in_the_tracker(self) -> None:
        """Pre-existing precedence, pinned so the split cannot silently alter it.

        The ADR-093 check precedes the governance check, so a Z4xx code carrying
        a directory_policy still reports ``non-inline-suppressible`` here. That is
        not a contradiction: policy suppression for those codes is applied by
        ``governance.apply_directory_policies``, never through this tracker.
        """
        tracker = _tracker("text\n", globally_suppressed_codes={"Z402": ["archive/**"]})
        verdict = tracker.explain_suppression(1, "Z402")
        assert verdict.suppressed is False
        assert verdict.source == "non-inline-suppressible"

    def test_non_suppressible_security_code(self) -> None:
        verdict = _tracker(f"secret {_IGNORE}\n").explain_suppression(1, "Z201")
        assert verdict.suppressed is False
        assert verdict.source == "non-suppressible"

    def test_non_inline_suppressible_code_adr_093(self) -> None:
        verdict = _tracker("text\n").explain_suppression(1, "Z410")
        assert verdict.suppressed is False
        assert verdict.source == "non-inline-suppressible"

    def test_nothing_suppresses_it(self) -> None:
        verdict = _tracker("plain text\n").explain_suppression(1, "Z101")
        assert verdict.suppressed is False
        assert verdict.source == "none"


class TestPurity:
    """The property the hover depends on: explaining must not change state."""

    def test_explaining_does_not_consume_an_inline_directive(self) -> None:
        tracker = _tracker(f"[a](b.md) {_IGNORE}\n")
        for _ in range(5):
            assert tracker.explain_suppression(1, "Z101").source == "inline"
        assert tracker.directives[0].consumed is False, (
            "explain_suppression consumed a directive; a hover would silently "
            "delete the Z603 dead-suppression finding for it"
        )
        assert tracker.get_dead_suppressions() != [], "the Z603 finding must survive"

    def test_explaining_does_not_mark_a_policy_used(self) -> None:
        tracker = _tracker("text\n", globally_suppressed_codes={"Z402": ["archive/**"]})
        tracker.explain_suppression(1, "Z402")
        assert tracker.consumed_global_patterns == set()

    def test_is_suppressed_still_consumes(self) -> None:
        """The mutating half must keep mutating."""
        tracker = _tracker(f"[a](b.md) {_IGNORE}\n")
        assert tracker.is_suppressed(1, "Z101") is True
        assert tracker.directives[0].consumed is True
        assert tracker.get_dead_suppressions() == []


class TestOneDecisionTree:
    """is_suppressed and explain_suppression can never disagree on the answer."""

    @pytest.mark.parametrize(
        ("code", "text", "globals_"),
        [
            ("Z101", f"[a](b.md) {_IGNORE}\n", None),
            ("Z101", "plain text\n", None),
            ("Z201", f"secret {_IGNORE}\n", None),
            ("Z410", "text\n", None),
            ("Z402", "text\n", {"Z402": ["archive/**"]}),
            ("Z101", "text\n", {"Z101": ["archive/**"]}),
            ("Z101", "text\n", {"Z999": ["other/**"]}),
        ],
    )
    def test_agreement(self, code: str, text: str, globals_: dict[str, list[str]] | None) -> None:
        explained = _tracker(text, globally_suppressed_codes=globals_).explain_suppression(1, code)
        decided = _tracker(text, globally_suppressed_codes=globals_).is_suppressed(1, code)
        assert explained.suppressed is decided


class TestBackwardCompatibility:
    """is_suppressed's return type is unchanged — the claim, asserted directly."""

    def test_returns_the_real_bool_singletons(self) -> None:
        tracker = _tracker(f"[a](b.md) {_IGNORE}\n")
        assert tracker.is_suppressed(1, "Z101") is True
        assert _tracker("plain\n").is_suppressed(1, "Z101") is False

    def test_verdict_is_truthy_in_a_condition(self) -> None:
        assert bool(SuppressionVerdict(True, "inline")) is True
        assert bool(SuppressionVerdict(False, "none")) is False
        assert not SuppressionVerdict(False, "non-suppressible")
