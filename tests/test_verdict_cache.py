# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The verdict cache skips only a byte-identical tree, and never a failing stage.

The dangerous outcome is a skip on a tree that changed -- an untracked new
file, a deletion, an edit to the gitignored local trees the local gates
read -- so each of those must move the key. The other dangerous outcome is a
recorded verdict for a stage that failed. Both directions are asserted on a
real repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import verdict_cache as vc  # noqa: E402


def _run(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("ZENZIC_VERDICT_CACHE", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    _run(["git", "init", "-q", "-b", "main"], root)
    for k, v in (("user.email", "t@e.invalid"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _run(["git", "config", k, v], root)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    (root / ".gitignore").write_text(".claude/\n.zenzic_cache/\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "seed"], root)
    return root


def _touch_counter(root: Path) -> list[str]:
    """A command that records every real execution -- outside the repository,
    or its own log would be an untracked file and move the key it is testing."""
    log = root.parent / "ran.log"
    return ["sh", "-c", f"echo ran >> {log}"]


def _runs(root: Path) -> int:
    log = root.parent / "ran.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def test_second_run_on_an_identical_tree_is_skipped(repo: Path) -> None:
    cache = repo / ".zenzic_cache" / "verdicts"
    assert vc.run("stage", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    assert vc.run("stage", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    assert _runs(repo) == 1, "the command must run once, not twice, on the same tree"


def test_a_tracked_edit_an_untracked_file_a_deletion_and_a_private_edit_each_move_the_key(
    repo: Path,
) -> None:
    keys = {vc.tree_key(repo)}
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    keys.add(vc.tree_key(repo))
    (repo / "new.txt").write_text("new\n", encoding="utf-8")  # untracked, not ignored
    keys.add(vc.tree_key(repo))
    (repo / "a.txt").unlink()
    keys.add(vc.tree_key(repo))
    (repo / ".claude").mkdir()
    (repo / ".claude" / "rule.md").write_text("rule\n", encoding="utf-8")  # gitignored
    keys.add(vc.tree_key(repo))
    (repo / ".claude" / "rule.md").write_text("rule changed\n", encoding="utf-8")
    keys.add(vc.tree_key(repo))
    assert len(keys) == 6, "every one of the five changes must produce a distinct key"


def test_a_failing_stage_records_no_verdict(repo: Path) -> None:
    cache = repo / ".zenzic_cache" / "verdicts"
    assert vc.run("stage", ["sh", "-c", "exit 7"], root=repo, cache_dir=cache) == 7
    assert not (cache / "stage").exists()
    assert vc.run("stage", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    assert _runs(repo) == 1, "after a failure the next run must execute for real"


def test_ci_and_the_off_switch_disable_the_cache(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = repo / ".zenzic_cache" / "verdicts"
    assert vc.run("stage", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    monkeypatch.setenv("CI", "1")
    assert vc.run("stage", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    monkeypatch.delenv("CI")
    monkeypatch.setenv("ZENZIC_VERDICT_CACHE", "0")
    assert vc.run("stage", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    assert _runs(repo) == 3


def test_a_commit_does_not_move_the_key(repo: Path) -> None:
    """`just verify`, then `git commit`, then the pre-push hook: same bytes,
    same key. A key that included `git status` would miss here."""
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    before = vc.tree_key(repo)
    _run(["git", "add", "-A"], repo)
    staged = vc.tree_key(repo)
    _run(["git", "commit", "-q", "-m", "edit"], repo)
    assert before == staged == vc.tree_key(repo)


def test_labels_are_independent(repo: Path) -> None:
    cache = repo / ".zenzic_cache" / "verdicts"
    assert vc.run("one", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    assert vc.run("two", _touch_counter(repo), root=repo, cache_dir=cache) == 0
    assert _runs(repo) == 2
