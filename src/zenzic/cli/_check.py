# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Check sub-commands: links, orphans, snippets, references, assets, placeholders, all."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import typer

from zenzic import __version__
from zenzic.core.adapters import get_adapter
from zenzic.core.adapters._mkdocs import check_config_assets as _mkdocs_check_assets
from zenzic.core.adapters._zensical import check_config_assets as _zensical_check_assets
from zenzic.core.baseline import DEFAULT_BASELINE_FILE, BaselineManager
from zenzic.core.codes import CODE_DEFINITIONS, code_severity
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.reporter import Finding, ZenzicReporter
from zenzic.core.scanner import (
    _build_rule_engine,
    _map_credential_to_finding,
    find_missing_directory_indices,
    find_orphans,
    find_repo_root,
    find_unused_assets,
    scan_docs_references,
)
from zenzic.core.scorer import compute_score
from zenzic.core.sovereign_context import sovereign_context
from zenzic.core.ui import ZenzicPalette
from zenzic.core.validator import (
    LinkError,
    SnippetError,
    check_nav_contract,
    validate_links_structured,
    validate_snippets,
)
from zenzic.models.config import ZenzicConfig
from zenzic.models.references import IntegrityReport

from . import _shared
from ._governance import (
    SuppressionAudit,
    _apply_directory_policies,
    _apply_per_file_ignores,
    build_cap_exceeded_json_payload,
    build_cap_exceeded_sarif_payload,
    collect_inline_suppression_stats,
    count_per_file_ignores,
    print_governance_cap_failure,
    print_suppression_audit_footer,
    resolve_governance_panel_title,
)
from ._metadata import COMMAND_BY_NAME
from ._target_resolver import _apply_target


check_app = _shared.create_app(
    name="check",
    long_help=(f"[bold {ZenzicPalette.BRAND}]Check[/] — {COMMAND_BY_NAME['check'].long_help}"),
)


def _validate_only_flag(only: str | None) -> None:
    if not only:
        return
    for code in only.split(","):
        code = code.strip().upper()
        if code and code not in CODE_DEFINITIONS:
            _shared.console.print(
                f"[bold red]Error:[/] Invalid finding code '{code}' provided to --only flag."
            )
            raise typer.Exit(1)


def _finding_severity(code: str) -> str:
    """Derive CLI finding severity from CodeDefinition SSoT (codes.py).

    Returns ``"security_incident"`` only for Z203 (fatal system-path traversal),
    ``"security_breach"`` for Z205 (Tier-0 'Exit 2 — never suppressible' set,
    alongside Z201/Z204 which reach this severity via the credential-scanner
    bridge in ``_map_credential_to_finding`` instead of this function), and
    the base SSoT severity (``"error"``, ``"warning"``, or ``"info"`` —
    derived from ``codes.py`` via ``code_severity()``, the same Core-layer
    helper ``rules.py`` and ``incremental.py`` use) for all others. Unknown
    codes default to ``"error"`` since the validator only emits findings
    when it detects a genuine problem.

    This is the CLI-layer wrapper around ``code_severity()``: the Z2xx
    security-breach/security-incident reclassification is a CLI-only
    reporting concern (exit-code contract), not part of the Core severity
    vocabulary ``RuleFinding.severity`` accepts.
    """
    if code == "Z203":
        return "security_incident"
    if code == "Z205":
        return "security_breach"
    try:
        return code_severity(code)
    except KeyError:
        return "error"


# ── Check commands ────────────────────────────────────────────────────────────


@check_app.command(name="links")
def check_links(
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Treat warnings as errors (exit non-zero on any warning).",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Force flat URL resolution for offline builds."
    ),
    no_external: bool = typer.Option(
        False,
        "--no-external",
        help=(
            "Skip HTTP validation of external URLs (Pass 3). "
            "For air-gapped / offline environments. "
            "Credential scanner (Z201) always active regardless of this flag."
        ),
    ),
    exclude_url: list[str] = typer.Option(
        [],
        "--exclude-url",
        help=(
            "Bypass external URL validation for URLs matching this prefix (repeatable). "
            "Merged with excluded_external_urls from .zenzic.toml at runtime."
        ),
        metavar="PREFIX",
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress output except for errors.",
    ),
    no_header: bool = typer.Option(
        False,
        "--no-header",
        help="Suppress the Zenzic startup banner.",
    ),
    path: str | None = typer.Argument(
        None,
        help="Limit to a directory or file. Accepts paths relative to repository root or docs directory. The path must be inside a project with a .git/ directory or .zenzic.toml (root marker); run 'zenzic init' first if no marker exists.",
        show_default=False,
    ),
) -> None:
    """Check for broken internal links and enforce strict warning policy when requested."""
    _validate_only_flag(only)

    if ci or quiet:
        no_header = True
    if ci:
        strict = True
        if output_format == "text":
            output_format = "github-annotations"

    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    repo_root = find_repo_root(search_from=_search_from)
    config, _ = ZenzicConfig.load(repo_root)
    if offline:
        config.build_context.offline_mode = True
    if exclude_url:
        config = config.model_copy(
            update={"excluded_external_urls": config.excluded_external_urls + list(exclude_url)}
        )
    if path is not None:
        config, _, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    t0 = time.monotonic()

    adapter = get_adapter(config.build_context, docs_root, repo_root)
    _roots = adapter.get_locale_source_roots(repo_root)
    locale_roots: list[tuple[Path, str]] | None = _roots if _roots else None

    # Scan once, share the reports with validate_links_structured() (via its
    # own `reports=` reuse parameter) so credential-scan results already
    # computed during this same pass aren't discarded. See
    # V031_EXIT2_WIRING_AND_Z406_ADAPTER_AGNOSTICISM_CHECK: harvest() already
    # runs the credential scanner unconditionally as part of this scan; this
    # subcommand previously threw its output away instead of surfacing it.
    reports, ext_errors = scan_docs_references(
        docs_root,
        exclusion_mgr,
        repo_root=repo_root,
        config=config,
        validate_links=strict and not no_external,
        locale_roots=locale_roots,
    )
    link_errors = validate_links_structured(
        docs_root,
        exclusion_mgr,
        repo_root=repo_root,
        config=config,
        strict=strict,
        locale_roots=locale_roots,
        check_external=not no_external,
        reports=reports,
        ext_errors=ext_errors,
    )
    elapsed = time.monotonic() - t0

    findings = [
        Finding(
            rel_path=_rel(err.file_path),
            line_no=err.line_no,
            code=err.code,
            severity=_finding_severity(err.code),
            message=err.message,
            source_line=err.source_line,
            col_start=err.col_start,
            match_text=err.match_text,
        )
        for err in link_errors
    ]
    for report in reports:
        for sf in report.security_findings:
            findings.append(_map_credential_to_finding(sf, repo_root))
    _append_z620_findings(
        findings, config, repo_root, check_all=False, check_external_urls=not no_external
    )
    findings = _filter_flat_findings(findings, only)

    if output_format == "json":
        _shared._output_json_findings(findings, elapsed)
        incidents = sum(1 for f in findings if f.severity == "security_incident")
        if incidents:
            raise typer.Exit(3)
        breaches = sum(1 for f in findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count > 0 or (strict and warnings_count > 0):
            raise typer.Exit(1)
        return
    elif output_format == "sarif":
        _engine = _build_rule_engine(config)
        _rules_map = {r.rule_id: r for r in _engine._rules} if _engine else None
        _shared._output_sarif_findings(findings, __version__, rules_map=_rules_map)
        incidents = sum(1 for f in findings if f.severity == "security_incident")
        if incidents:
            raise typer.Exit(3)
        breaches = sum(1 for f in findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count > 0 or (strict and warnings_count > 0):
            raise typer.Exit(1)
        return
    elif output_format == "github-annotations":
        _shared._output_github_annotations(findings)
        incidents = sum(1 for f in findings if f.severity == "security_incident")
        if incidents:
            raise typer.Exit(3)
        breaches = sum(1 for f in findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count > 0 or (strict and warnings_count > 0):
            raise typer.Exit(1)
        return

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)
        if path is not None:
            try:
                _hint = str(docs_root.relative_to(Path.cwd()))
            except ValueError:
                _hint = str(docs_root)
            _shared.console.print(f"[{ZenzicPalette.DIM}]  Scanning: {_hint}[/]")

    reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
    if quiet:
        errors, warnings = reporter.render_quiet(findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(docs_root, repo_root, exclusion_mgr)
        footer_lines = [f"[{ZenzicPalette.DIM}]Try 'zenzic check links --help' for options.[/]"]
        if no_external and output_format == "text":
            footer_lines.append(
                f"[{ZenzicPalette.DIM}]💡 External link validation skipped (--no-external). "
                f"Credential scanner (Z201) remains active.[/]"
            )
        errors, warnings = reporter.render(
            findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            ok_message="No broken links found.",
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(*footer_lines),
        )
    incidents = sum(1 for f in findings if f.severity == "security_incident")
    if incidents:
        raise typer.Exit(3)
    breaches = sum(1 for f in findings if f.severity == "security_breach")
    if breaches:
        raise typer.Exit(2)
    if errors or (strict and warnings):
        raise typer.Exit(1)


@check_app.command(name="orphans")
def check_orphans(
    engine: str | None = typer.Option(
        None,
        "--engine",
        help="Override the build engine adapter (e.g. mkdocs, zensical). "
        "Auto-detected from .zenzic.toml when omitted.",
        metavar="ENGINE",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except for errors."),
    no_header: bool = typer.Option(
        False, "--no-header", help="Suppress the Zenzic startup banner."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Force flat URL resolution for offline builds."
    ),
    path: str | None = typer.Argument(
        None,
        help="Limit to a directory or file. Accepts paths relative to repository root or docs directory. The path must be inside a project with a .git/ directory or .zenzic.toml (root marker); run 'zenzic init' first if no marker exists.",
        show_default=False,
    ),
) -> None:
    """Detect .md files not listed in the nav."""
    _validate_only_flag(only)

    if ci or quiet:
        no_header = True
    if ci:
        if output_format == "text":
            output_format = "github-annotations"

    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    repo_root = find_repo_root(search_from=_search_from)
    config, loaded_from_file = ZenzicConfig.load(repo_root)
    if not loaded_from_file and not quiet:
        _shared._print_no_config_hint(output_format)
    config = _shared._apply_engine_override(config, engine)
    if offline:
        config.build_context.offline_mode = True
    if path is not None:
        config, _, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    adapter = get_adapter(config.build_context, docs_root, repo_root)

    t0 = time.monotonic()
    orphans = find_orphans(
        docs_root,
        exclusion_mgr,
        config=config,
        has_engine_config=adapter.has_engine_config(),
        nav_paths=adapter.get_nav_paths(),
        is_locale_dir=adapter.is_locale_dir,
        ignored_patterns=adapter.get_ignored_patterns(),
        adapter=adapter,
    )
    elapsed = time.monotonic() - t0

    findings = [
        Finding(
            rel_path=_rel(docs_root / path),
            line_no=0,
            code="Z402",
            severity=_finding_severity("Z402"),
            message="Physical file not listed in navigation.",
        )
        for path in orphans
    ]
    _append_z620_findings(findings, config, repo_root, check_all=False, check_external_urls=False)
    findings = _filter_flat_findings(findings, only)

    if output_format == "json":
        _shared._output_json_findings(findings, elapsed)
        errors_count = sum(1 for f in findings if f.severity == "error")
        if errors_count:
            raise typer.Exit(1)
        return
    elif output_format == "sarif":
        _engine = _build_rule_engine(config)
        _rules_map = {r.rule_id: r for r in _engine._rules} if _engine else None
        _shared._output_sarif_findings(findings, __version__, rules_map=_rules_map)
        errors_count = sum(1 for f in findings if f.severity == "error")
        if errors_count:
            raise typer.Exit(1)
        return

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)
        if path is not None:
            try:
                _hint = str(docs_root.relative_to(Path.cwd()))
            except ValueError:
                _hint = str(docs_root)
            _shared.console.print(f"[{ZenzicPalette.DIM}]  Scanning: {_hint}[/]")

    reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
    if quiet:
        errors, warnings = reporter.render_quiet(findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(docs_root, repo_root, exclusion_mgr)
        errors, warnings = reporter.render(
            findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            strict=True,
            ok_message="No orphan pages found.",
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(_shared.footer_hint("check")),
        )
    if errors or warnings:
        raise typer.Exit(1)


@check_app.command(name="snippets")
def check_snippets(
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Treat warnings as errors (exit non-zero on any warning).",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except for errors."),
    no_header: bool = typer.Option(
        False, "--no-header", help="Suppress the Zenzic startup banner."
    ),
    path: str | None = typer.Argument(
        None,
        help="Limit to a directory or file. Accepts paths relative to repository root or docs directory. The path must be inside a project with a .git/ directory or .zenzic.toml (root marker); run 'zenzic init' first if no marker exists.",
        show_default=False,
    ),
) -> None:
    """Validate Python code blocks in documentation Markdown files."""
    _validate_only_flag(only)

    if ci or quiet:
        no_header = True
    if ci:
        strict = True
        if output_format == "text":
            output_format = "github-annotations"

    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    repo_root = find_repo_root(search_from=_search_from)
    config, loaded_from_file = ZenzicConfig.load(repo_root)
    if not loaded_from_file and not quiet:
        _shared._print_no_config_hint(output_format)
    if path is not None:
        config, _, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    t0 = time.monotonic()
    snippet_errors = validate_snippets(docs_root, exclusion_mgr, config=config)
    elapsed = time.monotonic() - t0

    findings: list[Finding] = []
    for s_err in snippet_errors:
        src = ""
        if s_err.line_no > 0 and s_err.file_path.is_file():
            try:
                lines = s_err.file_path.read_text(encoding="utf-8").splitlines()
                if 0 < s_err.line_no <= len(lines):
                    src = lines[s_err.line_no - 1].strip()
            except OSError:
                pass
        findings.append(
            Finding(
                rel_path=_rel(s_err.file_path),
                line_no=s_err.line_no,
                code="Z503",
                severity=_finding_severity("Z503"),
                message=s_err.message,
                source_line=src,
            )
        )

    if output_format == "json":
        _shared._output_json_findings(findings, elapsed)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count > 0 or (strict and warnings_count > 0):
            raise typer.Exit(1)
        return
    elif output_format == "sarif":
        _engine = _build_rule_engine(config)
        _rules_map = {r.rule_id: r for r in _engine._rules} if _engine else None
        _shared._output_sarif_findings(findings, __version__, rules_map=_rules_map)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count > 0 or (strict and warnings_count > 0):
            raise typer.Exit(1)
        return

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)
        if path is not None:
            try:
                _hint = str(docs_root.relative_to(Path.cwd()))
            except ValueError:
                _hint = str(docs_root)
            _shared.console.print(f"[{ZenzicPalette.DIM}]  Scanning: {_hint}[/]")

    reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
    if quiet:
        errors, warnings = reporter.render_quiet(findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(docs_root, repo_root, exclusion_mgr)
        errors, warnings = reporter.render(
            findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            ok_message="All code snippets are syntactically valid.",
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(_shared.footer_hint("check")),
        )
    if errors > 0 or (strict and warnings > 0):
        raise typer.Exit(1)


@check_app.command(name="references")
def check_references(
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Treat warnings as errors (exit non-zero on any warning).",
    ),
    links: bool = typer.Option(
        False,
        "--links",
        "-l",
        help="Also validate external HTTP/HTTPS reference URLs via async HEAD requests.",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except for errors."),
    no_header: bool = typer.Option(
        False, "--no-header", help="Suppress the Zenzic startup banner."
    ),
    path: str | None = typer.Argument(
        None,
        help="Limit to a directory or file. Accepts paths relative to repository root or docs directory. The path must be inside a project with a .git/ directory or .zenzic.toml (root marker); run 'zenzic init' first if no marker exists.",
        show_default=False,
    ),
) -> None:
    """Run the Two-Pass Reference Pipeline: harvest definitions, check integrity, run credential scan.

    Pass 1 — Harvest: extract [id]: url definitions, detect secrets (credential scanner).
    Pass 2 — Cross-Check: resolve [text][id] links against the ReferenceMap.
    Pass 3 — Report: compute Reference Integrity score, flag Dead Definitions and Dangling References.

    With --links: validate all external URLs via deduplicated async HEAD requests
    (one ping per unique URL across the entire docs tree).

    Exit codes:
      0 — all references resolve; no secrets found.
      1 — Dangling References or (with --strict) warnings found.
      2 — SECURITY CRITICAL: a secret was detected in a reference URL.
    """
    _validate_only_flag(only)

    if ci or quiet:
        no_header = True
    if ci:
        strict = True
        if output_format == "text":
            output_format = "github-annotations"

    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    repo_root = find_repo_root(search_from=_search_from)
    config, loaded_from_file = ZenzicConfig.load(repo_root)
    if not loaded_from_file and not quiet:
        _shared._print_no_config_hint(output_format)
    if path is not None:
        config, _, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    adapter = get_adapter(config.build_context, docs_root, repo_root)

    _locale_roots = adapter.get_locale_source_roots(repo_root)
    locale_roots: list[tuple[Path, str]] | None = _locale_roots if _locale_roots else None

    _content_roots = adapter.get_extra_content_roots(repo_root)
    content_roots: list[Path] | None = _content_roots if _content_roots else None

    t0 = time.monotonic()
    reports, ext_link_errors = scan_docs_references(
        docs_root,
        exclusion_mgr,
        config=config,
        validate_links=links,
        locale_roots=locale_roots,
        content_roots=content_roots,
    )
    elapsed = time.monotonic() - t0

    findings: list[Finding] = []
    for report in reports:
        rel = _rel(report.file_path)
        _lines: list[str] = []
        if report.file_path.is_file():
            try:
                _lines = report.file_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                pass
        for ref_f in report.findings:
            src = ""
            if _lines and 0 < ref_f.line_no <= len(_lines):
                src = _lines[ref_f.line_no - 1].strip()
            findings.append(
                Finding(
                    rel_path=rel,
                    line_no=ref_f.line_no,
                    code=ref_f.issue,
                    severity=_finding_severity(ref_f.issue),
                    message=ref_f.detail,
                    source_line=src,
                )
            )
        for rule_f in report.rule_findings:
            findings.append(
                Finding(
                    rel_path=rel,
                    line_no=rule_f.line_no,
                    code=rule_f.rule_id,
                    severity=rule_f.severity,
                    message=rule_f.message,
                    source_line=rule_f.matched_line or "",
                    col_start=rule_f.col_start,
                    match_text=rule_f.match_text or "",
                )
            )
        for sf in report.security_findings:
            findings.append(_map_credential_to_finding(sf, repo_root))

    for err_str in ext_link_errors:
        findings.append(
            Finding(
                rel_path="(external-urls)",
                line_no=0,
                code="Z101",
                severity=_finding_severity("Z101"),
                message=err_str,
            )
        )

    if output_format == "json":
        _shared._output_json_findings(findings, elapsed)
        breaches = sum(1 for f in findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count or (strict and warnings_count):
            raise typer.Exit(1)
        return
    elif output_format == "sarif":
        _engine = _build_rule_engine(config)
        _rules_map = {r.rule_id: r for r in _engine._rules} if _engine else None
        _shared._output_sarif_findings(findings, __version__, rules_map=_rules_map)
        breaches = sum(1 for f in findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)
        errors_count = sum(1 for f in findings if f.severity == "error")
        warnings_count = sum(1 for f in findings if f.severity == "warning")
        if errors_count or (strict and warnings_count):
            raise typer.Exit(1)
        return

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)
        if path is not None:
            try:
                _hint = str(docs_root.relative_to(Path.cwd()))
            except ValueError:
                _hint = str(docs_root)
            _shared.console.print(f"[{ZenzicPalette.DIM}]  Scanning: {_hint}[/]")

    reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
    if quiet:
        errors, warnings = reporter.render_quiet(findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(docs_root, repo_root, exclusion_mgr)
        errors, warnings = reporter.render(
            findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            strict=strict,
            ok_message="All references resolved.",
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(_shared.footer_hint("check")),
        )

    breaches = sum(1 for f in findings if f.severity == "security_breach")
    if breaches:
        raise typer.Exit(2)
    if errors or (strict and warnings):
        raise typer.Exit(1)


@check_app.command(name="assets")
def check_assets(
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except for errors."),
    no_header: bool = typer.Option(
        False, "--no-header", help="Suppress the Zenzic startup banner."
    ),
    path: str | None = typer.Argument(
        None,
        help="Limit to a directory or file. Accepts paths relative to repository root or docs directory. The path must be inside a project with a .git/ directory or .zenzic.toml (root marker); run 'zenzic init' first if no marker exists.",
        show_default=False,
    ),
) -> None:
    """Detect unused images and assets in the documentation."""
    _validate_only_flag(only)

    if ci or quiet:
        no_header = True
    if ci:
        if output_format == "text":
            output_format = "github-annotations"

    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    repo_root = find_repo_root(search_from=_search_from)
    config, loaded_from_file = ZenzicConfig.load(repo_root)
    if not loaded_from_file and not quiet:
        _shared._print_no_config_hint(output_format)
    if path is not None:
        config, _, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()

    adapter = get_adapter(config.build_context, docs_root, repo_root)
    adapter_meta = adapter.get_metadata_files()
    _locale_roots = adapter.get_locale_source_roots(repo_root)
    locale_roots: list[tuple[Path, str]] | None = _locale_roots if _locale_roots else None
    _content_roots = adapter.get_extra_content_roots(repo_root)
    content_roots: list[Path] | None = _content_roots if _content_roots else None
    exclusion_mgr = _shared._build_exclusion_manager(
        config, repo_root, docs_root, adapter_metadata_files=adapter_meta
    )

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    t0 = time.monotonic()
    unused = find_unused_assets(
        docs_root,
        exclusion_mgr,
        config=config,
        locale_roots=locale_roots,
        content_roots=content_roots,
        adapter_metadata_files=adapter_meta,
    )
    elapsed = time.monotonic() - t0

    findings = [
        Finding(
            rel_path=_rel(docs_root / path),
            line_no=0,
            code="Z405",
            severity=_finding_severity("Z405"),
            message="File not referenced in any documentation page.",
        )
        for path in unused
    ]
    _append_z620_findings(findings, config, repo_root, check_all=False, check_external_urls=False)
    findings = _filter_flat_findings(findings, only)

    if output_format == "json":
        _shared._output_json_findings(findings, elapsed)
        errors_count = sum(1 for f in findings if f.severity == "error")
        if errors_count:
            raise typer.Exit(1)
        return
    elif output_format == "sarif":
        _engine = _build_rule_engine(config)
        _rules_map = {r.rule_id: r for r in _engine._rules} if _engine else None
        _shared._output_sarif_findings(findings, __version__, rules_map=_rules_map)
        errors_count = sum(1 for f in findings if f.severity == "error")
        if errors_count:
            raise typer.Exit(1)
        return

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)
        if path is not None:
            try:
                _hint = str(docs_root.relative_to(Path.cwd()))
            except ValueError:
                _hint = str(docs_root)
            _shared.console.print(f"[{ZenzicPalette.DIM}]  Scanning: {_hint}[/]")

    reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
    if quiet:
        errors, warnings = reporter.render_quiet(findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(docs_root, repo_root, exclusion_mgr)
        errors, warnings = reporter.render(
            findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            strict=True,
            ok_message="No unused assets found.",
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(_shared.footer_hint("check")),
        )
    if errors or warnings:
        raise typer.Exit(1)


@check_app.command(name="placeholders")
def check_placeholders(
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Treat warnings as errors (exit non-zero on any warning).",
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output except for errors."),
    no_header: bool = typer.Option(
        False, "--no-header", help="Suppress the Zenzic startup banner."
    ),
    path: str | None = typer.Argument(
        None,
        help="Limit to a directory or file. Accepts paths relative to repository root or docs directory. The path must be inside a project with a .git/ directory or .zenzic.toml (root marker); run 'zenzic init' first if no marker exists.",
        show_default=False,
    ),
) -> None:
    """Detect pages with < 50 words or containing TODOs/stubs."""
    _validate_only_flag(only)

    if ci or quiet:
        no_header = True
    if ci:
        strict = True
        if output_format == "text":
            output_format = "github-annotations"

    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    repo_root = find_repo_root(search_from=_search_from)
    config, loaded_from_file = ZenzicConfig.load(repo_root)
    if not loaded_from_file and not quiet:
        _shared._print_no_config_hint()
    if path is not None:
        config, _, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    adapter = get_adapter(config.build_context, docs_root, repo_root)
    _locale_roots = adapter.get_locale_source_roots(repo_root)
    locale_roots: list[tuple[Path, str]] | None = _locale_roots if _locale_roots else None
    _content_roots = adapter.get_extra_content_roots(repo_root)
    content_roots: list[Path] | None = _content_roots if _content_roots else None

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    t0 = time.monotonic()
    raw_findings, _ = scan_docs_references(
        docs_root,
        exclusion_mgr,
        config=config,
        locale_roots=locale_roots,
        content_roots=content_roots,
    )
    elapsed = time.monotonic() - t0

    findings: list[Finding] = []
    for report in raw_findings:
        rel = _rel(report.file_path)
        for rule_f in report.rule_findings:
            if rule_f.rule_id in ("Z501", "Z502"):
                findings.append(
                    Finding(
                        rel_path=rel,
                        line_no=rule_f.line_no,
                        code=rule_f.rule_id,
                        severity=rule_f.severity,
                        message=rule_f.message,
                        source_line=rule_f.matched_line or "",
                        col_start=rule_f.col_start,
                        match_text=rule_f.match_text or "",
                    )
                )
        # harvest() already runs the credential scanner unconditionally as
        # part of scan_docs_references() above; surface its results instead
        # of discarding them. See
        # V031_EXIT2_WIRING_AND_Z406_ADAPTER_AGNOSTICISM_CHECK.
        for sf in report.security_findings:
            findings.append(_map_credential_to_finding(sf, repo_root))

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)
        if path is not None:
            try:
                _hint = str(docs_root.relative_to(Path.cwd()))
            except ValueError:
                _hint = str(docs_root)
            _shared.console.print(f"[{ZenzicPalette.DIM}]  Scanning: {_hint}[/]")

    reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
    if quiet:
        errors, warnings = reporter.render_quiet(findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(docs_root, repo_root, exclusion_mgr)
        errors, warnings = reporter.render(
            findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            strict=strict,
            ok_message="No placeholder stubs found.",
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(_shared.footer_hint("check")),
        )
    incidents = sum(1 for f in findings if f.severity == "security_incident")
    if incidents:
        raise typer.Exit(3)
    breaches = sum(1 for f in findings if f.severity == "security_breach")
    if breaches:
        raise typer.Exit(2)
    if errors > 0 or (strict and warnings > 0):
        raise typer.Exit(1)


# ── All-checks aggregate ──────────────────────────────────────────────────────


@dataclass
class _AllCheckResults:
    link_errors: list[LinkError]
    orphans: list[Path]
    snippet_errors: list[SnippetError]
    unused_assets: list[Path]
    nav_contract_errors: list[str]
    reference_reports: list[IntegrityReport]
    security_events: int
    directory_index_issues: list[Path]
    config_asset_issues: list[tuple[str, str]] = field(default_factory=list)


def _apply_only_filter(results: _AllCheckResults, only_str: str) -> None:
    """Destructively filter CheckResults keeping only the specified Z-codes."""
    if not only_str:
        return
    allowed = frozenset(code.strip().upper() for code in only_str.split(",") if code.strip())
    if not allowed:
        return

    results.link_errors = [e for e in results.link_errors if e.code in allowed]
    if "Z402" not in allowed:
        results.orphans = []
    if "Z503" not in allowed:
        results.snippet_errors = []
    if "Z405" not in allowed:
        results.unused_assets = []
    if "Z406" not in allowed:
        results.nav_contract_errors = []
    if "Z401" not in allowed:
        results.directory_index_issues = []
    if "Z404" not in allowed:
        results.config_asset_issues = []

    for rep in results.reference_reports:
        rep.findings = [f for f in rep.findings if f.issue in allowed]
        rep.rule_findings = [f for f in rep.rule_findings if getattr(f, "rule_id", "") in allowed]
        if "Z201" not in allowed:
            rep.security_findings = []


def _filter_flat_findings(findings: list[Finding], only_str: str | None) -> list[Finding]:
    """Filter a flat list of findings keeping only the specified Z-codes (except fatal config errors Z110, Z111)."""
    if not only_str:
        return findings
    allowed = frozenset(code.strip().upper() for code in only_str.split(",") if code.strip())
    if not allowed:
        return findings
    bypass_codes = {"Z110", "Z111"}
    return [f for f in findings if f.code in allowed or f.code in bypass_codes]


# _apply_per_file_ignores and _apply_directory_policies have moved to _governance.py.
# They are re-imported above and remain accessible from this module for backward
# compatibility with any direct callers (e.g. tests).


def _collect_all_results(
    repo_root: Path,
    docs_root: Path,
    config: ZenzicConfig,
    exclusion_mgr: LayeredExclusionManager,
    strict: bool,
    check_external: bool = True,
    show_progress: bool = False,
    init_start_time: float | None = None,
    rule_engine_target: Path | None = None,
) -> _AllCheckResults:
    """Run all seven checks and return results as a typed container."""

    adapter = get_adapter(config.build_context, docs_root, repo_root)
    _locale_roots = adapter.get_locale_source_roots(repo_root)
    locale_roots: list[tuple[Path, str]] | None = _locale_roots if _locale_roots else None

    _content_roots = adapter.get_extra_content_roots(repo_root)
    content_roots: list[Path] | None = _content_roots if _content_roots else None

    progress = None
    if show_progress:
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=_shared.get_console(),
        )
        progress.start()
        _init_ms = (time.perf_counter() - (init_start_time or time.perf_counter())) * 1000
        progress.add_task(
            f"Initializing environment & VSM... [dim]({_init_ms:.1f}ms)[/dim]",
            total=1,
            completed=1,
        )

    try:
        ref_reports, ext_errors = scan_docs_references(
            docs_root,
            exclusion_mgr,
            config=config,
            validate_links=strict and check_external,
            locale_roots=locale_roots,
            content_roots=content_roots,
            show_progress=show_progress,
            progress_instance=progress,
            rule_engine_target=rule_engine_target,
        )
        security_events = sum(len(r.security_findings) for r in ref_reports)

        config_asset_issues: list[tuple[str, str]] = []
        _engine = config.build_context.engine
        if _engine == "mkdocs":
            config_asset_issues = _mkdocs_check_assets(repo_root)
        elif _engine == "zensical":
            config_asset_issues = _zensical_check_assets(repo_root)

        trackers = {
            r.file_path.resolve(): r.suppression_tracker
            for r in ref_reports
            if r.suppression_tracker is not None
        }

        link_errors = validate_links_structured(
            docs_root,
            exclusion_mgr,
            repo_root=repo_root,
            config=config,
            strict=strict,
            locale_roots=locale_roots,
            check_external=check_external,
            trackers=trackers,
            reports=ref_reports,
            ext_errors=ext_errors,
        )

        for r in ref_reports:
            if r.suppression_tracker is not None:
                dead_lines = {d.line_no for d in r.suppression_tracker.directives if not d.consumed}
                r.rule_findings = [
                    f for f in r.rule_findings if f.rule_id != "Z603" or f.line_no in dead_lines
                ]

        if progress is not None:
            task_orphans = progress.add_task(
                "Checking orphan pages & topology...",
                total=1,
                start=True,
            )
            t0 = time.perf_counter()
            orphans = find_orphans(
                docs_root,
                exclusion_mgr,
                config=config,
                has_engine_config=adapter.has_engine_config(),
                nav_paths=adapter.get_nav_paths(),
                is_locale_dir=adapter.is_locale_dir,
                ignored_patterns=adapter.get_ignored_patterns(),
                adapter=adapter,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            progress.update(
                task_orphans,
                completed=1,
                description=f"Checking orphan pages & topology... [dim]({elapsed_ms:.1f}ms)[/dim]",
            )

            task_snippets = progress.add_task(
                "Validating code snippets...",
                total=1,
                start=True,
            )
            t0 = time.perf_counter()
            snippet_errors = validate_snippets(docs_root, exclusion_mgr, config=config)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            progress.update(
                task_snippets,
                completed=1,
                description=f"Validating code snippets... [dim]({elapsed_ms:.1f}ms)[/dim]",
            )

            task_assets = progress.add_task(
                "Checking unused assets & media...",
                total=1,
                start=True,
            )
            t0 = time.perf_counter()
            unused_assets = find_unused_assets(
                docs_root,
                exclusion_mgr,
                config=config,
                locale_roots=locale_roots,
                content_roots=content_roots,
                adapter_metadata_files=adapter.get_metadata_files(),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            progress.update(
                task_assets,
                completed=1,
                description=f"Checking unused assets & media... [dim]({elapsed_ms:.1f}ms)[/dim]",
            )
        else:
            orphans = find_orphans(
                docs_root,
                exclusion_mgr,
                config=config,
                has_engine_config=adapter.has_engine_config(),
                nav_paths=adapter.get_nav_paths(),
                is_locale_dir=adapter.is_locale_dir,
                ignored_patterns=adapter.get_ignored_patterns(),
                adapter=adapter,
            )
            snippet_errors = validate_snippets(docs_root, exclusion_mgr, config=config)
            unused_assets = find_unused_assets(
                docs_root,
                exclusion_mgr,
                config=config,
                locale_roots=locale_roots,
                content_roots=content_roots,
                adapter_metadata_files=adapter.get_metadata_files(),
            )

        return _AllCheckResults(
            link_errors=link_errors,
            orphans=orphans,
            snippet_errors=snippet_errors,
            unused_assets=unused_assets,
            nav_contract_errors=check_nav_contract(
                repo_root,
                exclusion_mgr,
                engine=config.build_context.engine
                if hasattr(config, "build_context")
                else "mkdocs",
            ),
            reference_reports=ref_reports,
            security_events=security_events,
            directory_index_issues=find_missing_directory_indices(
                docs_root,
                exclusion_mgr,
                config=config,
                provides_index=adapter.provides_index,
            ),
            config_asset_issues=config_asset_issues,
        )
    finally:
        if progress is not None:
            progress.stop()


def _append_z620_findings(
    findings: list[Finding],
    config: ZenzicConfig,
    repo_root: Path,
    check_all: bool,
    check_external_urls: bool,
) -> None:
    tracker = getattr(config, "_global_tracker", None)
    if not tracker:
        return
    for stale in tracker.get_stale_findings(
        check_all=check_all, check_external_urls=check_external_urls
    ):
        try:
            rp = str(stale.file_path.relative_to(repo_root))
        except ValueError:
            rp = str(stale.file_path)
        findings.append(
            Finding(
                rel_path=rp,
                line_no=stale.line_no,
                code=stale.rule_id,
                severity=stale.severity,
                message=stale.message,
            )
        )


def _to_findings(
    results: _AllCheckResults, docs_root: Path, repo_root: Path, config: ZenzicConfig | None = None
) -> list[Finding]:
    """Convert all result types into a flat list of :class:`Finding`."""
    findings: list[Finding] = []

    # Local, call-scoped cache: a file can appear in both snippet_errors and
    # reference_reports (e.g. one page with both a snippet issue and a
    # dangling reference), and each category independently re-reads the file
    # for `source_line` context. This dedupes reads *within this call only*
    # — deduping across the seven independent sub-checks in
    # _collect_all_results would require scanner.py/validator.py to expose
    # raw file content on their result objects, which they don't; that's a
    # larger, out-of-scope change tracked separately.
    _content_cache: dict[Path, list[str] | None] = {}

    def _cached_lines(path: Path) -> list[str] | None:
        if path not in _content_cache:
            try:
                _content_cache[path] = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                _content_cache[path] = None
        return _content_cache[path]

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    for err in results.link_errors:
        findings.append(
            Finding(
                rel_path=_rel(err.file_path),
                line_no=err.line_no,
                code=err.code,
                severity=_finding_severity(err.code),
                message=err.message,
                source_line=err.source_line,
                col_start=err.col_start,
                match_text=err.match_text,
            )
        )

    for path in results.orphans:
        findings.append(
            Finding(
                rel_path=_rel(docs_root / path),
                line_no=0,
                code="Z402",
                severity=_finding_severity("Z402"),
                message="Physical file not listed in navigation.",
            )
        )

    for s_err in results.snippet_errors:
        src = ""
        if s_err.line_no > 0:
            lines = _cached_lines(s_err.file_path)
            if lines and 0 < s_err.line_no <= len(lines):
                src = lines[s_err.line_no - 1].strip()
        findings.append(
            Finding(
                rel_path=_rel(s_err.file_path),
                line_no=s_err.line_no,
                code="Z503",
                severity=_finding_severity("Z503"),
                message=s_err.message,
                source_line=src,
            )
        )

    for path in results.unused_assets:
        findings.append(
            Finding(
                rel_path=_rel(docs_root / path),
                line_no=0,
                code="Z405",
                severity=_finding_severity("Z405"),
                message="File not referenced in any documentation page.",
            )
        )

    for msg in results.nav_contract_errors:
        findings.append(
            Finding(
                rel_path="(nav)",
                line_no=0,
                code="Z406",
                severity=_finding_severity("Z406"),
                message=msg,
            )
        )

    for report in results.reference_reports:
        rel = _rel(report.file_path)
        _lines = _cached_lines(report.file_path) or []
        for ref_f in report.findings:
            src = ""
            if _lines and 0 < ref_f.line_no <= len(_lines):
                src = _lines[ref_f.line_no - 1].strip()
            findings.append(
                Finding(
                    rel_path=rel,
                    line_no=ref_f.line_no,
                    code=ref_f.issue,
                    severity=_finding_severity(ref_f.issue),
                    message=ref_f.detail,
                    source_line=src,
                )
            )
        for rule_f in report.rule_findings:
            if rule_f.rule_id in (
                "Z101",
                "Z102",
                "Z103",
                "Z104",
                "Z105",
                "Z106",
                "Z108",
                "Z112",
                "Z120",
                "Z121",
                "Z122",
                "Z123",
                "Z124",
                "Z202",
                "Z203",
                "Z205",
            ):
                continue
            findings.append(
                Finding(
                    rel_path=rel,
                    line_no=rule_f.line_no,
                    code=rule_f.rule_id,
                    severity=rule_f.severity,
                    message=rule_f.message,
                    source_line=rule_f.matched_line,
                    col_start=rule_f.col_start,
                    match_text=rule_f.match_text,
                )
            )

        for sf in report.security_findings:
            findings.append(_map_credential_to_finding(sf, repo_root))

    for dir_path in results.directory_index_issues:
        findings.append(
            Finding(
                rel_path=_rel(docs_root / dir_path),
                line_no=0,
                code="Z401",
                severity=_finding_severity("Z401"),
                message=(
                    "Directory contains Markdown files but has no index page — "
                    "the directory URL may return a 404."
                ),
            )
        )

    for rel_path, message in results.config_asset_issues:
        findings.append(
            Finding(
                rel_path=rel_path,
                line_no=0,
                code="Z404",
                severity=_finding_severity("Z404"),
                message=message,
            )
        )

    return findings


# ── Target helpers (file or directory) ─────────────────────────────────────────
# _resolve_target and _apply_target have moved to _target_resolver.py.
# They are re-imported above and remain accessible from this module for
# backward compatibility with any direct callers.


@check_app.command(name="all")
def check_all(
    strict: bool | None = typer.Option(
        None, "--strict", "-s", help="Treat warnings as errors (exit non-zero on any warning)."
    ),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text, json, or sarif."
    ),
    ci: bool = typer.Option(
        False, "--ci", help="Run in CI mode (forces github-annotations and strict)."
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated list of Z-Codes to filter. Findings not matching these codes are discarded.",
    ),
    exit_zero: bool | None = typer.Option(
        None, "--exit-zero", help="Always exit 0; report issues without failing."
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Minimal one-line output for pre-commit hooks."
    ),
    engine: str | None = typer.Option(
        None,
        "--engine",
        help="Override the build engine adapter (e.g. mkdocs, zensical). "
        "Auto-detected from .zenzic.toml when omitted.",
        metavar="ENGINE",
    ),
    exclude_dir: list[str] | None = typer.Option(
        None,
        "--exclude-dir",
        help="Additional directories to exclude from scanning (repeatable).",
        metavar="DIR",
    ),
    include_dir: list[str] | None = typer.Option(
        None,
        "--include-dir",
        help="Directories to force-include even if excluded by config (repeatable). "
        "Cannot override system guardrails.",
        metavar="DIR",
    ),
    path: str | None = typer.Argument(
        None,
        metavar="PATH",
        help=(
            "Limit audit to a single Markdown file or an entire directory. "
            "Accepts paths relative to the repository root or to the docs directory. "
            "File examples: README.md, docs/index.md. "
            "Directory examples: content/, docs/guide/. "
            "When a directory is given, the configured docs directory is patched to that path and all "
            "Markdown files inside it are audited."
        ),
        show_default=False,
    ),
    show_info: bool = typer.Option(
        False, "--show-info", help="Show info-level findings (e.g. circular links) in the report."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Force flat URL resolution for offline builds."
    ),
    no_external: bool = typer.Option(
        False,
        "--no-external",
        help=(
            "Skip HTTP validation of external URLs (Pass 3). "
            "For air-gapped / offline environments. "
            "Credential scanner (Z201) always active regardless of this flag."
        ),
    ),
    exclude_url: list[str] = typer.Option(
        [],
        "--exclude-url",
        help=(
            "Bypass external URL validation for URLs matching this prefix (repeatable). "
            "Merged with excluded_external_urls from .zenzic.toml at runtime."
        ),
        metavar="PREFIX",
    ),
    audit: bool = typer.Option(
        False,
        "--audit",
        help=(
            "Sovereign truth-seeking mode: ignore all suppressible bypasses "
            "(inline zenzic-ignore and governance.per_file_ignores)."
        ),
    ),
    no_header: bool = typer.Option(
        False,
        "--no-header",
        help="Suppress the Zenzic ASCII art header.",
    ),
    update_baseline: bool = typer.Option(
        False,
        "--update-baseline",
        help="Generate or overwrite the baseline snapshot file (.zenzic-baseline.json).",
    ),
    baseline: str | None = typer.Option(
        None,
        "--baseline",
        help="Path to a baseline snapshot file to consume (defaults to .zenzic-baseline.json if present in workspace root).",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        help=(
            "Explicit path to a Zenzic TOML config file, bypassing the normal "
            ".zenzic.toml / pyproject.toml discovery. Does not have to live under "
            "the repository root."
        ),
        metavar="PATH",
    ),
) -> None:
    """Run all checks: links, orphans, snippets, placeholders, assets, references.

    Optionally pass PATH to scope the audit to a single Markdown file or a custom
    directory (e.g. ``README.md``, ``content/``).  Zenzic auto-selects the
    StandaloneAdapter when the target lives outside the configured docs directory.
    """
    _t_init_start = time.perf_counter()
    _validate_only_flag(only)

    # GAP-04: Conflict validation — --strict and --exit-zero are mutually exclusive.
    # Plain CLI-usage error: Exit 1, not Exit 2 (reserved for security breaches
    # per the Tier-0 Exit Code Contract).
    if strict and exit_zero:
        typer.echo(
            "ERROR: --strict and --exit-zero are mutually exclusive. "
            "--strict promotes warnings to errors; --exit-zero suppresses all exit codes.",
            err=True,
        )
        raise typer.Exit(1)

    if ci:
        strict = True
        no_header = True
        if output_format == "text":
            output_format = "github-annotations"

    # CEO-052 "The Sovereign Root Fix": when an explicit target PATH is given,
    # derive repo_root by searching upward FROM that path — not from CWD.
    # "The configuration follows the target, not the caller."
    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre
    _config_file_override = Path(config_path).resolve() if config_path else None
    try:
        repo_root = find_repo_root(search_from=_search_from)
        config, loaded_from_file = ZenzicConfig.load(repo_root, config_file=_config_file_override)
    except RuntimeError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(1) from exc
    if not loaded_from_file and not quiet:
        _shared._print_no_config_hint(output_format)
    config = _shared._apply_engine_override(config, engine)
    if offline:
        config.build_context.offline_mode = True
    if exclude_url:
        config = config.model_copy(
            update={"excluded_external_urls": config.excluded_external_urls + list(exclude_url)}
        )

    if not quiet and not no_header and output_format == "text":
        _shared._ui.print_header(__version__)

    _single_file: Path | None = None
    _target_hint: str | None = None
    if path is not None:
        config, _single_file, _, _target_hint = _apply_target(repo_root, config, path)

    docs_root = (repo_root / config.docs_dir).resolve()
    # CEO-043: explicit target may live outside the CWD repo root.
    # Adopt the target as the sovereign sandbox so the path traversal guard
    # rejects escapes FROM the target, not the location OF the target.
    try:
        docs_root.relative_to(repo_root)
    except ValueError:
        repo_root = docs_root
    exclusion_mgr = _shared._build_exclusion_manager(
        config,
        repo_root,
        docs_root,
        exclude_dirs=exclude_dir,
        include_dirs=include_dir,
    )

    effective_strict = strict if strict is not None else config.strict
    effective_exit_zero = exit_zero if exit_zero is not None else config.exit_zero

    t0 = time.monotonic()
    inline_suppressions, inline_hotspots = collect_inline_suppression_stats(
        docs_root, config, exclusion_mgr
    )
    per_file_suppressions = count_per_file_ignores(config)
    suppression_audit = SuppressionAudit(
        inline_count=inline_suppressions,
        per_file_count=per_file_suppressions,
        cap=config.governance.suppression_cap,
        inline_hotspots=inline_hotspots,
    )

    if (
        config.governance.suppression_cap_fail_hard
        and suppression_audit.total > suppression_audit.cap
    ):
        if output_format == "json":
            print(json.dumps(build_cap_exceeded_json_payload(suppression_audit), indent=2))
        elif output_format == "sarif":
            print(
                json.dumps(
                    build_cap_exceeded_sarif_payload(suppression_audit, version=__version__),
                    indent=2,
                )
            )
        elif output_format == "github-annotations":
            print(
                f"::error title=Zenzic::Suppression CAP exceeded: {suppression_audit.total} > {suppression_audit.cap}"
            )
        elif output_format == "text":
            if not quiet:
                _shared.console.print()
            print_governance_cap_failure(
                suppression_audit,
                title=resolve_governance_panel_title(repo_root),
            )
        raise typer.Exit(1)

    show_progress = not (ci or no_header or quiet or output_format != "text")

    with sovereign_context(force_audit=audit):
        results = _collect_all_results(
            repo_root,
            docs_root,
            config,
            exclusion_mgr,
            strict=effective_strict,
            check_external=not no_external,
            show_progress=show_progress,
            init_start_time=_t_init_start,
            rule_engine_target=_single_file,
        )

    if only:
        _apply_only_filter(results, only)

    elapsed = time.monotonic() - t0

    with sovereign_context(force_audit=audit):
        all_findings = _to_findings(results, docs_root, repo_root, config)
        all_findings = _apply_per_file_ignores(all_findings, config)
        all_findings = _apply_directory_policies(all_findings, config)
        _append_z620_findings(
            all_findings, config, repo_root, check_all=True, check_external_urls=True
        )
        if only:
            all_findings = _filter_flat_findings(all_findings, only)

    if _single_file is not None:
        _sf_rel = str(_single_file.relative_to(repo_root))
        all_findings = [f for f in all_findings if f.rel_path == _sf_rel]

    # ── Baseline Handling ──────────────────────────────────────────────────────
    baseline_file_path = Path(baseline) if baseline else (repo_root / DEFAULT_BASELINE_FILE)

    _findings_counts: dict[str, int] = {}
    for _f in all_findings:
        _findings_counts[_f.code] = _findings_counts.get(_f.code, 0) + 1

    # DQS scope parity: Z-code finding penalties above are already scoped to
    # _single_file (all_findings was filtered before this point). The
    # suppression/technical-debt penalty must match that scope instead of
    # always reflecting the whole project — otherwise a single-file scan
    # silently mixes "this file's findings" with "the whole project's debt",
    # an undocumented hybrid a user has no way to detect from the score
    # alone. suppression_audit itself (used for the CAP fail-hard gate above,
    # and passed as-is to SARIF/text reporting) stays project-wide on
    # purpose: the suppression cap is a project-level governance ceiling,
    # not a per-file concept. Only the score/JSON-payload view is rescoped.
    _score_suppression_audit = suppression_audit
    if _single_file is not None:
        try:
            _sf_rel_for_score = str(_single_file.relative_to(docs_root))
        except ValueError:
            # Target lives outside docs_root (e.g. CHANGELOG.md at repo root) —
            # inline_hotspots is keyed relative to docs_root, so a target
            # outside it cannot carry an inline suppression by construction.
            _sf_inline_count = 0
        else:
            _sf_inline_count = suppression_audit.inline_hotspots.get(_sf_rel_for_score, 0)
        _score_suppression_audit = SuppressionAudit(
            inline_count=_sf_inline_count,
            per_file_count=0,
            cap=suppression_audit.cap,
            inline_hotspots=({_sf_rel_for_score: _sf_inline_count} if _sf_inline_count else {}),
        )

    _score_report = compute_score(
        _findings_counts,
        suppression_count=_score_suppression_audit.total,
        suppression_cap=_score_suppression_audit.cap,
    )

    if update_baseline:
        bdata = BaselineManager.create_baseline(
            _score_report.score, all_findings, version_str=__version__
        )
        BaselineManager.save_baseline(bdata, baseline_file_path)
        if not quiet and output_format == "text":
            _shared.console.print(
                f"[bold green]✓ Baseline snapshot saved to {baseline_file_path.name}[/bold green] "
                f"[{ZenzicPalette.DIM}](score: {_score_report.score}/100, {len(bdata.signatures)} finding{'s' if len(bdata.signatures) != 1 else ''})[/]"
            )

    active_baseline = None
    if baseline_file_path.is_file():
        try:
            active_baseline = BaselineManager.load_baseline(baseline_file_path)
            BaselineManager.apply_baseline(all_findings, active_baseline)
        except Exception as exc:
            if baseline is not None:
                typer.echo(
                    f"ERROR: Failed to load baseline '{baseline_file_path}': {exc}", err=True
                )
                raise typer.Exit(1) from None

    elapsed = time.monotonic() - t0

    if output_format == "json":
        _shared._output_check_all_json_findings(
            results, all_findings, repo_root, docs_root, config, _score_suppression_audit
        )

        incidents = sum(1 for f in all_findings if f.severity == "security_incident")
        if incidents:
            raise typer.Exit(3)
        breaches = sum(1 for f in all_findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)

        if active_baseline is not None and not effective_exit_zero:
            unbaselined = sum(
                1 for f in all_findings if not f.is_baselined and f.severity == "error"
            )
            if unbaselined or _score_report.score < active_baseline.score:
                raise typer.Exit(1)
        elif not effective_exit_zero:
            errors_count = sum(1 for f in all_findings if f.severity == "error")
            if errors_count:
                raise typer.Exit(1)
        return
    elif output_format == "sarif":
        _engine = _build_rule_engine(config)
        _rules_map = {r.rule_id: r for r in _engine._rules} if _engine else None
        _shared._output_sarif_findings(all_findings, __version__, rules_map=_rules_map)
        incidents = sum(1 for f in all_findings if f.severity == "security_incident")
        if incidents:
            raise typer.Exit(3)
        breaches = sum(1 for f in all_findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)

        if active_baseline is not None and not effective_exit_zero:
            unbaselined = sum(
                1 for f in all_findings if not f.is_baselined and f.severity == "error"
            )
            if unbaselined or _score_report.score < active_baseline.score:
                raise typer.Exit(1)
        elif not effective_exit_zero:
            errors_count = sum(1 for f in all_findings if f.severity == "error")
            if errors_count:
                raise typer.Exit(1)
        return
    elif output_format == "github-annotations":
        _shared._output_github_annotations(all_findings)

        incidents = sum(1 for f in all_findings if f.severity == "security_incident")
        if incidents:
            raise typer.Exit(3)
        breaches = sum(1 for f in all_findings if f.severity == "security_breach")
        if breaches:
            raise typer.Exit(2)

        if active_baseline is not None and not effective_exit_zero:
            unbaselined = sum(
                1
                for f in all_findings
                if not f.is_baselined
                and (f.severity == "error" or (effective_strict and f.severity == "warning"))
            )
            if unbaselined or _score_report.score < active_baseline.score:
                raise typer.Exit(1)
        elif not effective_exit_zero:
            errors_count = sum(1 for f in all_findings if f.severity == "error")
            warnings_count = sum(1 for f in all_findings if f.severity == "warning")
            if errors_count > 0 or (effective_strict and warnings_count > 0):
                raise typer.Exit(1)
        return

    if quiet:
        reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
        errors, warnings = reporter.render_quiet(all_findings)
    else:
        docs_count, assets_count = _shared._count_docs_assets(
            docs_root, repo_root, exclusion_mgr, config
        )
        if _single_file is not None:
            docs_count, assets_count = 1, 0

        if docs_count == 0 and _single_file is None:
            _target_display = _target_hint or "./"
            _shared.console.print(
                f"[bold yellow]\u26a0 Z906 NO_FILES_FOUND[/bold yellow] — "
                f"No Markdown sources found in [cyan]{_target_display}[/cyan]. "
                "Audit skipped."
            )
            return

        _footer_lines = [_shared.footer_hint("check")]
        if no_external:
            _footer_lines.append(
                f"[{ZenzicPalette.DIM}]💡 External link validation skipped (--no-external). "
                f"Credential scanner (Z201) remains active.[/]"
            )

        if active_baseline is not None:
            baselined_cnt = sum(1 for f in all_findings if f.is_baselined)
            new_cnt = sum(1 for f in all_findings if not f.is_baselined)
            fixed_cnt = max(0, active_baseline.findings_count - baselined_cnt)
            _footer_lines.append(
                f"[{ZenzicPalette.DIM}]Baseline: {active_baseline.score}/100 "
                f"({baselined_cnt} baselined, {new_cnt} new)[/]"
            )
            if fixed_cnt > 0:
                if fixed_cnt > 50 and new_cnt == 0:
                    _footer_lines.append(
                        f"[{ZenzicPalette.SUCCESS}]✨ Massive technical debt reduction detected ({fixed_cnt} issues resolved). "
                        f"Baseline is stale. Run 'zenzic check all --update-baseline' to lock in this clean state.[/]"
                    )
                else:
                    _footer_lines.append(
                        f"[{ZenzicPalette.SUCCESS}]💡 {fixed_cnt} baselined issue{'s' if fixed_cnt != 1 else ''} resolved! "
                        f"Run 'zenzic check --update-baseline' to refresh baseline.[/]"
                    )

        if _score_report.security_override:
            _dqs_line = (
                f"[bold red]DQS Final Score: 0/100[/bold red] "
                f"[{ZenzicPalette.DIM}](Security Override — "
                f"{_score_report.security_findings} non-suppressible finding"
                f"{'s' if _score_report.security_findings != 1 else ''} detected)[/]"
            )
        else:
            # Non-suppressible security findings always fail regardless of
            # baseline; plain errors and strict-promoted warnings are
            # baseline-sensitive, matching the real exit-code decision
            # (unbaselined_defects, below) and reporter.py's baseline_active
            # verdict fix (same bug shape, one screen away).
            if active_baseline is not None:
                _pre_errors = sum(
                    1 for _f in all_findings if _f.severity == "error" and not _f.is_baselined
                )
                _pre_warnings = sum(
                    1 for _f in all_findings if _f.severity == "warning" and not _f.is_baselined
                )
            else:
                _pre_errors = sum(1 for _f in all_findings if _f.severity == "error")
                _pre_warnings = sum(1 for _f in all_findings if _f.severity == "warning")
            _pre_breaches = sum(
                1 for _f in all_findings if _f.severity in {"security_breach", "security_incident"}
            )
            _gate_failed = (
                _pre_breaches > 0 or _pre_errors > 0 or (effective_strict and _pre_warnings > 0)
            )
            _gate_label = "Gate Failed" if _gate_failed else "Gate Passed"
            _gate_style = ZenzicPalette.ERROR if _gate_failed else ZenzicPalette.SUCCESS
            _dqs_line = (
                f"[bold {_gate_style}]DQS Final Score: "
                f"{_score_report.score}/100[/bold {_gate_style}] "
                f"[{ZenzicPalette.DIM}]({_gate_label})[/]"
            )
        _footer_lines.insert(0, _dqs_line)

        reporter = ZenzicReporter(_shared.console, docs_root, docs_dir=str(config.docs_dir))
        errors, warnings = reporter.render(
            all_findings,
            version=__version__,
            elapsed=elapsed,
            docs_count=docs_count,
            assets_count=assets_count,
            engine=config.build_context.engine if hasattr(config, "build_context") else "auto",
            target=_target_hint,
            strict=effective_strict,
            show_info=show_info,
            footer_notice=_shared.make_footer_notice(*_footer_lines),
            baseline_active=active_baseline is not None,
        )

    if output_format == "text" and not quiet:
        print_suppression_audit_footer(
            suppression_audit, audit_mode=audit, scoped_to_single_file=_single_file is not None
        )

    incidents = sum(1 for f in all_findings if f.severity == "security_incident")
    if incidents:
        raise typer.Exit(3)
    breaches = sum(1 for f in all_findings if f.severity == "security_breach")
    if breaches:
        raise typer.Exit(2)

    if active_baseline is not None:
        unbaselined_defects = sum(
            1
            for f in all_findings
            if not f.is_baselined
            and (f.severity == "error" or (effective_strict and f.severity == "warning"))
        )
        score_regressed = _score_report.score < active_baseline.score
        if (score_regressed or unbaselined_defects > 0) and not effective_exit_zero:
            raise typer.Exit(1)
    else:
        has_failures = (errors > 0) or (effective_strict and warnings > 0)
        if has_failures and not effective_exit_zero:
            raise typer.Exit(1)
