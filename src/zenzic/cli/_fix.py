# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""CLI command for AST Auto-Fix."""

from __future__ import annotations

import difflib
import os
import sys
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from zenzic.core.mutator import EmptyLinkTextMutation, Mutator
from zenzic.core.parser import parse, serialize


def _atomic_write(file_path: Path, content: str) -> None:
    """Atomic Write Barrier."""
    file_path = file_path.resolve()
    dir_path = file_path.parent
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=dir_path, delete=False, prefix=".zenzic-tmp-"
        ) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)
        os.replace(temp_path, file_path)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def fix(
    path: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=True,
            help="Markdown file or directory to auto-fix. Defaults to docs root.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--apply",
            help="Show unified diff without saving changes (default).",
        ),
    ] = True,
) -> None:
    """Auto-fix deterministic structural violations (e.g., Z108)."""
    from zenzic.cli._shared import _build_exclusion_manager
    from zenzic.core.discovery import iter_markdown_sources
    from zenzic.core.scanner import find_repo_root
    from zenzic.models.config import ZenzicConfig

    _search_from: Path | None = None
    if path is not None:
        _pre = path.resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre

    repo_root = find_repo_root(search_from=_search_from)
    config, _ = ZenzicConfig.load(repo_root)
    docs_root = (repo_root / config.docs_dir).resolve()

    if path and path.resolve().is_file():
        files = [path.resolve()]
    else:
        search_dir = path.resolve() if path else docs_root
        exclusion_mgr = _build_exclusion_manager(config, repo_root, docs_root)
        files = list(iter_markdown_sources(search_dir, config, exclusion_mgr))

    from zenzic.core.mutator import (
        BareUrlMutation,
        DeadSuppressionMutation,
        HeadingPunctuationMutation,
        UntaggedCodeBlockMutation,
    )
    from zenzic.core.scanner import _scan_single_file

    modified_count = 0

    for md_file in files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as exc:
            typer.echo(f"Error reading {md_file}: {exc}", err=True)
            continue

        report, _ = _scan_single_file(md_file, config)
        dead_lines = {f.line_no for f in report.rule_findings if f.rule_id == "Z603"}

        mutator = Mutator(
            [
                EmptyLinkTextMutation(),
                UntaggedCodeBlockMutation(),
                DeadSuppressionMutation(dead_lines),
                BareUrlMutation(),
                HeadingPunctuationMutation(),
            ]
        )

        ast = parse(content)
        new_ast, changed = mutator.mutate(ast)

        if not changed:
            continue

        modified_count += 1
        new_content = serialize(new_ast)

        if dry_run:
            diff_lines = list(
                difflib.unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{md_file.name}",
                    tofile=f"b/{md_file.name}",
                    n=3,
                )
            )
            sys.stdout.writelines(diff_lines)
        else:
            try:
                _atomic_write(md_file, new_content)
                try:
                    rel_path = md_file.relative_to(Path.cwd())
                except ValueError:
                    rel_path = md_file
                typer.echo(f"Fixed structural violations in {rel_path}")
            except Exception as exc:
                typer.echo(f"Failed to write {md_file}: {exc}", err=True)

    if modified_count == 0:
        typer.echo("No violations to fix.")
