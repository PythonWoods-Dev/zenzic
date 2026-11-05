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
  ``severity="error"`` at both emission sites while ``codes.py`` classified it
  ``warning``. (The registry was the one that moved, in the end: Z902 became
  ``error`` on 2026-09-19 because a rule that timed out did not run. These
  tests assert agreement with the registry, not its value.)

Same bug shape as Z301/Z406/Z503, now confirmed in a second independent
subsystem.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.codes import code_severity
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

    def check_vsm(self, file_path, text, vsm, anchors_cache, containers=None):
        raise ZenzicRuleTimeout("simulated timeout for testing")


def test_z107_is_error_not_warning() -> None:
    """A Z107 finding must be error-level, matching codes.py's
    CodeDefinition("error", 1.0, "structural") -- not hardcoded as a warning."""
    rule = CircularAnchorRule()
    # The link must sit *inside* the section its fragment names; before the
    # first heading there is no enclosing section and Z107 does not apply.
    # Plain heading, not `## Security Gate {#security-gate}`. `rules._slugify`
    # slugifies the attr-list along with the text -- it returns
    # 'security-gate-{#security-gate}' where `validator.slug_heading` returns
    # 'security-gate' -- so Z107's guard can never match inside such a section.
    # Two implementations disagreeing, not one being wrong; rowed rather than
    # worked around, and measured at 368 affected headings in this repository.
    text = "## Security Gate\n\nSee [security-gate](#security-gate) below.\n"
    findings = rule.check(Path("docs/example.md"), text)

    z107_findings = [f for f in findings if f.rule_id == "Z107"]
    assert z107_findings, "Expected at least one Z107 finding from the fixture text"
    assert all(f.severity == "error" for f in z107_findings), (
        f"Z107 findings must be severity='error' per codes.py, got: "
        f"{[f.severity for f in z107_findings]}"
    )


def test_z902_severity_in_run_comes_from_the_registry() -> None:
    """A Z902 finding from AdaptiveRuleEngine.run() must carry whatever
    `codes.py` classifies Z902 as.

    This asserted the literal `"warning"` until 2026-09-19, which made it a
    second copy of the number it exists to protect: promoting Z902 to `error`
    in the registry broke a test whose subject is *agreement with the
    registry*, not the registry's value. The regression it guards -- a
    hardcoded severity at the emission site -- is unchanged and still caught,
    because a hardcoded literal cannot follow `code_severity()`.
    """
    engine = AdaptiveRuleEngine([_TimeoutRule()], containers=None)
    findings = engine.run(Path("docs/example.md"), "# Example\n")

    z902_findings = [f for f in findings if f.rule_id == "Z902"]
    assert z902_findings, "Expected a Z902 finding when a rule raises ZenzicRuleTimeout"
    expected = code_severity("Z902")
    assert all(f.severity == expected for f in z902_findings), (
        f"Z902 findings must carry codes.py's severity ({expected!r}), got: "
        f"{[f.severity for f in z902_findings]}"
    )


def test_z902_severity_in_run_vsm_comes_from_the_registry() -> None:
    """Same as above, for the run_vsm() code path specifically -- a
    separate emission site with its own duplicated exception handling."""
    engine = AdaptiveRuleEngine([_TimeoutRule()], containers=None)
    findings = engine.run_vsm(Path("docs/example.md"), "# Example\n", {}, {})

    z902_findings = [f for f in findings if f.rule_id == "Z902"]
    assert z902_findings, (
        "Expected a Z902 finding when a rule raises ZenzicRuleTimeout in check_vsm"
    )
    expected = code_severity("Z902")
    assert all(f.severity == expected for f in z902_findings), (
        f"Z902 findings must carry codes.py's severity ({expected!r}), got: "
        f"{[f.severity for f in z902_findings]}"
    )
