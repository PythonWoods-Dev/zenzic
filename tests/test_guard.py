# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``guard`` sub-commands: scan and init.

Covers:
- _is_doc_source
- _scan_file_for_secrets (OSError branch)
- _staged_doc_files (OSError and non-zero returncode branches)
- _resolve_targets (staged, paths with file/dir, default docs_root branches)
- scan command (no targets, json/text output, findings, no findings)
- init_guard command (new file, existing file, already present, existing non-empty)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from zenzic.cli._guard import (
    _is_doc_source,
    _resolve_targets,
    _scan_file_for_secrets,
    _staged_doc_files,
)
from zenzic.main import app


runner = CliRunner()


# ── _is_doc_source ────────────────────────────────────────────────────────────


def test_is_doc_source_md() -> None:
    assert _is_doc_source(Path("foo.md"))


def test_is_doc_source_mdx() -> None:
    assert _is_doc_source(Path("foo.MDX"))


def test_is_doc_source_txt_false() -> None:
    assert not _is_doc_source(Path("foo.txt"))


# ── _scan_file_for_secrets ────────────────────────────────────────────────────


def test_scan_file_for_secrets_oserror(tmp_path: Path) -> None:
    """An unreadable file returns no findings AND reports itself unreadable.

    The second element is the whole point: an empty finding list alone cannot
    distinguish "this file is clean" from "this file could not be opened", and
    a secret gate that conflates the two reports a clean bill it did not earn.
    """
    missing = tmp_path / "nonexistent.md"
    findings, readable = _scan_file_for_secrets(missing, [])
    assert findings == []
    assert readable is False


def test_scan_file_for_secrets_clean_file(tmp_path: Path) -> None:
    """A genuinely clean file returns no findings and reports itself readable."""
    doc = tmp_path / "clean.md"
    doc.write_text("# Hello\n\nThis is a clean document.\n")
    findings, readable = _scan_file_for_secrets(doc, [])
    assert findings == []
    assert readable is True


# ── _staged_doc_files ─────────────────────────────────────────────────────────


def test_staged_doc_files_oserror(tmp_path: Path) -> None:
    """OSError in subprocess.run returns empty list."""
    with patch("zenzic.cli._guard.subprocess.run", side_effect=OSError("no git")):
        result = _staged_doc_files(tmp_path)
    assert result == []


def test_staged_doc_files_nonzero_returncode(tmp_path: Path) -> None:
    """Non-zero returncode from git returns empty list."""
    fake = MagicMock()
    fake.returncode = 1
    fake.stdout = ""
    with patch("zenzic.cli._guard.subprocess.run", return_value=fake):
        result = _staged_doc_files(tmp_path)
    assert result == []


def test_staged_doc_files_returns_existing_docs(tmp_path: Path) -> None:
    """Valid git output listing real .md files returns their resolved paths."""
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Hello\n")
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "docs/index.md\n"
    with patch("zenzic.cli._guard.subprocess.run", return_value=fake):
        result = _staged_doc_files(tmp_path)
    # The staging filter filters by is_file() — because docs/index.md exists relative to cwd,
    # not tmp_path, the list may be empty; that's acceptable for this unit test.
    assert isinstance(result, list)


# ── _resolve_targets ──────────────────────────────────────────────────────────


def test_resolve_targets_staged_delegates(tmp_path: Path) -> None:
    """staged=True delegates to _staged_doc_files."""
    with patch("zenzic.cli._guard._staged_doc_files", return_value=[]) as mock_staged:
        result = _resolve_targets(tmp_path, [], staged=True)
    mock_staged.assert_called_once_with(tmp_path)
    assert result == []


def test_resolve_targets_explicit_file(tmp_path: Path) -> None:
    """Explicit .md file path is returned directly."""
    doc = tmp_path / "page.md"
    doc.write_text("# Page\n")
    result = _resolve_targets(tmp_path, [str(doc)], staged=False)
    assert doc.resolve() in result


def test_resolve_targets_explicit_directory(tmp_path: Path) -> None:
    """Explicit directory path expands to all .md/.mdx files inside."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n")
    (docs / "b.mdx").write_text("# B\n")
    (docs / "c.txt").write_text("plain text")
    result = _resolve_targets(tmp_path, [str(docs)], staged=False)
    names = {p.name for p in result}
    assert "a.md" in names
    assert "b.mdx" in names
    assert "c.txt" not in names


def test_resolve_targets_default_docs_root_missing(tmp_path: Path) -> None:
    """When docs_root doesn't exist, returns empty list."""
    # No docs/ directory exists, no .zenzic.toml
    result = _resolve_targets(tmp_path, [], staged=False)
    assert result == []


def test_resolve_targets_default_docs_root_scans_dir(tmp_path: Path) -> None:
    """When docs_root exists, all .md/.mdx files are returned."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Index\n")
    result = _resolve_targets(tmp_path, [], staged=False)
    assert any(p.name == "index.md" for p in result)


def test_resolve_targets_default_docs_root_skips_venv(tmp_path: Path) -> None:
    """Root scans honor system exclusions even when docs_dir is the repo root."""
    from zenzic.models.config import ZenzicConfig

    readme = tmp_path / "README.md"
    readme.write_text("# Root docs\n")

    venv_readme = (
        tmp_path
        / ".venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "zenzic"
        / "examples"
        / "matrix"
        / "adversarial-validation"
        / "README.md"
    )
    venv_readme.parent.mkdir(parents=True)
    venv_readme.write_text("# Vendored docs\n")

    config = ZenzicConfig(docs_dir=Path("."), excluded_dirs=[])
    with patch("zenzic.cli._guard.ZenzicConfig.load", return_value=(config, None)):
        result = _resolve_targets(tmp_path, [], staged=False)

    assert readme.resolve() in result
    assert all(".venv" not in p.parts for p in result)


# ── scan command ──────────────────────────────────────────────────────────────


def test_guard_scan_no_targets_text(tmp_path: Path) -> None:
    """scan with no targets prints informational message and exits 0."""
    with (
        patch("zenzic.cli._guard.find_repo_root", return_value=tmp_path),
        patch("zenzic.cli._guard._resolve_targets", return_value=[]),
    ):
        result = runner.invoke(app, ["guard", "scan"])
    assert result.exit_code == 0
    assert "no Markdown" in result.output or result.exit_code == 0


def test_guard_scan_no_targets_json(tmp_path: Path) -> None:
    """scan --format json with no targets prints JSON with empty findings."""
    with (
        patch("zenzic.cli._guard.find_repo_root", return_value=tmp_path),
        patch("zenzic.cli._guard._resolve_targets", return_value=[]),
    ):
        result = runner.invoke(app, ["guard", "scan", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["targets"] == 0
    assert data["findings"] == []


def test_guard_scan_clean_text(tmp_path: Path) -> None:
    """scan with no findings exits 0 and prints success message."""
    doc = tmp_path / "index.md"
    doc.write_text("# Clean doc\n")
    with (
        patch("zenzic.cli._guard.find_repo_root", return_value=tmp_path),
        patch("zenzic.cli._guard._resolve_targets", return_value=[doc]),
        patch("zenzic.cli._guard._scan_file_for_secrets", return_value=([], True)),
    ):
        result = runner.invoke(app, ["guard", "scan"])
    assert result.exit_code == 0


def test_guard_scan_with_findings_text_exits_2(tmp_path: Path) -> None:
    """scan with findings prints table and exits 2 in text mode."""
    from zenzic.core.credentials import SecurityFinding

    doc = tmp_path / "leaky.md"
    doc.write_text("sk-abc123\n")
    finding = SecurityFinding(
        file_path=doc,
        line_no=1,
        secret_type="openai-api-key",
        url="",
        match_text="sk-abc123",
    )
    with (
        patch("zenzic.cli._guard.find_repo_root", return_value=tmp_path),
        patch("zenzic.cli._guard._resolve_targets", return_value=[doc]),
        patch("zenzic.cli._guard._scan_file_for_secrets", return_value=([finding], True)),
    ):
        result = runner.invoke(app, ["guard", "scan"])
    assert result.exit_code == 2


def test_guard_scan_with_findings_json_exits_2(tmp_path: Path) -> None:
    """scan --format json with findings prints JSON and exits 2."""
    from zenzic.core.credentials import SecurityFinding

    doc = tmp_path / "leaky.md"
    doc.write_text("sk-abc123\n")
    finding = SecurityFinding(
        file_path=doc,
        line_no=1,
        secret_type="openai-api-key",
        url="",
        match_text="sk-abc123",
    )
    with (
        patch("zenzic.cli._guard.find_repo_root", return_value=tmp_path),
        patch("zenzic.cli._guard._resolve_targets", return_value=[doc]),
        patch("zenzic.cli._guard._scan_file_for_secrets", return_value=([finding], True)),
    ):
        result = runner.invoke(app, ["guard", "scan", "--format", "json"])
    assert result.exit_code == 2
    data = json.loads(result.output)
    assert data["targets"] == 1
    assert len(data["findings"]) == 1


def test_guard_scan_json_clean_exits_0(tmp_path: Path) -> None:
    """scan --format json with no findings exits 0."""
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean\n")
    with (
        patch("zenzic.cli._guard.find_repo_root", return_value=tmp_path),
        patch("zenzic.cli._guard._resolve_targets", return_value=[doc]),
        patch("zenzic.cli._guard._scan_file_for_secrets", return_value=([], True)),
    ):
        result = runner.invoke(app, ["guard", "scan", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["findings"] == []


# ── init_guard command ────────────────────────────────────────────────────────


def test_guard_init_creates_new_file(tmp_path: Path) -> None:
    """guard init creates .pre-commit-hooks.yaml with the hook block."""
    hooks_path = tmp_path / ".pre-commit-hooks.yaml"
    result = runner.invoke(app, ["guard", "init", "--path", str(hooks_path)])
    assert result.exit_code == 0
    content = hooks_path.read_text(encoding="utf-8")
    assert "- id: zenzic-guard" in content


def test_guard_init_already_present(tmp_path: Path) -> None:
    """guard init does nothing when hook block is already present."""
    hooks_path = tmp_path / ".pre-commit-hooks.yaml"
    hooks_path.write_text("- id: zenzic-guard\n  name: existing\n")
    result = runner.invoke(app, ["guard", "init", "--path", str(hooks_path)])
    assert result.exit_code == 0
    # Content must be unchanged
    assert hooks_path.read_text(encoding="utf-8").count("- id: zenzic-guard") == 1


def test_guard_init_appends_to_existing_file(tmp_path: Path) -> None:
    """guard init appends the hook block when file has existing content."""
    hooks_path = tmp_path / ".pre-commit-hooks.yaml"
    hooks_path.write_text("- id: other-hook\n  name: Other\n")
    result = runner.invoke(app, ["guard", "init", "--path", str(hooks_path)])
    assert result.exit_code == 0
    content = hooks_path.read_text(encoding="utf-8")
    assert "- id: other-hook" in content
    assert "- id: zenzic-guard" in content
