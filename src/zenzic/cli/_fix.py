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
    rename: Annotated[
        tuple[str, str] | None,
        typer.Option(
            "--rename",
            help=(
                "Repair inbound relative links across the docs tree after renaming/moving "
                "OLD to NEW (e.g. after `git mv docs/old.md docs/new.md`). OLD does not need "
                "to still exist on disk. Same --dry-run/--apply gate as the default mode."
            ),
        ),
    ] = None,
) -> None:
    """Auto-fix deterministic structural violations (e.g., Z108)."""
    from zenzic.cli._shared import _build_exclusion_manager
    from zenzic.core.discovery import iter_markdown_sources
    from zenzic.core.scanner import find_repo_root
    from zenzic.models.config import ZenzicConfig

    if rename is not None:
        _fix_rename(rename[0], rename[1], dry_run=dry_run)
        return

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
        MalformedListMutation,
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
                MalformedListMutation(),
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


def _fix_rename(old: str, new: str, *, dry_run: bool) -> None:
    """Repair inbound relative links across the docs tree after a rename.

    CLI/batch counterpart to the LSP's `workspace/willRenameFiles` handler
    (`zenzic.lsp.server._handle_will_rename_files`) -- same `RenameLinkMutation`
    (no new resolution logic), same safety gates (alias-style hrefs skipped,
    a suppressed occurrence never rewritten), same "report every file
    individually, never a single opaque batch result" discipline.

    Unlike the LSP version, this scans the whole docs tree directly instead
    of using the VSM's `incoming_links` reverse index: OLD does not need to
    still exist on disk (the realistic `git mv old new && zenzic fix --rename
    old new` workflow already moved it), so there is no VSM entry to key a
    reverse-index lookup off in the general case.
    """
    from zenzic.cli._shared import _build_exclusion_manager
    from zenzic.core.discovery import iter_markdown_sources
    from zenzic.core.mutator import Mutator, RenameLinkMutation
    from zenzic.core.scanner import _scan_single_file, find_repo_root
    from zenzic.models.config import ZenzicConfig

    old_path = Path(old).resolve()
    new_path = Path(new).resolve()

    _search_from = old_path.parent
    repo_root = find_repo_root(search_from=_search_from)
    config, _ = ZenzicConfig.load(repo_root)
    docs_root = (repo_root / config.docs_dir).resolve()
    docs_root_str = str(docs_root)
    repo_root_str = str(repo_root)
    old_abs = str(old_path)
    new_abs = str(new_path)

    exclusion_mgr = _build_exclusion_manager(config, repo_root, docs_root)
    files = list(iter_markdown_sources(docs_root, config, exclusion_mgr))

    fixed_count = 0
    skipped_count = 0
    checked_count = 0

    for md_file in files:
        if md_file.resolve() in (old_path, new_path):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as exc:
            typer.echo(f"Error reading {md_file}: {exc}", err=True)
            continue

        checked_count += 1

        try:
            rel_path = md_file.relative_to(Path.cwd())
        except ValueError:
            rel_path = md_file

        # Safety gate: if ANY occurrence of a link-integrity finding at this
        # file's location is inline-suppressed, skip it -- same fail-safe
        # choice as the LSP version (no per-occurrence location scoping
        # exists to respect partial suppression surgically).
        try:
            report, _ = _scan_single_file(md_file, config, text=content)
        except Exception:
            report = None
        suppressed = bool(
            report
            and report.suppression_tracker
            and any(d.consumed for d in report.suppression_tracker.directives)
        )
        if suppressed:
            typer.echo(f"Skipped {rel_path}: has an active inline suppression, not overriding it")
            skipped_count += 1
            continue

        try:
            mutation = RenameLinkMutation(
                source_file=md_file,
                docs_root_str=docs_root_str,
                repo_root_str=repo_root_str,
                old_abs=old_abs,
                new_abs=new_abs,
            )
            ast = parse(content)
            new_ast, changed = Mutator([mutation]).mutate(ast)
        except Exception as exc:
            typer.echo(f"Skipped {rel_path}: mutation failed ({exc})", err=True)
            skipped_count += 1
            continue

        if not changed:
            continue

        new_content = serialize(new_ast)
        fixed_count += 1

        if dry_run:
            diff_lines = list(
                difflib.unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                    n=3,
                )
            )
            sys.stdout.writelines(diff_lines)
        else:
            try:
                _atomic_write(md_file, new_content)
                typer.echo(f"Repaired link to {Path(new).name} in {rel_path}")
            except Exception as exc:
                typer.echo(f"Failed to write {md_file}: {exc}", err=True)

    if fixed_count == 0:
        suffix = f" ({skipped_count} skipped)" if skipped_count else ""
        typer.echo(
            f"No inbound links to {Path(old).name} found in {checked_count} file(s){suffix}."
        )
    elif skipped_count:
        typer.echo(f"{fixed_count} file(s) repaired, {skipped_count} skipped (see above).")
