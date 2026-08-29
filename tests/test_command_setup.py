# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the shared ``setup_command()`` CLI preamble factory.

``setup_command()`` was previously dead code (V031_CODE_BACKLOG_BATCH1's
finding) -- these tests establish a baseline before wiring it into the real
``check`` sub-commands, and cover the extra parameters (`config_file`,
`engine_override`, `offline`, `exclude_url`) added specifically so that
wiring is behavior-identical to what each sub-command's own inline preamble
did before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.cli._command_setup import setup_command


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / ".zenzic.toml").touch()
    (repo / "docs" / "index.md").write_text("# Hello\n")
    return repo


def test_directory_mode_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    config, repo_root, docs_root, exclusion_mgr, single_file, loaded_from_file = setup_command()

    assert repo_root == repo.resolve()
    assert docs_root == (repo / "docs").resolve()
    assert single_file is None
    assert loaded_from_file is True
    assert exclusion_mgr is not None


def test_single_file_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    _, repo_root, docs_root, _, single_file, _ = setup_command("docs/index.md")

    assert single_file == (repo / "docs" / "index.md").resolve()
    assert docs_root == (repo / "docs").resolve()
    assert repo_root == repo.resolve()


def test_no_config_file_reports_loaded_from_file_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "bare"
    (repo / "docs").mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    _, _, _, _, _, loaded_from_file = setup_command()

    assert loaded_from_file is False


def test_config_file_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    override = tmp_path / "custom.toml"
    override.write_text('docs_dir = "docs"\n')

    config, *_ = setup_command(config_file=override)

    assert config is not None


def test_engine_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    (repo / ".zenzic.toml").write_text('[build_context]\nengine = "mkdocs"\n')
    monkeypatch.chdir(repo)

    config, *_ = setup_command(engine_override="standalone")

    assert config.build_context.engine == "standalone"


def test_offline_flag_sets_offline_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    config, *_ = setup_command(offline=True)

    assert config.build_context.offline_mode is True


def test_offline_flag_false_leaves_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    config, *_ = setup_command(offline=False)

    assert config.build_context.offline_mode is False


def test_exclude_url_merges_into_excluded_external_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    config, *_ = setup_command(exclude_url=["https://example.com/"])

    assert "https://example.com/" in config.excluded_external_urls


def test_exclude_url_empty_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    config, *_ = setup_command(exclude_url=[])

    assert config.excluded_external_urls == []


def test_extra_exclude_dirs_still_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    config, *_ = setup_command(extra_exclude_dirs=["vendor"])

    assert "vendor" in config.excluded_dirs
