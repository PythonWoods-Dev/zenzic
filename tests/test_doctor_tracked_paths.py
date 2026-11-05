# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic doctor`` reads versioned content: a configured path git does not track is reported.

A check that passes for whoever holds a file locally and cannot run in a fresh clone or in CI is worse than no check.
The rule names no folder: the same configured path is judged on one clone that holds it untracked, on a fresh clone
that does not have it, and outside any repository, where there is nothing to compare it with. Loading the
configuration never needs git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app
from zenzic.models.config import DoctorConfig


VAULT = ".private/adr"
runner = CliRunner()


def _git(root: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603  # Fixed test arguments
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
    )


def _configured(root: Path, **doctor: str) -> None:
    lines = "".join(f'{key} = "{value}"\n' for key, value in doctor.items())
    (root / ".zenzic.toml").write_text(f"[doctor]\n{lines}", encoding="utf-8")


def _vault(root: Path, where: str = VAULT) -> None:
    vault = root / where
    vault.mkdir(parents=True)
    (vault / "adr-001-example.md").write_text("# ADR-001\n", encoding="utf-8")


def _doctor(root: Path) -> tuple[int, dict[str, list[dict[str, str]]]]:
    result = runner.invoke(app, ["doctor", str(root), "--format", "json"])
    return result.exit_code, json.loads(result.stdout)["checks"]


@pytest.fixture
def maintainer(tmp_path: Path) -> Path:
    """A clone whose vault exists and is excluded by the clone's own, unversioned exclude file."""
    root = tmp_path / "maintainer"
    root.mkdir()
    _git(root, "init", "-q")
    _configured(root, adr_vault_path=VAULT)
    _vault(root)
    (root / ".git/info/exclude").write_text(".private/\n", encoding="utf-8")
    _git(root, "add", ".zenzic.toml")
    _git(root, "commit", "-q", "-m", "first")
    return root


def test_the_clone_that_holds_the_path_untracked_is_told(maintainer: Path) -> None:
    code, checks = _doctor(maintainer)
    assert code == 1
    assert [f["check"] for f in checks["tracked-paths"]] == ["tracked-paths"]
    assert VAULT in checks["tracked-paths"][0]["message"]
    assert "not tracked" in checks["tracked-paths"][0]["message"]


def test_a_fresh_clone_does_not_have_the_path_and_is_told(maintainer: Path, tmp_path: Path) -> None:
    fresh = tmp_path / "fresh"
    _git(tmp_path, "clone", "-q", str(maintainer), str(fresh))
    assert not (fresh / VAULT).exists()
    code, checks = _doctor(fresh)
    assert code == 1
    assert "not found" in checks["adr-citations"][0]["message"]
    assert VAULT in checks["adr-citations"][0]["message"], (
        "the configured path, not a default put in its place"
    )


def test_outside_a_repository_there_is_nothing_to_compare_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = tmp_path / "plain"
    root.mkdir()
    _configured(root, adr_vault_path=VAULT)
    _vault(root)
    code, checks = _doctor(root)
    assert code == 0
    assert checks["tracked-paths"] == []


def test_without_git_on_the_machine_the_check_does_not_run(
    maintainer: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    code, checks = _doctor(maintainer)
    assert code == 0
    assert checks["tracked-paths"] == []


def test_a_tracked_vault_is_clean(maintainer: Path) -> None:
    (maintainer / ".git/info/exclude").write_text("", encoding="utf-8")
    _git(maintainer, "add", VAULT)
    code, checks = _doctor(maintainer)
    assert code == 0
    assert checks["tracked-paths"] == []


def test_a_redirects_file_git_does_not_track_is_told(maintainer: Path) -> None:
    _configured(maintainer, adr_vault_path=VAULT, redirects_path=".private/_redirects")
    (maintainer / ".private/_redirects").write_text("/a /b 301\n", encoding="utf-8")
    _, checks = _doctor(maintainer)
    assert any(".private/_redirects" in f["message"] for f in checks["tracked-paths"])


def test_loading_the_configuration_needs_no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the configuration must load without running anything")

    monkeypatch.setattr(subprocess, "run", refuse)
    assert DoctorConfig(adr_vault_path=Path(VAULT)).adr_vault_path == Path(VAULT)
