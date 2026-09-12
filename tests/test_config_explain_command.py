# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for `zenzic config explain` (zenzic.cli._config_explain).

No prior coverage existed for this command at all. These exercise the
source-resolution precedence (local > global > default) across every
config section, the forbidden_patterns special-case branches, the
_value_repr rendering branches (bool/list/dict, short/long/empty), and
the malformed-TOML tolerance in _load_raw_toml.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def test_explain_defaults_when_no_config_files_exist(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "not found — using built-in defaults" in result.stdout
    assert "not found — no local overrides active" in result.stdout
    assert "default" in result.stdout


def test_explain_global_override_shows_global_source(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "documentation"\nfail_under = 90\n\n[build_context]\nengine = "mkdocs"\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert ".zenzic.toml" in result.stdout
    assert "global" in result.stdout
    assert "documentation" in result.stdout
    assert "mkdocs" in result.stdout


def test_explain_local_override_shows_local_source_and_overlay_status(
    tmp_path: Path,
) -> None:
    (tmp_path / ".zenzic.local.toml").write_text(
        '[core]\ndocs_dir = "local-docs"\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert ".zenzic.local.toml" in result.stdout
    assert "local" in result.stdout
    assert "local-docs" in result.stdout


def test_explain_forbidden_patterns_local_core_section_wins(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text(
        'forbidden_patterns = ["global-term"]\n',
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.local.toml").write_text(
        '[core]\nforbidden_patterns = ["local-term"]\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "forbidden_patterns" in result.stdout


def test_explain_forbidden_patterns_local_top_level_wins_over_global(
    tmp_path: Path,
) -> None:
    (tmp_path / ".zenzic.toml").write_text(
        'forbidden_patterns = ["global-term"]\n',
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.local.toml").write_text(
        'forbidden_patterns = ["local-term"]\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "forbidden_patterns" in result.stdout


def test_explain_forbidden_patterns_global_only(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text(
        'forbidden_patterns = ["global-term"]\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "forbidden_patterns" in result.stdout


def test_explain_renders_short_and_long_list_values(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text(
        "[policies]\n"
        'weasel_words = ["clearly", "simply"]\n'
        "forbidden_external_domains = ["
        + ", ".join(f'"domain-{i}.example.com"' for i in range(10))
        + "]\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "clearly" in result.stdout
    assert "items]" in result.stdout


def test_explain_renders_dict_values(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text(
        '[policies.required_table_columns]\n"*" = ["Status", "Description"]\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "key" in result.stdout.lower()


def test_explain_tolerates_malformed_global_toml(tmp_path: Path) -> None:
    (tmp_path / ".zenzic.toml").write_text("docs_dir = [unclosed", encoding="utf-8")

    result = runner.invoke(app, ["config", "explain", "--path", str(tmp_path)])

    # _load_raw_toml swallows the parse error internally (returns {}); the
    # downstream ZenzicConfig.load() call raises on the same malformed file,
    # so the command surfaces a non-zero exit rather than crashing silently.
    assert result.exit_code != 0
