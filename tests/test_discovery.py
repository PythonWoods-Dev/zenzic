# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Security and discovery tests for Symlink Boundary Enforcement (Z202 Path Traversal)."""

import logging
from pathlib import Path
import pytest

from zenzic.core.discovery import iter_markdown_sources, walk_files
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.models.config import ZenzicConfig


def test_escaping_symlink_skipped_and_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
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
