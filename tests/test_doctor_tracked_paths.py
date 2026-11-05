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
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from zenzic.core.doctor import check_tracked_paths
from zenzic.main import app
from zenzic.models.config import DoctorConfig, load_config_with_diagnostics


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
    (root / ".git/info").mkdir(exist_ok=True)
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
    _git(maintainer, "commit", "-q", "-m", "the vault")
    code, checks = _doctor(maintainer)
    assert code == 0
    assert checks["tracked-paths"] == []


def test_a_redirects_file_git_does_not_track_is_told(maintainer: Path) -> None:
    _configured(maintainer, adr_vault_path=VAULT, redirects_path=".private/_redirects")
    (maintainer / ".private/_redirects").write_text("/a /b 301\n", encoding="utf-8")
    _, checks = _doctor(maintainer)
    assert any(".private/_redirects" in f["message"] for f in checks["tracked-paths"])


def test_loading_the_configuration_needs_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the configuration must load without running anything")

    _configured(tmp_path, adr_vault_path=VAULT)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    config, _ = load_config_with_diagnostics(tmp_path)
    assert config is not None
    assert config.doctor.adr_vault_path == Path(VAULT)


def test_a_file_name_that_is_not_utf8_does_not_stop_the_doctor(maintainer: Path) -> None:
    """Git gives names as bytes: the check must not depend on the locale's encoding, nor fall over on a name."""
    name = maintainer.as_posix().encode() + b"/caf\xe9.md"
    with open(name, "w", encoding="utf-8") as fh:
        fh.write("x\n")
    subprocess.run(  # noqa: S603  # Fixed test arguments
        [b"git", b"add", b"caf\xe9.md"],  # noqa: S607
        cwd=maintainer,
        check=True,
    )
    _git(maintainer, "commit", "-q", "-m", "the name")
    code, checks = _doctor(maintainer)
    assert code == 1
    assert [f["check"] for f in checks["tracked-paths"]] == ["tracked-paths"]


def test_a_git_that_cannot_answer_is_told_and_not_taken_for_no_repository(tmp_path: Path) -> None:
    """Git refuses for other reasons than «no repository» (a checkout of another user in a CI container): silence
    there would pass the very case the check exists for."""
    root = tmp_path / "broken"
    root.mkdir()
    (root / ".git").write_text("not a gitfile\n", encoding="utf-8")
    _configured(root, adr_vault_path=VAULT)
    _vault(root)
    code, checks = _doctor(root)
    assert code == 1
    assert "git could not list" in checks["tracked-paths"][0]["message"]


def test_a_vault_in_a_submodule_is_tracked(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    _git(library, "init", "-q")
    _vault(library, "adr")
    _git(library, "add", "adr")
    _git(library, "commit", "-q", "-m", "first")
    root = tmp_path / "root"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "lib")
    _git(root, "commit", "-q", "-m", "the submodule")
    _configured(root, adr_vault_path="lib/adr")
    _, checks = _doctor(root)
    assert checks["tracked-paths"] == []


def test_a_vault_with_one_file_tracked_and_a_record_not_is_told(maintainer: Path) -> None:
    """The holder would read a record no clone has: one tracked file must not clear the rest."""
    (maintainer / ".git/info/exclude").write_text("adr-*.md\n", encoding="utf-8")
    (maintainer / VAULT / "README.md").write_text("# The vault\n", encoding="utf-8")
    _git(maintainer, "add", VAULT)
    _git(maintainer, "commit", "-q", "-m", "one file")
    code, checks = _doctor(maintainer)
    assert code == 1
    assert "adr-001-example.md" in checks["tracked-paths"][0]["message"]


def test_a_vault_staged_and_not_committed_is_told(maintainer: Path) -> None:
    """A clone gets the last commit, never the index."""
    (maintainer / ".git/info/exclude").write_text("", encoding="utf-8")
    _git(maintainer, "add", VAULT)
    code, checks = _doctor(maintainer)
    assert code == 1
    assert VAULT in checks["tracked-paths"][0]["message"]


def test_a_repository_without_a_commit_tracks_nothing(tmp_path: Path) -> None:
    root = tmp_path / "new"
    root.mkdir()
    _git(root, "init", "-q")
    _configured(root, adr_vault_path=VAULT)
    _vault(root)
    code, checks = _doctor(root)
    assert code == 1
    assert "not tracked" in checks["tracked-paths"][0]["message"]


def test_a_tracked_link_to_an_untracked_vault_is_told(maintainer: Path) -> None:
    (maintainer / "vault").symlink_to(VAULT, target_is_directory=True)
    _configured(maintainer, adr_vault_path="vault")
    _git(maintainer, "add", "vault", ".zenzic.toml")
    _git(maintainer, "commit", "-q", "-m", "the link")
    code, checks = _doctor(maintainer)
    assert code == 1
    assert "vault" in checks["tracked-paths"][0]["message"]


def test_a_redirects_link_out_of_the_repository_is_not_read(
    maintainer: Path, tmp_path: Path
) -> None:
    """A branch's configuration must not print what lies outside the repository into the CI log."""
    secret = tmp_path / "secret"
    secret.write_text("CANARY-VALUE one two three four\n", encoding="utf-8")
    (maintainer / "r").symlink_to(secret)
    _configured(maintainer, adr_vault_path=VAULT, redirects_path="r")
    _git(maintainer, "add", "r", ".zenzic.toml")
    _git(maintainer, "commit", "-q", "-m", "the link")
    result = runner.invoke(app, ["doctor", str(maintainer), "--format", "json"])
    assert "CANARY-VALUE" not in result.stdout
    assert result.exit_code == 1


def test_a_redirects_link_out_is_not_read_without_git_either(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    outside = tmp_path / "secret"
    outside.write_text("CANARY-VALUE one two three four\n", encoding="utf-8")
    root = tmp_path / "plain"
    root.mkdir()
    (root / "r").symlink_to(outside)
    _configured(root, redirects_path="r")
    result = runner.invoke(app, ["doctor", str(root), "--format", "json"])
    assert "CANARY-VALUE" not in result.stdout


def test_an_untracked_redirects_file_is_told_and_not_read(maintainer: Path) -> None:
    (maintainer / ".private/_redirects").write_text(
        "CANARY-VALUE one two three four\n", encoding="utf-8"
    )
    _configured(maintainer, adr_vault_path=VAULT, redirects_path=".private/_redirects")
    result = runner.invoke(app, ["doctor", str(maintainer), "--format", "json"])
    assert "CANARY-VALUE" not in result.stdout


@pytest.mark.parametrize(
    "bad", [".git/config", "docs/.git/config", "C:foo", "C:/foo", "\\\\server\\share", "\\foo"]
)
def test_a_path_that_is_never_content_or_leaves_on_windows_is_refused(bad: str) -> None:
    with pytest.raises(ValidationError):
        DoctorConfig(redirects_path=Path(bad))


def test_the_scanned_repository_cannot_run_a_command_through_its_config(
    maintainer: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "ran"
    hook = maintainer / ".git/hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    hook.chmod(0o755)
    _git(maintainer, "config", "core.fsmonitor", str(hook))
    _doctor(maintainer)
    assert not marker.exists(), "doctor ran a command the scanned repository configured"


def test_a_git_in_the_current_folder_is_not_the_one_run(
    maintainer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows looks in the current folder first; here a relative entry of PATH stands for it."""
    marker = tmp_path / "ran"
    fake = maintainer / "git"
    fake.write_text(f"#!/bin/sh\n{shutil.which('touch')} {marker}\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.chdir(maintainer)
    monkeypatch.setenv("PATH", ".")
    _doctor(maintainer)
    assert not marker.exists(), "doctor ran a git from the scanned repository"


def test_a_redirects_line_with_brackets_does_not_stop_the_text_output(maintainer: Path) -> None:
    (maintainer / "_redirects").write_text("[/foo] /b 301 extra\n", encoding="utf-8")
    _configured(maintainer, adr_vault_path=VAULT, redirects_path="_redirects")
    _git(maintainer, "add", "_redirects", ".zenzic.toml")
    _git(maintainer, "commit", "-q", "-m", "brackets")
    result = runner.invoke(app, ["doctor", str(maintainer), "--no-header"])
    assert isinstance(result.exception, SystemExit) or result.exception is None, result.exception


def test_a_redirects_file_that_is_not_text_is_a_finding(maintainer: Path) -> None:
    (maintainer / "_redirects").write_bytes(b"\xff\xfe\x00binary")
    _configured(maintainer, adr_vault_path=VAULT, redirects_path="_redirects")
    _git(maintainer, "add", "_redirects", ".zenzic.toml")
    _git(maintainer, "commit", "-q", "-m", "binary")
    result = runner.invoke(app, ["doctor", str(maintainer), "--format", "json"])
    assert "could not read" in result.stdout


def test_adr_new_does_not_write_through_a_link_out_of_the_repository(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "plain"
    root.mkdir()
    (root / "vault").symlink_to(outside, target_is_directory=True)
    _configured(root, adr_vault_path="vault")
    result = runner.invoke(app, ["adr", "new", "A title", "--path", str(root)])
    assert list(outside.rglob("*")) == [], result.output
    assert result.exit_code != 0


class TestThePureCheck:
    """`check_tracked_paths` over a list of tracked files: no git here."""

    @staticmethod
    def _found(
        root: Path,
        tracked: frozenset[str] | None,
        *,
        adr_vault_path: str = "none",
        redirects_path: str = "none",
    ) -> list[str]:
        config = DoctorConfig(
            adr_vault_path=Path(adr_vault_path), redirects_path=Path(redirects_path)
        )
        return [f.message for f in check_tracked_paths(root, config, tracked)]

    def test_a_tracked_file_and_a_folder_with_a_tracked_file_are_clean(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "docs/adr").mkdir(parents=True)
        (tmp_path / "docs/_redirects").write_text("", encoding="utf-8")
        (tmp_path / "docs/adr/one.md").write_text("# One\n", encoding="utf-8")
        tracked = frozenset({"docs/adr/one.md", "docs/_redirects"})
        assert (
            self._found(
                tmp_path, tracked, adr_vault_path="docs/adr", redirects_path="docs/_redirects"
            )
            == []
        )

    def test_a_folder_with_the_same_prefix_does_not_count(self, tmp_path: Path) -> None:
        (tmp_path / "docs/adr").mkdir(parents=True)
        found = self._found(tmp_path, frozenset({"docs/adr-old/one.md"}), adr_vault_path="docs/adr")
        assert len(found) == 1
        assert "docs/adr" in found[0]

    def test_a_path_that_is_not_there_is_for_the_check_that_reads_it(self, tmp_path: Path) -> None:
        assert self._found(tmp_path, frozenset({"a.md"}), adr_vault_path="absent") == []

    def test_nothing_to_compare_with_is_silent(self, tmp_path: Path) -> None:
        (tmp_path / "adr").mkdir()
        assert self._found(tmp_path, None, adr_vault_path="adr") == []

    def test_the_repository_root_as_a_path_is_clean(self, tmp_path: Path) -> None:
        assert self._found(tmp_path, frozenset({"a.md"}), adr_vault_path=".") == []
