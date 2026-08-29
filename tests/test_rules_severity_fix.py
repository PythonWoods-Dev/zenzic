# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP.

Two more hardcoded-severity-literal instances were found in
``src/zenzic/core/rules.py`` during the bounded ``rules.py`` sweep that
followed the ``_check.py`` fix (V031_SEVERITY_HARDCODE_ARCHITECTURAL_REMEDIATION):

- ``Z107`` (``CircularAnchorRule``): hardcoded ``severity="warning"``, but
  ``codes.py:232`` classifies it ``error``.
- ``Z902`` (``RULE_TIMEOUT``, emitted by ``AdaptiveRuleEngine.run()`` and
  ``run_vsm()`` when a rule raises ``ZenzicRuleTimeout``): hardcoded
  ``severity="error"`` at both emission sites, but ``codes.py:318``
  classifies it ``warning``.

Same bug shape as Z301/Z406/Z503, now confirmed in a second independent
subsystem.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.exceptions import ZenzicRuleTimeout
from zenzic.core.rules import AdaptiveRuleEngine, BaseRule, CircularAnchorRule, RuleFinding


class _TimeoutRule(BaseRule):
    """Minimal fake rule that always raises ZenzicRuleTimeout, for testing
    AdaptiveRuleEngine's Z902 handling without an actual slow rule."""

    @property
    def rule_id(self) -> str:
        return "ZZ-FAKE-TIMEOUT"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        raise ZenzicRuleTimeout("simulated timeout for testing")

    def check_vsm(self, file_path, text, vsm, anchors_cache, context=None):
        raise ZenzicRuleTimeout("simulated timeout for testing")


def test_z107_is_error_not_warning() -> None:
    """A Z107 finding must be error-level, matching codes.py's
    CodeDefinition("error", 1.0, "structural") -- not hardcoded as a warning."""
    rule = CircularAnchorRule()
    text = "See [security-gate](#security-gate) below.\n\n## Security Gate {#security-gate}\n"
    findings = rule.check(Path("docs/example.md"), text)

    z107_findings = [f for f in findings if f.rule_id == "Z107"]
    assert z107_findings, "Expected at least one Z107 finding from the fixture text"
    assert all(f.severity == "error" for f in z107_findings), (
        f"Z107 findings must be severity='error' per codes.py, got: "
        f"{[f.severity for f in z107_findings]}"
    )


def test_z902_is_warning_not_error_in_run() -> None:
    """A Z902 finding from AdaptiveRuleEngine.run() must be warning-level,
    matching codes.py's CodeDefinition("warning", 0.0, None)."""
    engine = AdaptiveRuleEngine([_TimeoutRule()])
    findings = engine.run(Path("docs/example.md"), "# Example\n")

    z902_findings = [f for f in findings if f.rule_id == "Z902"]
    assert z902_findings, "Expected a Z902 finding when a rule raises ZenzicRuleTimeout"
    assert all(f.severity == "warning" for f in z902_findings), (
        f"Z902 findings must be severity='warning' per codes.py, got: "
        f"{[f.severity for f in z902_findings]}"
    )


def test_z902_is_warning_not_error_in_run_vsm() -> None:
    """Same as above, for the run_vsm() code path specifically -- a
    separate emission site with its own duplicated exception handling."""
    engine = AdaptiveRuleEngine([_TimeoutRule()])
    findings = engine.run_vsm(Path("docs/example.md"), "# Example\n", {}, {})

    z902_findings = [f for f in findings if f.rule_id == "Z902"]
    assert z902_findings, (
        "Expected a Z902 finding when a rule raises ZenzicRuleTimeout in check_vsm"
    )
    assert all(f.severity == "warning" for f in z902_findings), (
        f"Z902 findings must be severity='warning' per codes.py, got: "
        f"{[f.severity for f in z902_findings]}"
    )
