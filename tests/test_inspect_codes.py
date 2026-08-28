# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for `zenzic inspect codes`'s penalty-column rendering."""

from __future__ import annotations

from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def test_z901_renders_as_halt_not_plain_zero() -> None:
    """Z901 (RULE_ENGINE_ERROR) must render HALT, not 0.0.

    Z901 is severity="error" + penalty=0.0 — 0.0 because it never reaches
    DQS scoring, not because it's harmless: it unconditionally fails the
    pipeline via the normal error path (no --strict needed), the exact same
    practical outcome as a warning+0.0 HALT code (Z504, Z902) — just reached
    via severity="error" instead of the governance-gate mechanism warnings
    need. docs/reference/finding-codes.md's HALT examples table already
    listed Z901 as a HALT example; this locks the CLI display to match it.
    """
    result = runner.invoke(app, ["inspect", "codes"])
    assert result.exit_code == 0, result.output

    lines = [line for line in result.stdout.splitlines() if "Z901" in line]
    assert lines, f"Z901 row not found in output:\n{result.stdout}"
    assert "HALT" in lines[0], f"Z901 row must show HALT, got:\n{lines[0]}"
    assert "0.0" not in lines[0], f"Z901 row must not show plain 0.0, got:\n{lines[0]}"


def test_z902_still_renders_as_halt() -> None:
    """Regression guard: Z902 (warning+0.0) must remain HALT, unaffected by the Z901 fix."""
    result = runner.invoke(app, ["inspect", "codes"])
    assert result.exit_code == 0, result.output

    lines = [line for line in result.stdout.splitlines() if "Z902" in line]
    assert lines, f"Z902 row not found in output:\n{result.stdout}"
    assert "HALT" in lines[0], f"Z902 row must show HALT, got:\n{lines[0]}"


def test_z906_still_renders_as_plain_zero() -> None:
    """Regression guard: Z906 (note+0.0, genuinely informational) must stay 0.0, not HALT."""
    result = runner.invoke(app, ["inspect", "codes"])
    assert result.exit_code == 0, result.output

    lines = [line for line in result.stdout.splitlines() if "Z906" in line]
    assert lines, f"Z906 row not found in output:\n{result.stdout}"
    assert "HALT" not in lines[0], f"Z906 row must not show HALT, got:\n{lines[0]}"
