# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for V031_Z406_SEVERITY_FIX_AND_SYSTEMIC_SWEEP.

Before this fix, ``Z406`` (NAV_CONTRACT) was classified as ``"warning"`` in
``src/zenzic/core/codes.py``'s ``CODE_DEFINITIONS`` (the declared single
source of truth), but ``src/zenzic/cli/_check.py`` hardcoded
``severity="error"`` when constructing the ``Finding`` for each
``results.nav_contract_errors`` entry, instead of calling
``_finding_severity("Z406")`` -- the exact SSoT-derivation helper every
sibling code in that same function correctly uses. This is the same bug
shape already found and fixed for Z301
(V031_Z301_SEVERITY_FIX_AND_BACKLOG_SEQUENCING).

Consequence: a Z406 finding always hard-failed a plain ``zenzic check`` run
with no ``--strict`` flag, contradicting the Tier-0 Exit Code Contract
("Exit 1: Quality findings -- Errors, or Warnings under ``--strict``").
"""

from __future__ import annotations

from pathlib import Path

from zenzic.cli._check import _collect_all_results, _to_findings
from zenzic.cli._lab import _GALLERY, _examples_root
from zenzic.models.config import ZenzicConfig


def _run(code: str) -> tuple[list, int, int]:  # type: ignore[type-arg]
    """Same helper pattern as tests/test_gallery_phase2bc.py's _run()."""
    act = _GALLERY[code]
    example_dir = _examples_root() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    docs_root = (example_dir / config.docs_dir).resolve()
    from _helpers import make_mgr

    mgr = make_mgr(config, repo_root=example_dir, docs_root=docs_root)
    results = _collect_all_results(example_dir, docs_root, config, mgr, strict=False)
    findings = _to_findings(results, docs_root, repo_root=example_dir)
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    return findings, errors, warnings


def test_z406_is_warning_not_error() -> None:
    """A Z406 finding must be warning-level, matching codes.py's
    CodeDefinition("warning", 2.0, "brand") -- not hardcoded as an error."""
    findings, errors, warnings = _run("z406")

    z406_findings = [f for f in findings if f.code == "Z406"]
    assert z406_findings, "Expected at least one Z406 finding in the gallery fixture"
    assert all(f.severity == "warning" for f in z406_findings), (
        f"Z406 findings must be severity='warning' per codes.py, got: "
        f"{[f.severity for f in z406_findings]}"
    )
    assert errors == 0, f"Z406 alone must not produce any error-level findings, got {errors}"
    assert warnings == 1, f"Expected exactly one Z406 warning, got {warnings}"


def test_z406_does_not_hard_fail_without_strict(tmp_path: Path) -> None:
    """A lone Z406 finding must not cause Exit 1 unless --strict is passed."""
    from typer.testing import CliRunner

    from zenzic.main import app

    act = _GALLERY["z406"]
    example_dir = _examples_root() / act.example_dir

    runner = CliRunner()
    result = runner.invoke(app, ["check", "all", "--no-header", "--", str(example_dir)])

    assert result.exit_code == 0, (
        f"A warning-level Z406 finding must not hard-fail a non---strict run. "
        f"stdout:\n{result.stdout}"
    )
