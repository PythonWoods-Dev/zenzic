# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic import __version__
from zenzic.main import app


runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup_audit_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("---\ntitle: Audit Test\n---\n# Audit\n[test](index.md)\n")
    (tmp_path / ".zenzic.toml").write_text('[policies]\nrequired_frontmatter_keys = ["title"]\n')
    monkeypatch.chdir(tmp_path)


def test_zenzic_audit_text_output() -> None:
    result = runner.invoke(app, ["audit", "--no-external"])
    assert result.exit_code == 0
    output = result.stdout
    assert "# ZENZIC GOVERNANCE AUDIT REPORT" in output
    assert "Executive Summary" in output
    assert "Governance Policies" in output
    assert "Technical Debt Ledger" in output
    assert "Architectural State" in output


def test_zenzic_audit_json_output() -> None:
    result = runner.invoke(app, ["audit", "--format", "json", "--no-external"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)

    assert data["audit_version"] == __version__
    assert "executive_summary" in data
    assert data["executive_summary"]["status"] == "PASS"
    assert isinstance(data["executive_summary"]["score"], int)
    assert isinstance(data["executive_summary"]["total_files"], int)

    assert "governance_policies" in data
    assert isinstance(data["governance_policies"]["required_frontmatter_keys"], list)
    assert isinstance(data["governance_policies"]["forbidden_external_domains"], list)
    assert isinstance(data["governance_policies"]["suppression_cap"], int)

    assert "technical_debt_ledger" in data
    assert isinstance(data["technical_debt_ledger"]["inline_suppressions"], int)
    assert isinstance(data["technical_debt_ledger"]["per_file_ignores"], int)

    assert "architectural_state" in data
    assert isinstance(data["architectural_state"]["engine"], str)
    assert isinstance(data["architectural_state"]["adapter"], str)
    assert isinstance(data["architectural_state"]["custom_rules"], list)


def test_zenzic_audit_determinism() -> None:
    result1 = runner.invoke(app, ["audit", "--format", "json", "--no-external"])
    result2 = runner.invoke(app, ["audit", "--format", "json", "--no-external"])
    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert result1.stdout == result2.stdout
