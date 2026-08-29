# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Snapshot tests for CLI help contracts.

These tests lock the user-facing help surface for:
- zenzic --help
- zenzic check all --help

The snapshot compares normalized semantic lines, not terminal frame glyphs.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from zenzic.core import regex as re


_SNAPSHOTS = Path(__file__).parent / "snapshots"


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _normalize_help(raw: str) -> str:
    # Remove ANSI and frame glyphs, then collapse whitespace for stable matching.
    text = _strip_ansi(raw)
    text = re.sub(r"[─-╿]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _capture_help(args: list[str]) -> str:
    env = dict(os.environ)
    env.update(
        {
            "NO_COLOR": "1",
            "COLUMNS": "220",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    proc = subprocess.run(
        ["uv", "run", "zenzic", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return (proc.stdout or "") + (proc.stderr or "")


def _extract_contract(normalized: str, snippets: list[str]) -> str:
    lines: list[str] = []
    for snippet in snippets:
        assert snippet in normalized, f"Missing help contract snippet: {snippet}"
        lines.append(snippet)
    return "\n".join(lines) + "\n"


def _load_snapshot(name: str) -> str:
    return (_SNAPSHOTS / name).read_text(encoding="utf-8")


def test_root_help_snapshot_contract() -> None:
    normalized = _normalize_help(_capture_help(["--help"]))
    snippets = [
        "Usage: zenzic [OPTIONS] COMMAND [ARGS]...",
        "Run zenzic check all for a full audit, or pick individual checks below.",
        "Core",
        "lab Run interactive lab scenarios for bundled documentation examples.",
        "check Run documentation quality checks.",
        "clean Safely remove unused documentation files.",
        "Quality",
        "score Compute a 0–100 documentation quality score across all checks.",
        "diff Compare current documentation score against the saved snapshot.",
        "explain Show rule metadata, scoring weight, and config genealogy for a rule code.",
        "SDK & Extensibility",
        "init Scaffold a Zenzic configuration in the current project.",
        "Introspection",
        "config Inspect the active Zenzic configuration and the origin of each value.",
        "guard Run the fast pre-commit secret guard for Markdown/MDX files.",
        "inspect Introspect the Zenzic scanner arsenal and plugin registry.",
    ]
    assert _extract_contract(normalized, snippets) == _load_snapshot("help_root.txt")


def test_check_all_help_snapshot_contract() -> None:
    normalized = _normalize_help(_capture_help(["check", "all", "--help"]))
    snippets = [
        "Usage: zenzic check all [OPTIONS] [PATH]",
        "Run all checks: links, orphans, snippets, unused assets, nav contract, directory indices, config assets, and the reference/content/security pipeline (which also covers placeholders, brand rules, and credential scanning).",
        "Optionally pass PATH to scope the audit to a single Markdown file or a custom directory (e.g. ``README.md``, ``content/``). Zenzic auto-selects the StandaloneAdapter when the target lives outside the configured docs directory.",
        "Treat warnings as errors (exit non-zero on any warning).",
        "Output format: text, json, or sarif. [default: text]",
        "Always exit 0; report issues without failing.",
        "Minimal one-line output for pre-commit hooks.",
        "Override the build engine adapter (e.g. mkdocs, zensical). Auto-detected from .zenzic.toml when omitted.",
        "Additional directories to exclude from scanning (repeatable).",
        "Directories to force-include even if excluded by config (repeatable). Cannot override system guardrails.",
        "Show info-level findings (e.g. circular links) in the report.",
        "Force flat URL resolution for offline builds.",
        "Skip HTTP validation of external URLs (Pass 3). For air-gapped / offline environments. Credential scanner (Z201) always active regardless of this flag.",
        "Bypass external URL validation for URLs matching this prefix (repeatable). Merged with excluded_external_urls from .zenzic.toml at runtime.",
        "Sovereign truth-seeking mode: ignore all suppressible bypasses (inline zenzic-ignore and governance.per_file_ignores).",
    ]
    assert _extract_contract(normalized, snippets) == _load_snapshot("help_check_all.txt")
