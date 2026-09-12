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


def test_z110_renders_as_fatal_not_plain_zero() -> None:
    """Z110 (CONFIG_SYNTAX_ERROR) must render FATAL, not 0.0.

    Z110 is severity="error" + penalty=0.0, same shape as Z901 -- but unlike
    Z901 (a within-scan rule-engine error), Z110/Z111 are genuinely
    config-abort codes, the same class as Z000/Z001, just numbered in the
    "Z1xx" range for historical reasons. _inspect.py's FATAL branch only
    string-matches a Z0/Z2 prefix and misses them. This locks the display
    to FATAL, matching Z000/Z001's existing display and Z110/Z111's
    membership in FROZEN_CODES alongside them.
    """
    result = runner.invoke(app, ["inspect", "codes"])
    assert result.exit_code == 0, result.output

    lines = [line for line in result.stdout.splitlines() if "Z110" in line]
    assert lines, f"Z110 row not found in output:\n{result.stdout}"
    assert "FATAL" in lines[0], f"Z110 row must show FATAL, got:\n{lines[0]}"
    assert "0.0" not in lines[0], f"Z110 row must not show plain 0.0, got:\n{lines[0]}"


def test_z111_renders_as_fatal_not_plain_zero() -> None:
    """Z111 (CONFIG_SCHEMA_ERROR) must render FATAL, not 0.0. See test_z110 for reasoning."""
    result = runner.invoke(app, ["inspect", "codes"])
    assert result.exit_code == 0, result.output

    lines = [line for line in result.stdout.splitlines() if "Z111" in line]
    assert lines, f"Z111 row not found in output:\n{result.stdout}"
    assert "FATAL" in lines[0], f"Z111 row must show FATAL, got:\n{lines[0]}"
    assert "0.0" not in lines[0], f"Z111 row must not show plain 0.0, got:\n{lines[0]}"


def test_fixable_column_present_and_correct() -> None:
    """A Fixable column, derived from the same CODE_DEFINITIONS zenzic explain reads,
    must be present and show Yes for a fixable code, No for a non-fixable one."""
    result = runner.invoke(app, ["inspect", "codes"])
    assert result.exit_code == 0, result.output
    assert "Fixable" in result.stdout, f"'Fixable' column header not found:\n{result.stdout}"

    z515_lines = [line for line in result.stdout.splitlines() if "Z515" in line]
    assert z515_lines, f"Z515 row not found:\n{result.stdout}"
    assert "Yes" in z515_lines[0], f"Z515 (fixable=True) must show Yes, got:\n{z515_lines[0]}"

    z101_lines = [line for line in result.stdout.splitlines() if "Z101" in line]
    assert z101_lines, f"Z101 row not found:\n{result.stdout}"
    assert "No" in z101_lines[0], f"Z101 (fixable=False) must show No, got:\n{z101_lines[0]}"
