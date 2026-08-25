# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for V031_ADR093_ENFORCEMENT_FIX_AND_HYGIENE_CLOSEOUT Phase B.

Exhaustive enumeration of scanner.py's RuleFinding(...) construction sites
(8 sites, following the same method already proven for _check.py, rules.py,
and incremental.py) found two live severity mismatches against codes.py's
CODE_DEFINITIONS -- scanner.py is the fourth subsystem this session to
exhibit the "hardcoded severity literal bypasses the SSoT" bug:

- Z106 (CIRCULAR_LINK): codes.py says "note" (-> "info"), scanner.py's
  circular-cycle detection in _run_vsm_and_urp_pass() hardcoded "error".
- Z902 (RULE_TIMEOUT): codes.py says "warning", scanner.py's
  _make_timeout_report() hardcoded "error" -- a second, independent live
  site for the exact Z902 bug already fixed once this session in rules.py.

The other 6 RuleFinding sites (Z201, Z410, Z411, Z412, Z112, Z901) already
matched codes.py by inspection -- not treated as proof of correctness, per
the standing caution this session (both _check.py and rules.py had "mostly
correct" majorities hiding live bugs, and incremental.py's 17-site sweep
found 3 mismatches despite an earlier 6-site sample all matching).

Two further sites (scanner.py's _map_credential_to_finding, lines ~226-241)
construct the CLI-layer `Finding` class (not `RuleFinding`) with a bare
`severity="security_breach"` literal for Z201/Z204 -- this is the exact,
deliberate CLI-layer security-severity bridge _check.py's own
_finding_severity() docstring already cross-references ("Z201/Z204 ...
reach this severity via the credential-scanner bridge in
_map_credential_to_finding instead of this function"). Not a bug, not
covered by the new structural test (which scans RuleFinding(...) sites
only, matching the rules.py/incremental.py precedent).
"""

from __future__ import annotations

from pathlib import Path

from _helpers import make_mgr

from zenzic.core.codes import code_severity
from zenzic.core.scanner import _make_error_report, _make_timeout_report, scan_docs_references
from zenzic.models.config import ZenzicConfig


def test_z106_circular_link_severity_matches_codes_py(tmp_path: Path) -> None:
    """Z106 is codes.py-classified as note/info; must not surface as error."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("[go to b](b.md)\n", encoding="utf-8")
    (docs / "b.md").write_text("[go to a](a.md)\n", encoding="utf-8")

    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    reports, _ = scan_docs_references(docs, mgr, repo_root=tmp_path, config=config)

    z106 = [f for r in reports for f in r.rule_findings if f.rule_id == "Z106"]
    assert z106, "Fixture must trigger Z106 (circular link cycle) via scanner.py's RuleFinding path"
    assert code_severity("Z106") == "info"
    for f in z106:
        assert f.severity == "info", (
            f"Z106 RuleFinding severity is {f.severity!r}, expected 'info' "
            f"to match codes.py's CODE_DEFINITIONS['Z106']"
        )


def test_z902_timeout_report_severity_matches_codes_py(tmp_path: Path) -> None:
    """Z902 is codes.py-classified as warning; must not surface as error.

    _make_timeout_report() is documented as a standalone pure function
    specifically so it can be tested directly (see its own docstring) --
    exercised here exactly as intended, matching the second, independent
    live Z902 site this fix closes (the first was rules.py's, already
    fixed in V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP).
    """
    report = _make_timeout_report(Path("docs/slow.md"))

    assert len(report.rule_findings) == 1
    finding = report.rule_findings[0]
    assert finding.rule_id == "Z902"
    assert code_severity("Z902") == "warning"
    assert finding.severity == "warning", (
        f"Z902 RuleFinding severity is {finding.severity!r}, expected 'warning' "
        f"to match codes.py's CODE_DEFINITIONS['Z902']"
    )


def test_z901_error_report_severity_matches_codes_py(tmp_path: Path) -> None:
    """Regression guard: Z901 (already correct) stays correct post-refactor."""
    report = _make_error_report(Path("docs/broken.md"), ValueError("boom"))

    assert len(report.rule_findings) == 1
    finding = report.rule_findings[0]
    assert finding.rule_id == "Z901"
    assert code_severity("Z901") == "error"
    assert finding.severity == "error"
