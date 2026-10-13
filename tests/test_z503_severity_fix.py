# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for V031_SEVERITY_HARDCODE_ARCHITECTURAL_REMEDIATION.

Before this fix, ``Z503`` (SNIPPET_ERROR) was classified as ``"warning"`` in
``src/zenzic/core/codes.py``'s ``CODE_DEFINITIONS`` (the declared single
source of truth), but ``src/zenzic/cli/_check.py`` hardcoded
``severity="error"`` at two call sites (lines 541, 1411) instead of calling
``_finding_severity("Z503")``. Same bug shape as Z301 and Z406, found during
the systemic sweep those two fixes prompted.

Consequence: a Z503 finding always hard-failed a plain ``zenzic check`` run
with no ``--strict`` flag, contradicting the Tier-0 Exit Code Contract.
"""

from __future__ import annotations

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


def test_z503_is_warning_not_error() -> None:
    """A Z503 finding must be warning-level, matching codes.py's
    CodeDefinition("warning", 10.0, "content") -- not hardcoded as an error."""
    findings, errors, warnings = _run("z503")

    z503_findings = [f for f in findings if f.code == "Z503"]
    assert z503_findings, "Expected at least one Z503 finding in the gallery fixture"
    assert all(f.severity == "warning" for f in z503_findings), (
        f"Z503 findings must be severity='warning' per codes.py, got: "
        f"{[f.severity for f in z503_findings]}"
    )


def test_z503_does_not_hard_fail_without_strict() -> None:
    """A lone Z503 finding must not cause Exit 1 unless --strict is passed."""
    from typer.testing import CliRunner

    from zenzic.main import app

    act = _GALLERY["z503"]
    example_dir = _examples_root() / act.example_dir

    runner = CliRunner()
    result = runner.invoke(app, ["check", "all", "--no-header", "--", str(example_dir)])

    assert result.exit_code == 0, (
        f"A warning-level Z503 finding must not hard-fail a non---strict run. "
        f"stdout:\n{result.stdout}"
    )
