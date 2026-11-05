# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Security and discovery tests for Symlink Boundary Enforcement (Z202 Path Traversal)."""

import logging
from pathlib import Path

import pytest

from zenzic.core.discovery import iter_markdown_sources
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.models.config import ZenzicConfig


def test_escaping_symlink_skipped_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure symlinks resolving outside the repository root are skipped and log Z202 warning."""
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "docs"
    docs_root.mkdir(parents=True)

    # Valid internal markdown file
    valid_file = docs_root / "guide.md"
    valid_file.write_text("# Guide\n", encoding="utf-8")

    # Internal symlink pointing inside repo_root
    internal_target = docs_root / "internal_target.md"
    internal_target.write_text("# Internal Target\n", encoding="utf-8")
    internal_symlink = docs_root / "internal_link.md"
    internal_symlink.symlink_to(internal_target)

    # External file outside repo_root
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.md"
    secret_file.write_text("# Secret\n", encoding="utf-8")

    # Escaping symlink in docs pointing outside repo_root
    escaping_symlink = docs_root / "escaping.md"
    escaping_symlink.symlink_to(secret_file)

    config = ZenzicConfig()
    exclusion_manager = LayeredExclusionManager(config, docs_root=docs_root, repo_root=repo_root)

    with caplog.at_level(logging.WARNING, logger="zenzic.core.discovery"):
        discovered = list(iter_markdown_sources(docs_root, config, exclusion_manager))

    discovered_names = {f.name for f in discovered}

    # Internal files and internal symlink must be yielded
    assert "guide.md" in discovered_names
    assert "internal_target.md" in discovered_names
    assert "internal_link.md" in discovered_names

    # Escaping symlink must be skipped
    assert "escaping.md" not in discovered_names

    # Assert Z202 warning was logged for escaping symlink
    assert any("Z202 Path Traversal" in record.message for record in caplog.records)


# ── Extension case: the CLI and the LSP disagreed, and the security tier was on
# the wrong side of it (V031_FIX_SUFFIX_CASE_BYPASS, 2026-09-08) ──────────────
# `discovery.py` compared `path.suffix` verbatim while the LSP, the adapters and
# the scanner compared `path.suffix.lower()`. A credential in `notes.MD` was
# therefore analysed by the editor and invisible to `zenzic check all`: exit 1
# where the Exit Code Contract owes exit 2. `.MD` is an ordinary spelling on a
# case-insensitive filesystem, so this is not a contrived input.


def _case_repo(tmp_path: Path) -> Path:
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Index\n\nSee [notes](notes.MD).\n")
    (docs / "notes.MD").write_text("# Notes\n\nContent that is long enough to avoid noise.\n")
    return docs


def test_iter_markdown_sources_discovers_uppercase_extension(tmp_path: Path) -> None:
    from zenzic.cli._shared import _build_exclusion_manager
    from zenzic.core.discovery import iter_markdown_sources
    from zenzic.models.config import ZenzicConfig

    docs = _case_repo(tmp_path)
    config, _ = ZenzicConfig.load(tmp_path)
    mgr = _build_exclusion_manager(config, tmp_path, docs)
    found = sorted(p.name for p in iter_markdown_sources(docs, config, mgr))
    assert "notes.MD" in found, f"uppercase extension not discovered: {found}"


def test_credential_in_uppercase_extension_file_is_scanned(tmp_path: Path) -> None:
    """The security half: exit 2 is owed, and the CLI returned exit 1."""
    from zenzic.cli._shared import _build_exclusion_manager
    from zenzic.core.discovery import iter_markdown_sources
    from zenzic.models.config import ZenzicConfig

    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    docs = tmp_path / "docs"
    docs.mkdir()
    secret = "AKIA" + "IOSFODNN7EXAMPLE"
    (docs / "leak.MD").write_text(f"# Leak\n\nkey: {secret}\n")
    config, _ = ZenzicConfig.load(tmp_path)
    mgr = _build_exclusion_manager(config, tmp_path, docs)
    assert any(p.name == "leak.MD" for p in iter_markdown_sources(docs, config, mgr)), (
        "a file the credential scanner never sees cannot produce Z201"
    )
