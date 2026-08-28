# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic lab``'s process exit code must reflect scenario pass/fail.

Regression for: `lab <code>`/`lab all` printed a clear PASS/FAIL verdict per
scenario (via `_ActResult.met_expectation`) but never propagated it to the
process exit code — `lab` always exited 0, even when every single scenario
visibly failed its expectation. This defeated `lab all`'s use as an internal
regression gate (confirmed used as such in this session's own verification
evidence): a CI step running `zenzic lab all` would report success
regardless of what the printed table said.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from zenzic.cli._lab import _GALLERY, _ActResult
from zenzic.main import app


runner = CliRunner()


def _fake_result(code: str, *, met: bool) -> _ActResult:
    """Build an _ActResult whose met_expectation matches *met*, for any
    gallery scenario, without touching the real examples/ fixtures."""
    act = _GALLERY[code]
    if met:
        # expected_pass scenarios: errors == 0 satisfies met_expectation.
        # expected_breach scenarios: has_breach True satisfies it.
        # expected_incident scenarios: has_incident True satisfies it.
        # default (expected fail) scenarios: errors > 0 satisfies it.
        if act.expected_pass:
            errors, warnings, has_breach, has_incident = 0, 0, False, False
        elif act.expected_breach:
            errors, warnings, has_breach, has_incident = 0, 0, True, False
        elif act.expected_incident:
            errors, warnings, has_breach, has_incident = 0, 0, False, True
        else:
            errors, warnings, has_breach, has_incident = 1, 0, False, False
    else:
        # Force the opposite of whatever the scenario expects.
        if act.expected_pass:
            errors, warnings, has_breach, has_incident = 1, 0, False, False
        elif act.expected_breach:
            errors, warnings, has_breach, has_incident = 0, 0, False, False
        elif act.expected_incident:
            errors, warnings, has_breach, has_incident = 0, 0, False, False
        else:
            errors, warnings, has_breach, has_incident = 0, 0, False, False
    return _ActResult(
        act=act,
        errors=errors,
        warnings=warnings,
        has_breach=has_breach,
        elapsed=0.01,
        engine="standalone",
        docs_count=1,
        assets_count=0,
        has_incident=has_incident,
    )


def test_lab_single_scenario_exits_0_when_expectation_met() -> None:
    with patch("zenzic.cli._lab._run_act", return_value=_fake_result("z101", met=True)):
        result = runner.invoke(app, ["lab", "z101"])
    assert result.exit_code == 0, (
        f"lab must exit 0 when the scenario meets its expectation, got "
        f"{result.exit_code}.\nOutput:\n{result.stdout}"
    )


def test_lab_single_scenario_exits_nonzero_when_expectation_not_met() -> None:
    with patch("zenzic.cli._lab._run_act", return_value=_fake_result("z101", met=False)):
        result = runner.invoke(app, ["lab", "z101"])
    assert result.exit_code != 0, (
        f"lab must exit non-zero when the scenario does NOT meet its "
        f"expectation (regression gate must actually gate), got exit 0.\n"
        f"Output:\n{result.stdout}"
    )


def test_lab_all_exits_0_when_every_scenario_meets_expectation() -> None:
    def _fake_run_act(act, examples_root, show_all=False):  # noqa: ANN001, ARG001
        return _fake_result(act.code, met=True)

    with patch("zenzic.cli._lab._run_act", side_effect=_fake_run_act):
        result = runner.invoke(app, ["lab", "all"])
    assert result.exit_code == 0, (
        f"lab all must exit 0 when every scenario meets its expectation, "
        f"got {result.exit_code}.\nOutput:\n{result.stdout}"
    )


def test_z203_gallery_scenario_registered_and_runs_live() -> None:
    """Z203 (PATH_TRAVERSAL_FATAL) must have a real gallery entry and fixture.

    Regression for: Z201/Z202/Z204/Z205 (its Z2xx siblings) all had both an
    examples/z2NN-*/ fixture and a _GALLERY["z203"] registration; Z203 had
    neither (Mirror Law Target 8 gap). Unlike the other tests in this file,
    this one deliberately does NOT mock ``_run_act`` — it exercises the real
    bundled ``examples/z203-fatal-path-traversal`` fixture end-to-end so the
    fixture content and the classifier it's meant to demonstrate
    (``_classify_traversal_intent`` in ``zenzic.core.validator``) are both
    verified live, not just asserted from source.
    """
    assert "z203" in _GALLERY, "Z203 must be registered in _lab.py's _GALLERY"

    result = runner.invoke(app, ["lab", "z203"])
    assert result.exit_code == 0, (
        f"zenzic lab z203 must exit 0 (scenario met its expectation) against "
        f"the real bundled fixture, got {result.exit_code}.\nOutput:\n{result.stdout}"
    )
    assert "Z203" in result.stdout
    assert "/etc/" in result.stdout or "etc/passwd" in result.stdout


def test_lab_all_exits_nonzero_when_one_scenario_fails() -> None:
    call_count = 0

    def _fake_run_act(act, examples_root, show_all=False):  # noqa: ANN001, ARG001
        nonlocal call_count
        call_count += 1
        # Fail exactly the first scenario processed; pass the rest.
        return _fake_result(act.code, met=(call_count != 1))

    with patch("zenzic.cli._lab._run_act", side_effect=_fake_run_act):
        result = runner.invoke(app, ["lab", "all"])
    assert result.exit_code != 0, (
        f"lab all must exit non-zero when at least one scenario fails its "
        f"expectation, got exit 0.\nOutput:\n{result.stdout}"
    )
