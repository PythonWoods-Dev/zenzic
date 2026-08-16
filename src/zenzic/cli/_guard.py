# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""guard sub-commands: fast pre-commit credential scanner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer
from rich.table import Table

from zenzic.core.credentials import (
    SecurityFinding,
    scan_line_for_forbidden_terms,
    scan_line_for_secrets,
)
from zenzic.core.discovery import iter_markdown_sources
from zenzic.core.scanner import find_repo_root
from zenzic.core.ui import ZenzicPalette
from zenzic.models.config import ZenzicConfig

from . import _shared
from ._metadata import COMMAND_BY_NAME


guard_app = _shared.create_app(
    name="guard",
    long_help=(f"[bold {ZenzicPalette.BRAND}]Guard[/] — {COMMAND_BY_NAME['guard'].long_help}"),
)


def _is_doc_source(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".mdx"}


def _scan_file_for_secrets(path: Path, forbidden_patterns: list[str]) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return findings

    for idx, line in enumerate(lines, start=1):
        findings.extend(scan_line_for_secrets(line, path, idx))
        findings.extend(scan_line_for_forbidden_terms(line, forbidden_patterns, path, idx))
    return findings


def _staged_doc_files(repo_root: Path) -> list[Path]:
    """Return staged Markdown/MDX files from git index (fast pre-commit path)."""
    cmd = [
        "git",
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMRT",
    ]
    try:
        proc = subprocess.run(  # noqa: S603  # Fixed hardcoded git diff arguments
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    if proc.returncode != 0:
        return []

    candidates = [repo_root / line.strip() for line in proc.stdout.splitlines() if line.strip()]
    docs = [p.resolve() for p in candidates if p.is_file() and _is_doc_source(p)]
    return sorted(set(docs))


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _resolve_targets(repo_root: Path, paths: list[str], staged: bool) -> list[Path]:
    config, _ = ZenzicConfig.load(repo_root)
    docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    if staged:
        return _staged_doc_files(repo_root)

    if paths:
        repo_scan_root = repo_root.resolve()
        repo_scan_mgr = _shared._build_exclusion_manager(config, repo_root, repo_scan_root)
        repo_markdown = sorted(iter_markdown_sources(repo_scan_root, config, repo_scan_mgr))
        repo_markdown_set = set(repo_markdown)

        resolved: list[Path] = []
        for raw in paths:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = (repo_root / candidate).resolve()
            if candidate.is_file() and _is_doc_source(candidate):
                if candidate.resolve() in repo_markdown_set:
                    resolved.append(candidate)
            elif candidate.is_dir():
                resolved.extend(p for p in repo_markdown if _is_within(p, candidate))
        return sorted(set(resolved))

    if not docs_root.is_dir():
        return []
    return sorted(iter_markdown_sources(docs_root, config, exclusion_mgr))


def _mask_secret(secret: str) -> str:
    """Mask sensitive secret values to prevent cleartext exposure in logs/terminal (CWE-312 / CWE-532)."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


@guard_app.command(name="scan")
def scan(
    paths: list[str] = typer.Argument(
        None,
        help=(
            "Optional file/directory targets. If omitted, scans docs scope from config; "
            "with --staged scans staged Markdown/MDX files only."
        ),
    ),
    staged: bool = typer.Option(
        False,
        "--staged",
        help="Scan only staged Markdown/MDX files from git index (pre-commit fast path).",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text or json.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress output except for detected secrets.",
    ),
    no_header: bool = typer.Option(
        False,
        "--no-header",
        help="Suppress the Zenzic startup banner.",
    ),
) -> None:
    """Run pre-commit credential scan using built-in signatures and local forbidden patterns."""
    repo_root = find_repo_root(fallback_to_cwd=True)
    config, _ = ZenzicConfig.load(repo_root)

    targets = _resolve_targets(repo_root, paths or [], staged)
    if not targets:
        if output_format == "json":
            print(json.dumps({"targets": 0, "findings": []}, indent=2))
        elif not quiet:
            _shared.console.print(
                f"[{ZenzicPalette.DIM}]Secret Guard: no Markdown/MDX targets found.[/]"
            )
            _shared.print_footer_hint("guard")
        return

    findings: list[SecurityFinding] = []
    forbidden_patterns = [p for p in config.forbidden_patterns if isinstance(p, str) and p.strip()]

    for target in targets:
        findings.extend(_scan_file_for_secrets(target, forbidden_patterns))

    if output_format == "json":
        items = []
        for f in findings:
            items.append(
                {
                    "file": str(f.file_path),
                    "line": f.line_no,
                    "type": str(f.secret_type),
                    "match": _mask_secret(f.match_text),
                    "context": _mask_secret(f.url) if f.url else "",
                }
            )
        payload = {
            "targets": len(targets),
            "findings": items,
        }
        print(json.dumps(payload, indent=2))
        if findings:
            raise typer.Exit(2)
        return

    table = Table(
        title=f"[bold {ZenzicPalette.BRAND}]Secret Guard[/]",
        header_style=ZenzicPalette.STYLE_BRAND,
        border_style=ZenzicPalette.DIM,
    )
    table.add_column("File", overflow="fold")
    table.add_column("Line", justify="right", width=6)
    table.add_column("Type", style=ZenzicPalette.ERROR)
    table.add_column("Match", overflow="fold")

    if findings:
        for finding in findings:
            try:
                rel = finding.file_path.resolve().relative_to(repo_root)
                file_cell = str(rel)
            except ValueError:
                file_cell = str(finding.file_path)
            table.add_row(
                file_cell,
                str(finding.line_no),
                finding.secret_type,
                _mask_secret(finding.match_text),
            )
        _shared.console.print(table)
        _shared.console.print(
            f"[bold {ZenzicPalette.ERROR}]Secret Guard blocked commit:[/] "
            f"{len(findings)} finding(s) across {len(targets)} file(s)."
        )
        raise typer.Exit(2)

    if not quiet:
        _shared.console.print(
            f"[bold {ZenzicPalette.SUCCESS}]Secret Guard clean:[/] "
            f"{len(targets)} file(s) scanned, no secrets detected."
        )
        _shared.print_footer_hint("guard")


_GUARD_HOOK_BLOCK = """- id: zenzic-guard
  name: zenzic guard (Secret Guard)
  description: Fast staged-file credential scan for Markdown/MDX before commit.
  entry: zenzic guard scan --staged
  language: python
  types: [markdown]
  pass_filenames: false
  require_serial: true
"""


@guard_app.command(name="init")
def init_guard(
    path: str = typer.Option(
        ".pre-commit-hooks.yaml",
        "--path",
        help="Path of the pre-commit hooks definition file to create/update.",
        show_default=True,
    ),
) -> None:
    """Create or update .pre-commit-hooks.yaml with native Secret Guard hook."""
    target = Path(path).resolve()
    existing = ""
    if target.is_file():
        existing = target.read_text(encoding="utf-8")

    if "- id: zenzic-guard" in existing:
        _shared.console.print(
            f"[{ZenzicPalette.DIM}]Secret Guard hook already present; no changes applied.[/]"
        )
        _shared.print_footer_hint("guard")
        return

    if existing.strip():
        content = existing.rstrip() + "\n\n" + _GUARD_HOOK_BLOCK
    else:
        spdx_id_label = "SPDX-License-Identifier"
        content = (
            "# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>\n"
            f"# {spdx_id_label}: Apache-2.0\n\n"
            "# Generated by `zenzic guard init`\n"
            "# Native Secret Guard hook for staged Markdown/MDX files.\n\n" + _GUARD_HOOK_BLOCK
        )

    target.write_text(content, encoding="utf-8")
    _shared.console.print(f"[bold {ZenzicPalette.SUCCESS}]Secret Guard hook installed:[/] {target}")
    _shared.print_footer_hint("guard")
