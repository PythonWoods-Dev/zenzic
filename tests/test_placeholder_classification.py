# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the deterministic placeholder-credential classification (Z206 reframe).

Not a confidence score — a fixed, rule-based boolean classification, staying
inside Tier-0 Invariant #1 (Determinism & Pure Functions). Scope: Z201/Z204
only, the two codes SecurityFinding backs.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zenzic.core.credentials import (
    SecurityFinding,
    _is_likely_placeholder,
    scan_line_for_secrets,
    scan_url_for_secrets,
)
from zenzic.core.reporter import Finding
from zenzic.core.scanner import _map_credential_to_finding
from zenzic.main import app


runner = CliRunner()


# ── _is_likely_placeholder() — pure classifier ─────────────────────────────


def test_placeholder_marker_detected_case_insensitive() -> None:
    assert _is_likely_placeholder("sk-EXAMPLEXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    assert _is_likely_placeholder("AKIAexample1234567890")
    assert _is_likely_placeholder("ghp_PLACEHOLDER1234567890")
    assert _is_likely_placeholder("sk-live-YOUR_API_KEY_HERE")


def test_aws_documented_example_key_detected() -> None:
    """AWS's own publicly-documented example access key ID (from their docs)."""
    assert _is_likely_placeholder("AKIAIOSFODNN7EXAMPLE")


def test_repeated_character_run_detected() -> None:
    """A run of 8+ identical characters is a common dummy-token convention."""
    assert _is_likely_placeholder("AKIAXXXXXXXXXXXXXXXX")
    assert _is_likely_placeholder("sk-00000000000000000000000000000000000000000000")


def test_genuine_looking_secret_not_flagged() -> None:
    """A realistic, high-entropy-looking token must not be misclassified."""
    assert not _is_likely_placeholder("AKIAJ7ARBNTPDXVBQZ4A")
    assert not _is_likely_placeholder("sk-proj-h3kD9fL2mQ8xR1vT6yN4wA7bC5eG0jK3pS9uV2z")


# ── SecurityFinding construction sites set the field correctly ─────────────


def test_scan_url_for_secrets_flags_placeholder() -> None:
    findings = list(
        scan_url_for_secrets(
            "https://example.com?key=AKIAIOSFODNN7EXAMPLE", Path("docs/x.md"), 1
        )
    )
    assert findings
    assert findings[0].is_likely_placeholder is True


def test_scan_url_for_secrets_does_not_flag_real_looking_key() -> None:
    findings = list(
        scan_url_for_secrets(
            "https://example.com?key=AKIAJ7ARBNTPDXVBQZ4A", Path("docs/x.md"), 1
        )
    )
    assert findings
    assert findings[0].is_likely_placeholder is False


def test_scan_line_for_secrets_flags_placeholder() -> None:
    findings = list(
        scan_line_for_secrets("api_key: AKIAIOSFODNN7EXAMPLE", Path("docs/x.md"), 1)
    )
    assert findings
    assert findings[0].is_likely_placeholder is True


def test_security_finding_default_is_false() -> None:
    sf = SecurityFinding(file_path=Path("x.md"), line_no=1, secret_type="t", url="u")
    assert sf.is_likely_placeholder is False


# ── _map_credential_to_finding threads the field through ───────────────────


def test_map_credential_to_finding_threads_placeholder_flag_z201() -> None:
    sf = SecurityFinding(
        file_path=Path("/repo/docs/x.md"),
        line_no=3,
        secret_type="aws-access-key",
        url="AKIAIOSFODNN7EXAMPLE",
        match_text="AKIAIOSFODNN7EXAMPLE",
        is_likely_placeholder=True,
    )
    finding = _map_credential_to_finding(sf, Path("/repo"))
    assert finding.code == "Z201"
    assert finding.is_likely_placeholder is True


def test_map_credential_to_finding_threads_placeholder_flag_z204() -> None:
    sf = SecurityFinding(
        file_path=Path("/repo/docs/x.md"),
        line_no=3,
        secret_type="FORBIDDEN_TERM",
        url="line text",
        match_text="ExampleCorp",
        is_likely_placeholder=True,
    )
    finding = _map_credential_to_finding(sf, Path("/repo"))
    assert finding.code == "Z204"
    assert finding.is_likely_placeholder is True


def test_finding_default_is_false() -> None:
    f = Finding(rel_path="x.md", line_no=1, code="Z201", severity="security_breach", message="m")
    assert f.is_likely_placeholder is False


# ── CLI text display ────────────────────────────────────────────────────────


def test_cli_shows_likely_placeholder_tag(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Home\n\nExample key: AKIAIOSFODNN7EXAMPLE\n")

    result = runner.invoke(app, ["check", "all", str(tmp_path), "--no-header"])
    assert result.exit_code == 2, result.output
    assert "LIKELY PLACEHOLDER" in result.output


def test_cli_omits_tag_for_real_looking_secret(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Home\n\nLeaked key: AKIAJ7ARBNTPDXVBQZ4A\n")

    result = runner.invoke(app, ["check", "all", str(tmp_path), "--no-header"])
    assert result.exit_code == 2, result.output
    assert "LIKELY PLACEHOLDER" not in result.output


# ── SARIF output ─────────────────────────────────────────────────────────────


def test_sarif_output_includes_placeholder_property(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Home\n\nExample key: AKIAIOSFODNN7EXAMPLE\n")

    result = runner.invoke(app, ["check", "all", str(tmp_path), "--format", "sarif"])
    payload = json.loads(result.stdout)
    results = payload["runs"][0]["results"]
    z201_results = [r for r in results if r["ruleId"] == "Z201"]
    assert z201_results
    # NOTE: Z201 is known to double-emit today via two independent construction
    # paths (_map_credential_to_finding vs. the RuleFinding injection in
    # scanner.py's _scan_single_file) -- a real, pre-existing, separately
    # tracked bug (confirmed present before this change too), not something
    # this test should mask by asserting a single result. Only the
    # _map_credential_to_finding path carries the new field; assert at least
    # one result has it, not that every result does.
    assert any(r.get("properties", {}).get("is_likely_placeholder") is True for r in z201_results)
