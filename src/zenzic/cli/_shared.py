# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Shared CLI infrastructure: console singleton, _ui gateway, and cross-command utilities.

All Console and Panel configuration for the CLI lives here or in ``zenzic.ui``.
No other CLI module may instantiate Console or Panel directly.
"""

from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from zenzic.core.adapters import list_adapter_engines
from zenzic.core.codes import (
    CODE_DEFINITIONS,
    CODE_DESCRIPTIONS,
    CODE_NAMES,
    get_sarif_name,
)
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.reporter import Finding, FooterNotice
from zenzic.core.ui import ZenzicPalette, ZenzicUI, emoji
from zenzic.models.config import ZenzicConfig

from ._metadata import COMMAND_BY_NAME


# ── Console singleton & UI gateway ───────────────────────────────────────────

console = Console(
    highlight=False,
    no_color=os.environ.get("NO_COLOR") is not None,
    force_terminal=True
    if os.environ.get("FORCE_COLOR") and not os.environ.get("NO_COLOR")
    else None,
)

stderr_console = Console(
    stderr=True,
    highlight=False,
    no_color=os.environ.get("NO_COLOR") is not None,
    force_terminal=True
    if os.environ.get("FORCE_COLOR") and not os.environ.get("NO_COLOR")
    else None,
)

_ui = ZenzicUI(stderr_console)


def configure_console(*, no_color: bool = False, force_color: bool = False) -> None:
    """Reconfigure the module-level console for color control.

    Called by main.py callback when --no-color or --force-color flags are passed.
    CLI flags take priority over environment variables.  Also rebuilds ``_ui``
    so all subsequent command output uses the reconfigured console.
    """
    global console, stderr_console, _ui
    if no_color:
        console = Console(highlight=False, no_color=True)
        stderr_console = Console(stderr=True, highlight=False, no_color=True)
    elif force_color:
        console = Console(highlight=False, force_terminal=True)
        stderr_console = Console(stderr=True, highlight=False, force_terminal=True)
    # else: keep existing console — no_color=False + force_color=False means "auto",
    # which is already set correctly in the module-level Console (force_terminal=None).
    _ui = ZenzicUI(stderr_console)


def get_ui() -> ZenzicUI:
    """Return the current centralized :class:`~zenzic.ui.ZenzicUI` instance.

    Always performs a live lookup so callers outside this module always receive
    the instance that is current *after* any ``configure_console()`` call.
    """
    return _ui


def get_console() -> Console:
    """Return the current centralized :class:`rich.console.Console` instance."""
    return console


def make_footer_notice(*lines: str) -> FooterNotice:
    """Return a normalized footer notice contract for text-mode command footers."""
    return FooterNotice(lines=tuple(line for line in lines if line))


def footer_hint(command_name: str) -> str:
    """Return the canonical usage hint line for a top-level command name."""
    meta = COMMAND_BY_NAME.get(command_name)
    if meta is None:
        return f"[{ZenzicPalette.DIM}]Try 'zenzic --help' for options.[/]"
    return f"[{ZenzicPalette.DIM}]{meta.usage_hint}[/]"


def print_footer_hint(
    command_name: str,
    *,
    output_format: str = "text",
    quiet: bool = False,
) -> None:
    """Emit a canonical footer navigation hint for human-readable command output."""
    if output_format != "text" or quiet:
        return
    console.print(Text.from_markup(footer_hint(command_name)))


def create_app(*, name: str, long_help: str) -> typer.Typer:
    """Create a Typer sub-app with the standard Zenzic CLI defaults."""
    return typer.Typer(
        name=name,
        help=long_help,
        no_args_is_help=True,
        rich_markup_mode="rich",
    )


# ── Info hint panel ──────────────────────────────────────────────────────────

_NO_CONFIG_HINT = Panel(
    "Using built-in defaults — no [bold].zenzic.toml[/] found.\n"
    "Run [bold cyan]zenzic init[/] to create a project configuration file.\n"
    "Customise docs directory, excluded paths, engine adapter, and lint rules.",
    title=f"[bold yellow]{emoji('info')} Zenzic Tip[/]",
    border_style="yellow",
    expand=False,
)


_MACHINE_FORMATS: frozenset[str] = frozenset({"json", "sarif"})


def _print_no_config_hint(output_format: str = "text") -> None:
    """Print a one-time informational panel when running without .zenzic.toml.

    Suppressed for machine-readable formats (json, sarif) — Rule R20 Machine Silence:
    stdout must remain 100% valid against the target schema; no Rich panels allowed.
    """
    if output_format in _MACHINE_FORMATS:
        return
    console.print(_NO_CONFIG_HINT)
    console.print()


# ── Engine override ───────────────────────────────────────────────────────────


def _apply_engine_override(config: ZenzicConfig, engine: str | None) -> ZenzicConfig:
    """Return *config* with ``build_context.engine`` replaced by *engine*.

    When *engine* is ``None`` or ``"auto"``, the original config is returned
    unchanged.  When *engine* is not a registered adapter, a Rich error is
    printed to stderr and the process exits with code 1.
    """
    if not engine or engine == "auto":
        return config
    known = list_adapter_engines()
    if engine not in known:
        engines_fmt = ", ".join(f"[bold]{e}[/]" for e in known) if known else "(none installed)"
        hint = ""
        suggestions = difflib.get_close_matches(engine, known, n=1, cutoff=0.5)
        if suggestions:
            hint = f"\n\n  Did you mean [bold cyan]{suggestions[0]}[/]?"
        console.print(
            f"[red]ERROR:[/] Unknown engine adapter [bold]{engine!r}[/].\n"
            f"Installed adapters: {engines_fmt}{hint}"
        )
        raise typer.Exit(1)
    new_context = config.build_context.model_copy(update={"engine": engine})
    return config.model_copy(update={"build_context": new_context})


# ── JSON output ───────────────────────────────────────────────────────────────


def _output_json_findings(
    findings: list[Finding], elapsed: float, suppression_audit: Any | None = None
) -> None:
    """Serialize findings list to JSON and print to stdout."""
    report = {
        "findings": [
            {
                "rel_path": f.rel_path,
                "line_no": f.line_no,
                "code": f.code,
                "severity": f.severity,
                "message": f.message,
            }
            for f in findings
        ],
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
            "security_incidents": sum(1 for f in findings if f.severity == "security_incident"),
            "security_breaches": sum(1 for f in findings if f.severity == "security_breach"),
            "elapsed_seconds": round(elapsed, 3),
        },
    }
    if suppression_audit is not None:
        report["suppression"] = {
            "suppression_count": suppression_audit.total,
            "suppression_cap": suppression_audit.cap,
            "suppression_debt_pts": suppression_audit.excess,
            "debt_status": suppression_audit.debt_status,
        }
    print(json.dumps(report, indent=2))


def _output_check_all_json_findings(
    results: Any,
    all_findings: list[Finding],
    repo_root: Path,
    docs_root: Path,
    config: ZenzicConfig,
    suppression_audit: Any | None = None,
) -> None:
    """Format and print the checkAllReport JSON payload."""

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    allowed_keys = {(f.rel_path, f.line_no, f.code) for f in all_findings}

    def _is_allowed(rel_path: str, line_no: int, code: str) -> bool:
        return (rel_path, line_no, code) in allowed_keys

    ref_errors = []
    for r in results.reference_reports:
        rel = _rel(r.file_path)
        for f in r.findings:
            if not f.is_warning:
                if _is_allowed(rel, f.line_no, f.issue):
                    try:
                        rel_d = r.file_path.relative_to(repo_root / config.docs_dir)
                    except ValueError:
                        rel_d = r.file_path
                    ref_errors.append(f"{rel_d}:{f.line_no} [{f.issue}] — {f.detail}")

    report = {
        "links": [
            str(e) for e in results.link_errors if _is_allowed(_rel(e.file_path), e.line_no, e.code)
        ],
        "orphans": [str(p) for p in results.orphans if _is_allowed(_rel(docs_root / p), 0, "Z402")],
        "snippets": [
            {"file": str(e.file_path), "line": e.line_no, "message": e.message}
            for e in results.snippet_errors
            if _is_allowed(_rel(e.file_path), e.line_no, "Z503")
        ],
        "unused_assets": [
            str(p) for p in results.unused_assets if _is_allowed(_rel(docs_root / p), 0, "Z405")
        ],
        "nav_contract": [
            msg for msg in results.nav_contract_errors if _is_allowed("(nav)", 0, "Z406")
        ],
        "references": ref_errors,
        "security_breaches": sum(1 for f in all_findings if f.severity == "security_breach"),
        "security_incidents": sum(1 for f in all_findings if f.severity == "security_incident"),
        "suppression_count": suppression_audit.total if suppression_audit else 0,
        "suppression_cap": suppression_audit.cap if suppression_audit else 0,
        "suppression_debt_pts": suppression_audit.excess if suppression_audit else 0,
        "debt_status": suppression_audit.debt_status if suppression_audit else "CLEAN",
    }
    print(json.dumps(report, indent=2))


# ── SARIF output ──────────────────────────────────────────────────────────────
# Rule metadata (names, descriptions, levels, helpUri) is derived dynamically
# from zenzic.core.codes — the single source of truth.  Do NOT add hardcoded
# rule dicts here; update codes.py instead.

_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

_SARIF_SECURITY_SEVERITY: dict[str, str] = {
    "security_breach": "9.5",
    "security_incident": "9.0",
}


def _sarif_level(severity: str) -> str:
    return {
        "security_breach": "error",
        "security_incident": "error",
        "error": "error",
        "warning": "warning",
        "info": "note",
    }.get(severity, "note")


def _output_sarif_findings(
    findings: list[Finding],
    version: str,
    rules_map: dict[str, Any] | None = None,
) -> None:
    """Serialize findings list to deterministic SARIF 2.1.0 JSON and print to stdout."""
    seen_rule_ids: set[str] = set()

    sorted_findings = sorted(
        findings,
        key=lambda f: (f.rel_path, f.line_no, f.code, f.message),
    )

    sarif_results: list[dict[str, object]] = []
    for f in sorted_findings:
        seen_rule_ids.add(f.code)
        result: dict[str, object] = {
            "ruleId": f.code,
            "level": _sarif_level(f.severity),
            "message": {"text": f.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f.rel_path.replace("\\", "/"),
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {"startLine": max(f.line_no, 1)},
                    }
                }
            ],
        }
        if f.severity in _SARIF_SECURITY_SEVERITY:
            result["properties"] = {"security-severity": _SARIF_SECURITY_SEVERITY[f.severity]}
        sarif_results.append(result)

    rules: list[dict[str, object]] = []
    for rule_id in sorted(seen_rule_ids):
        rule_def = CODE_DEFINITIONS.get(rule_id)
        if rule_def is not None:
            category = rule_def.category or (
                "governance" if rule_id.startswith("Z6") else "uncategorized"
            )
            penalty = rule_def.penalty
            level = rule_def.severity
            help_uri = f"https://zenzic.dev/docs/reference/finding-codes#{rule_id.lower()}"
            short_desc = CODE_DESCRIPTIONS.get(rule_id, CODE_NAMES.get(rule_id, rule_id))
        elif rules_map and rule_id in rules_map:
            rule_obj = rules_map[rule_id]
            meta = getattr(rule_obj, "metadata", None)
            if meta:
                category = getattr(meta, "category", "custom")
                penalty = getattr(meta, "penalty", 1.0)
                level = _sarif_level(getattr(meta, "severity", "warning"))
                help_uri = (
                    getattr(meta, "docs_url", None)
                    or f"https://zenzic.dev/docs/reference/finding-codes#{rule_id.lower()}"
                )
                short_desc = getattr(meta, "description", getattr(meta, "title", rule_id))
            else:
                category = "custom"
                penalty = 1.0
                level = "warning"
                help_uri = f"https://zenzic.dev/docs/reference/finding-codes#{rule_id.lower()}"
                short_desc = rule_id
        else:
            category = "custom" if rule_id.startswith("ZZ-") else "uncategorized"
            penalty = 1.0 if rule_id.startswith("ZZ-") else 0.0
            level = "warning"
            help_uri = f"https://zenzic.dev/docs/reference/finding-codes#{rule_id.lower()}"
            short_desc = CODE_DESCRIPTIONS.get(rule_id, CODE_NAMES.get(rule_id, rule_id))

        rule_entry: dict[str, object] = {
            "id": rule_id,
            "name": get_sarif_name(rule_id),
            "shortDescription": {"text": short_desc},
            "fullDescription": {"text": short_desc},
            "defaultConfiguration": {"level": level},
            "helpUri": help_uri,
            "properties": {
                "category": category,
                "penalty": penalty,
            },
        }
        rules.append(rule_entry)

    run_obj: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": "zenzic",
                "version": version,
                "informationUri": "https://zenzic.dev",
                "rules": rules,
            }
        },
        "results": sarif_results,
    }

    execution_successful = True
    notifications = []
    for f in findings:
        if f.code in {"Z201", "Z202", "Z203", "Z204", "Z205"}:
            execution_successful = False
            notifications.append(
                {
                    "descriptor": {"id": f.code},
                    "level": "error",
                    "message": {"text": f"Critical security finding detected: {f.code}"},
                }
            )

    if not execution_successful:
        run_obj["invocations"] = [
            {
                "executionSuccessful": False,
                "toolExecutionNotifications": notifications,
            }
        ]

    report = {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [run_obj],
    }
    print(json.dumps(report, indent=2))


# ── GitHub Annotations output ─────────────────────────────────────────────────


def _output_github_annotations(findings: list[Finding]) -> None:
    """Print findings as GitHub Actions workflow commands to stdout."""
    for f in findings:
        if f.severity in {"error", "security_breach", "security_incident"}:
            level = "error"
        elif f.severity == "warning":
            level = "warning"
        else:
            level = "notice"

        props = []
        if f.rel_path:
            props.append(f"file={f.rel_path.replace(os.sep, '/')}")
        if f.line_no > 0:
            props.append(f"line={f.line_no}")
        if f.col_start > 0:
            props.append(f"col={f.col_start}")
        if f.code:
            props.append(f"title={f.code}")

        prop_str = ",".join(props)
        msg = f.message.replace("\n", "%0A")
        if prop_str:
            print(f"::{level} {prop_str}::{msg}")
        else:
            print(f"::{level}::{msg}")


# ── Link error renderer ───────────────────────────────────────────────────────


def _render_link_error(err: object, docs_root: Path) -> None:
    """Print a single LinkError with a Visual Snippet when source context is available."""
    from zenzic.core.validator import LinkError

    if not isinstance(err, LinkError):
        return
    try:
        rel = err.file_path.relative_to(docs_root)
        location = f"[{ZenzicPalette.DIM}]{rel}:{err.line_no}[/]"
    except ValueError:
        location = f"[{ZenzicPalette.DIM}]{err.file_path.name}:{err.line_no}[/]"

    raw_msg = err.message
    prefix = f"{err.file_path.relative_to(docs_root).as_posix() if err.file_path != docs_root else ''}:{err.line_no}: "
    body = raw_msg[len(prefix) :] if raw_msg.startswith(prefix) else raw_msg

    type_badge = f"[[bold red]{err.code}[/]]"
    header = f"  {type_badge} {location} — {body}"
    console.print(header)

    if err.source_line:
        console.print(f"    [{ZenzicPalette.DIM}]│[/] [italic]{err.source_line}[/]")


# ── Exclusion manager factory ─────────────────────────────────────────────────


def _build_exclusion_manager(
    config: ZenzicConfig,
    repo_root: Path,
    docs_root: Path,
    *,
    exclude_dirs: list[str] | None = None,
    include_dirs: list[str] | None = None,
    adapter_metadata_files: frozenset[str] = frozenset(),
) -> LayeredExclusionManager:
    """Construct a :class:`LayeredExclusionManager` from config + CLI flags.

    This is the **single factory** for exclusion managers in the CLI layer.
    Every command must call this and pass the result down the pipeline.

    Includes F4-1 jailbreak protection: rejects ``docs_root`` paths that
    escape the repository root via path traversal (``../``).
    """
    _validate_docs_root(repo_root, docs_root)
    return LayeredExclusionManager(
        config,
        repo_root=repo_root,
        docs_root=docs_root,
        cli_exclude=exclude_dirs,
        cli_include=include_dirs,
        adapter_metadata_files=adapter_metadata_files,
    )


def _validate_docs_root(repo_root: Path, docs_root: Path) -> None:
    """F4-1: Reject docs_dir paths that escape the repository root.

    Raises :class:`typer.Exit` with code 3 (path traversal guard) if
    ``docs_root.resolve()`` is not under ``repo_root.resolve()``.
    This prevents path-traversal attacks via ``docs_dir = "../../etc"``.
    """
    resolved_repo = repo_root.resolve()
    resolved_docs = docs_root.resolve()
    try:
        resolved_docs.relative_to(resolved_repo)
    except ValueError:
        console.print(
            f"[bold {ZenzicPalette.FATAL}]PATH TRAVERSAL:[/] docs_dir resolves to "
            f"[bold]{resolved_docs}[/] which is outside the repository root "
            f"[bold]{resolved_repo}[/]. Path traversal blocked."
        )
        raise typer.Exit(3) from None


# ── Telemetry counter ─────────────────────────────────────────────────────────


def _count_docs_assets(
    docs_root: Path,
    repo_root: Path,
    exclusion_mgr: LayeredExclusionManager,
    config: ZenzicConfig | None = None,
) -> tuple[int, int]:
    """Return ``(docs_count, assets_count)`` for the analysis telemetry line.

    When *config* is provided and the adapter exposes ``get_locale_source_roots()``,
    locale translation trees (e.g. MkDocs or Zensical ``docs-it/``) are counted in
    ``docs_count`` as well.
    """
    from zenzic.core.discovery import walk_files
    from zenzic.models.config import SYSTEM_EXCLUDED_DIRS

    _INERT = {".css", ".js"}
    _CONFIG = {".yml", ".yaml", ".toml"}
    _DOC_EXT = {".md", ".mdx"}
    if not docs_root.is_dir():
        return 0, 0
    docs_count = sum(
        1
        for p in walk_files(docs_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
        if p.suffix.lower() in _DOC_EXT or p.suffix.lower() in _CONFIG
    )
    docs_count += sum(
        1 for p in repo_root.iterdir() if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
    )
    assets_count = sum(
        1
        for p in walk_files(docs_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
        if p.suffix.lower() not in _INERT
        and p.suffix.lower() not in _CONFIG
        and p.suffix.lower() not in _DOC_EXT
    )
    if config is not None:
        from zenzic.core.adapters import get_adapter

        adapter = get_adapter(config.build_context, docs_root, repo_root)
        for locale_root, _ in adapter.get_locale_source_roots(repo_root):
            docs_count += sum(
                1
                for p in walk_files(locale_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
                if p.suffix.lower() in _DOC_EXT
            )
    return docs_count, assets_count
