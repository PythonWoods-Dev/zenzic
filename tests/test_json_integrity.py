# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Schema integrity tests for Zenzic JSON outputs (Phase 66)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def _schema_validator() -> Draft202012Validator:
    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "zenzic-output.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _write_contract_sandbox(
    tmp_path: Path,
    *,
    inline_count: int = 0,
    cap: int = 30,
    fail_hard: bool = True,
) -> Path:
    """Create a minimal standalone docs project for JSON contract validation."""
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent(
            """\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"

            [governance]
            suppression_cap = {cap}
            suppression_cap_fail_hard = {fail_hard}
            """
        ).format(cap=cap, fail_hard=str(fail_hard).lower()),
        encoding="utf-8",
    )

    suppressions = "\n".join(
        f"Allowed historical note {i}. <!-- zenzic:ignore: Z601 - test -->"
        for i in range(1, inline_count + 1)
    )
    index = tmp_path / "docs" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "# Contract fixture\n\n"
        "This page exists only to validate machine-readable JSON contracts and includes a long "
        "neutral narrative so quality gates remain deterministic. The text confirms that this "
        "document is synthetic, that no external references are expected, and that all assertions "
        "in this suite target output shape rather than content semantics. The wording is ordinary "
        "and intentionally avoids unfinished-work markers that could be interpreted as policy "
        "violations by static checks.\n\n"
        f"{suppressions}\n",
        encoding="utf-8",
    )
    return tmp_path


def test_check_all_json_matches_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """check all --format json must validate against the official schema."""
    _write_contract_sandbox(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["check", "all", "--format", "json"])

    assert result.exit_code == 0, f"Unexpected exit {result.exit_code}:\n{result.stdout}"
    payload = json.loads(result.stdout)
    _schema_validator().validate(payload)


def test_score_json_matches_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """score --format json must validate against the official schema."""
    _write_contract_sandbox(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["score", "--format", "json"])

    assert result.exit_code == 0, f"Unexpected exit {result.exit_code}:\n{result.stdout}"
    payload = json.loads(result.stdout)
    _schema_validator().validate(payload)


def test_cap_exceeded_json_matches_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CAP fail-hard JSON must validate against the same schema contract."""
    _write_contract_sandbox(tmp_path, inline_count=31, cap=30, fail_hard=True)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["check", "all", "--format", "json"])

    assert result.exit_code == 1, f"Unexpected exit {result.exit_code}:\n{result.stdout}"
    payload = json.loads(result.stdout)
    assert payload["error"] == "SUPPRESSION_CAP_EXCEEDED"
    _schema_validator().validate(payload)


def test_check_all_json_exposes_security_breach_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check all --format json must expose a machine-readable severity marker
    for security_breach findings, not just plain link-error strings.

    Regression for: the legacy checkAllReport JSON payload (links/orphans/
    snippets/unused_assets/nav_contract/references — all plain strings) had
    no field a JSON consumer could use to programmatically detect a Z2xx
    security breach. A consumer had to either parse link-error message text
    or rely solely on the process exit code, even though the CLI's process
    exit code IS already correct (2) for this case — this test targets the
    JSON payload's own self-description, independent of the exit code.
    """
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "standalone"\n',
        encoding="utf-8",
    )
    index = tmp_path / "docs" / "index.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "# Interactive Widget\n\n"
        "This page embeds a widget link using a scheme that must never be "
        "permitted in published documentation, regardless of context.\n\n"
        '<a href="javascript:alert(document.cookie)">Click for details</a>\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["check", "all", "--format", "json"])

    assert result.exit_code == 2, f"Unexpected exit {result.exit_code}:\n{result.stdout}"
    payload = json.loads(result.stdout)
    assert payload.get("security_breaches", 0) > 0, (
        f"Expected a positive security_breaches count in the JSON payload for "
        f"a Z205 finding, got: {payload}"
    )
    _schema_validator().validate(payload)
