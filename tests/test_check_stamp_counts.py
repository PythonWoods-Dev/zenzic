# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`zenzic score --check-stamp` names what it checked, and fails on what it could not.

Measured on 2026-09-17 in `zenzic-vscode`: `badge_stamp_files = ["README.md"]`
over a README with no marker printed `[SUCCESS] All badges are current.` --
a zero the instrument could not tell from a checked file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


SCORE = "<!-- zenzic:score-badge -->\n![score](https://img.shields.io/badge/placeholder-0-000000)\n"
AUDIT = "<!-- zenzic:audit-badge -->\n![audit](https://img.shields.io/badge/placeholder-0-000000)\n"


def _repo(tmp_path: Path, readme: str | None, files: str = '["README.md"]') -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text(
        "# Home\n\nA page with enough ordinary prose to pass the placeholder check, and a few more "
        "words for good measure so that nothing else is reported on it during the audit at all.\n",
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.toml").write_text(
        f'docs_dir = "docs"\n[project_metadata]\nbadge_stamp_files = {files}\n', encoding="utf-8"
    )
    if readme is not None:
        (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    return tmp_path


def _score(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    """Exit code and the output flattened to single spaces: Rich wraps at the
    console width, which differs between a lone run and an xdist worker, and
    a phrase must not fail for having been broken across two lines."""
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ["score", "--no-header", *args])
    return result.exit_code, " ".join(result.output.split())


def test_a_declared_file_with_no_marker_fails_and_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, "# Plain README\n\nNo badge here.\n")
    code, out = _score(root, monkeypatch, "--check-stamp")
    assert code == 1, out
    # Rich may soft-wrap inside a long temp path ("REA DME.md"), so the name is
    # looked for with spaces removed; the phrases are looked for as written.
    assert "README.md" in out.replace(" ", "") and "cannot be checked" in out and "neither" in out
    assert "current" not in out.lower().replace("cannot", "")


def test_a_declared_file_that_does_not_exist_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, None)
    code, out = _score(root, monkeypatch, "--check-stamp")
    assert code == 1 and "not on disk" in out, out


def test_two_current_badges_are_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, "# R\n\n" + SCORE + AUDIT)
    _score(
        root, monkeypatch, "--stamp"
    )  # writes the current URLs (exits 1 by design: a badge changed)
    code, out = _score(root, monkeypatch, "--check-stamp")
    assert code == 0, out
    assert "2 badge(s) current in 1 file(s)" in out


def test_one_marker_only_is_a_named_skip_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, "# R\n\n" + SCORE)
    _score(root, monkeypatch, "--stamp")
    code, out = _score(root, monkeypatch, "--check-stamp")
    assert code == 0, out
    assert (
        "1 badge(s) current" in out
        and "1 skipped (no marker)" in out
        and "audit badge in README.md skipped" in out
    )


def test_a_stale_badge_still_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, "# R\n\n" + SCORE + AUDIT)
    code, out = _score(root, monkeypatch, "--check-stamp")
    assert code == 1 and "is stale" in out, out


def test_an_empty_declaration_says_zero_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, None, files="[]")
    code, out = _score(root, monkeypatch, "--check-stamp")
    assert code == 0 and "0 badges checked" in out, out
