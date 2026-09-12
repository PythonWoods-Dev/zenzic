# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the zenzic explain command (Phase 26).

Verifies that rule metadata, scoring tier, and config genealogy are
displayed correctly for known and unknown rule codes.
"""

from __future__ import annotations

from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


# ─── Basic invocation ─────────────────────────────────────────────────────────


def test_explain_z101_shows_rule_name() -> None:
    """Z101 explain output must include the rule name LINK_BROKEN."""
    result = runner.invoke(app, ["explain", "Z101"])
    assert result.exit_code == 0
    assert "LINK_BROKEN" in result.stdout


def test_explain_z601_shows_governance_tier() -> None:
    """Z601 BRAND_OBSOLESCENCE must report 'brand' scoring tier."""
    result = runner.invoke(app, ["explain", "Z601"])
    assert result.exit_code == 0
    assert "brand" in result.stdout


def test_explain_z201_shows_security_gate() -> None:
    """Z201 CREDENTIAL_SECRET must show SECURITY GATE — score collapses to 0."""
    result = runner.invoke(app, ["explain", "Z201"])
    assert result.exit_code == 0
    assert "SECURITY GATE" in result.stdout


def test_explain_z204_shows_security_gate() -> None:
    """Z204 FORBIDDEN_TERM (Privacy Gate) must show SECURITY GATE."""
    result = runner.invoke(app, ["explain", "Z204"])
    assert result.exit_code == 0
    assert "SECURITY GATE" in result.stdout


def test_explain_z204_shows_forbidden_patterns_genealogy() -> None:
    """Z204 explain output must show the forbidden_patterns genealogy row."""
    result = runner.invoke(app, ["explain", "Z204"])
    assert result.exit_code == 0
    assert "forbidden_patterns list" in result.stdout


def test_explain_case_insensitive() -> None:
    """Rule ID argument must be case-insensitive (z101 == Z101)."""
    result_upper = runner.invoke(app, ["explain", "Z101"])
    result_lower = runner.invoke(app, ["explain", "z101"])
    assert result_upper.exit_code == 0
    assert result_lower.exit_code == 0
    assert "LINK_BROKEN" in result_lower.stdout


def test_explain_shows_config_genealogy_section() -> None:
    """Output must contain a Config Genealogy section."""
    result = runner.invoke(app, ["explain", "Z101"])
    assert result.exit_code == 0
    assert "Config Genealogy" in result.stdout


def test_explain_shows_default_layer() -> None:
    """Config genealogy must always show the Default layer."""
    result = runner.invoke(app, ["explain", "Z601"])
    assert result.exit_code == 0
    assert "Default" in result.stdout


# ─── Unknown rule ─────────────────────────────────────────────────────────────


def test_explain_unknown_rule_exits_zero_with_unknown_label() -> None:
    """Unknown rule codes are handled gracefully — output shows UNKNOWN name."""
    result = runner.invoke(app, ["explain", "Z999"])
    assert result.exit_code == 0
    assert "UNKNOWN" in result.stdout


# ─── Penalty display ──────────────────────────────────────────────────────────


def test_explain_z503_shows_penalty() -> None:
    """Z503 SNIPPET_ERROR has a 10 pt/occurrence penalty — must appear in output."""
    result = runner.invoke(app, ["explain", "Z503"])
    assert result.exit_code == 0
    assert "10.0 pt" in result.stdout or "10 pt" in result.stdout


def test_explain_z402_shows_navigation_tier() -> None:
    """Z402 ORPHAN_PAGE belongs to the navigation tier — must appear."""
    result = runner.invoke(app, ["explain", "Z402"])
    assert result.exit_code == 0
    assert "navigation" in result.stdout


def test_explain_z502_shows_placeholder_max_words_genealogy() -> None:
    """Z502 SHORT_CONTENT explain output must show its real config genealogy
    row (placeholder_max_words), not silently omit it.

    _RULE_CONFIG_MAP previously looked up a non-existent config attribute
    (short_content_threshold) via getattr(config, part, None), which always
    returned None and silently skipped the row -- see
    V031_Z501_Z506_REMEDIATION_AND_EXPLAIN_BUG.
    """
    result = runner.invoke(app, ["explain", "Z502"])
    assert result.exit_code == 0
    assert "placeholder_max_words" in result.stdout
