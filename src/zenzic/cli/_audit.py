# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic Governance Audit Command (`zenzic audit`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from zenzic import __version__
from zenzic.cli import _shared
from zenzic.cli._check import (
    _append_z118_findings,
    _apply_only_filter,
    _collect_all_results,
    _filter_flat_findings,
    _to_findings,
)
from zenzic.cli._governance import (
    SuppressionAudit,
    _apply_directory_policies,
    _apply_per_file_ignores,
    collect_inline_suppression_stats,
    count_per_file_ignores,
)
from zenzic.cli._shared import (
    _count_docs_assets,
)
from zenzic.core.adapters import get_adapter
from zenzic.core.baseline import DEFAULT_BASELINE_FILE, BaselineManager
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.scanner import _build_rule_engine
from zenzic.core.scorer import compute_score
from zenzic.core.sovereign_context import sovereign_context
from zenzic.core.ui import ZenzicPalette
from zenzic.models.config import ZenzicConfig


def audit(
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            "-s",
            help="Treat warnings as errors (exit non-zero on any warning).",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text or json."),
    ] = "text",
    no_external: Annotated[
        bool,
        typer.Option(
            "--no-external",
            help="Skip HTTP validation of external URLs for air-gapped / offline builds.",
        ),
    ] = False,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Force flat URL resolution for offline builds."),
    ] = False,
    only: Annotated[
        str | None,
        typer.Option(
            "--only",
            help="Comma-separated list of Z-Codes to include in audit findings.",
        ),
    ] = None,
    baseline: Annotated[
        str | None,
        typer.Option("--baseline", help="Path to custom baseline snapshot file."),
    ] = None,
    ci: Annotated[
        bool,
        typer.Option("--ci", help="Run in CI mode."),
    ] = False,
) -> None:
    """Generate a formal compliance audit report detailing active policies, DQS score, technical debt, and architectural state."""
    repo_root = Path.cwd()
    config, _ = ZenzicConfig.load(repo_root)

    if offline and config.build_context.offline_mode is not True:
        config.build_context.offline_mode = True

    docs_root = repo_root / config.docs_dir
    if not docs_root.is_dir():
        docs_root = repo_root

    exclusion_mgr = LayeredExclusionManager(config=config, repo_root=repo_root)
    effective_strict = strict or ci

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

    with sovereign_context(force_audit=False):
        results = _collect_all_results(
            repo_root,
            docs_root,
            config,
            exclusion_mgr,
            strict=effective_strict,
            check_external=not no_external,
            show_progress=False,
        )

    if only:
        _apply_only_filter(results, only)

    with sovereign_context(force_audit=False):
        all_findings = _to_findings(results, docs_root, repo_root, config)
        all_findings = _apply_per_file_ignores(all_findings, config)
        all_findings = _apply_directory_policies(all_findings, config)
        _append_z118_findings(
            all_findings, config, repo_root, check_all=True, check_external_urls=not no_external
        )
        if only:
            all_findings = _filter_flat_findings(all_findings, only)

    baseline_file_path = Path(baseline) if baseline else (repo_root / DEFAULT_BASELINE_FILE)
    if baseline_file_path.is_file():
        try:
            active_baseline = BaselineManager.load_baseline(baseline_file_path)
            BaselineManager.apply_baseline(all_findings, active_baseline)
        except Exception:
            pass

    findings_counts: dict[str, int] = {}
    for f in all_findings:
        findings_counts[f.code] = findings_counts.get(f.code, 0) + 1

    score_report = compute_score(
        findings_counts,
        suppression_count=suppression_audit.total,
        suppression_cap=suppression_audit.cap,
    )

    docs_count, assets_count = _count_docs_assets(docs_root, repo_root, exclusion_mgr)
    adapter = get_adapter(config.build_context, docs_root, repo_root)
    engine = _build_rule_engine(config)

    # Architectural state
    custom_rules_loaded = []
    if engine is not None and hasattr(engine, "_rules"):
        for r in engine._rules:
            meta = getattr(r, "metadata", None)
            if meta:
                custom_rules_loaded.append(
                    {
                        "code": getattr(meta, "code", r.rule_id),
                        "title": getattr(meta, "title", r.rule_id),
                        "category": getattr(meta, "category", "custom"),
                        "penalty": getattr(meta, "penalty", 1.0),
                    }
                )
            elif hasattr(r, "rule_id"):
                custom_rules_loaded.append(
                    {
                        "code": r.rule_id,
                        "title": r.rule_id,
                        "category": "custom",
                        "penalty": 1.0,
                    }
                )

    errors_count = sum(1 for f in all_findings if f.severity == "error")
    warnings_count = sum(1 for f in all_findings if f.severity == "warning")
    info_count = sum(1 for f in all_findings if f.severity in ("info", "note"))
    security_count = sum(
        1 for f in all_findings if f.severity in ("security_breach", "security_incident")
    )

    pass_status = (
        "FAIL"
        if (
            security_count > 0
            or (
                config.governance.suppression_cap_fail_hard
                and suppression_audit.total > suppression_audit.cap
            )
            or (effective_strict and (errors_count > 0 or warnings_count > 0))
            or (errors_count > 0)
        )
        else "PASS"
    )

    # ── Output Formats ────────────────────────────────────────────────────────
    if output_format == "json":
        audit_payload = {
            "audit_version": __version__,
            "executive_summary": {
                "status": pass_status,
                "score": score_report.score,
                "total_files": docs_count + assets_count,
                "docs_count": docs_count,
                "assets_count": assets_count,
                "debt_status": suppression_audit.debt_status,
            },
            "governance_policies": {
                "required_frontmatter_keys": config.policies.required_frontmatter_keys,
                "forbidden_external_domains": config.policies.forbidden_external_domains,
                "suppression_cap": config.governance.suppression_cap,
                "suppression_cap_fail_hard": config.governance.suppression_cap_fail_hard,
                "active_suppressions": suppression_audit.total,
                "policy_violations": sum(1 for f in all_findings if f.code in ("Z610", "Z611")),
            },
            "technical_debt_ledger": {
                "inline_suppressions": suppression_audit.inline_count,
                "per_file_ignores": suppression_audit.per_file_count,
                "directory_policies": len(config.governance.directory_policies),
                "suppression_debt_pts": suppression_audit.excess,
                "total_debt_penalty": score_report.suppression_debt_pts,
                "debt_status": suppression_audit.debt_status,
                "hotspots": [
                    {"path": path, "count": count}
                    for path, count in suppression_audit.top_offenders(limit=5)
                ],
            },
            "architectural_state": {
                "engine": config.build_context.engine,
                "adapter": adapter.__class__.__name__,
                "custom_rules": custom_rules_loaded,
                "active_rule_count": len(engine._rules)
                if engine and hasattr(engine, "_rules")
                else 0,
            },
            "findings_summary": {
                "security_violations": security_count,
                "error": errors_count,
                "warning": warnings_count,
                "info": info_count,
            },
        }
        print(json.dumps(audit_payload, indent=2))

        if pass_status == "FAIL":
            raise typer.Exit(1)
        return

    # Text format (Terminal Rich UI)
    console = _shared.console
    console.print()

    title_str = f"[bold {ZenzicPalette.BRAND}]# ZENZIC GOVERNANCE AUDIT REPORT v{__version__}[/]"
    console.print(title_str)
    console.print(
        f"[{ZenzicPalette.DIM}]Engine-agnostic Markdown static analyzer & compliance auditor[/]"
    )
    console.print()

    # Panel 1: Executive Summary
    status_color = "green" if pass_status == "PASS" else "red"
    summary_text = (
        f"• Status: [bold {status_color}]{pass_status}[/bold {status_color}]\n"
        f"• Quality Score: [bold cyan]{score_report.score}/100[/bold cyan] (Base: 100)\n"
        f"• Workspace Coverage: [bold]{docs_count}[/] docs, [bold]{assets_count}[/] assets ({docs_count + assets_count} files total)\n"
        f"• Technical Debt Posture: [bold yellow]{suppression_audit.debt_status}[/] ({suppression_audit.total}/{suppression_audit.cap} suppressions)"
    )
    console.print(
        _shared._ui.make_panel(summary_text, title="Executive Summary", border_style="cyan")
    )

    # Panel 2: Governance Policies
    fm_keys_str = (
        ", ".join(config.policies.required_frontmatter_keys)
        if config.policies.required_frontmatter_keys
        else "None configured"
    )
    domains_str = (
        ", ".join(config.policies.forbidden_external_domains)
        if config.policies.forbidden_external_domains
        else "None configured"
    )
    z610_violations = sum(1 for f in all_findings if f.code == "Z610")
    z611_violations = sum(1 for f in all_findings if f.code == "Z611")

    policies_text = (
        f"• Required Frontmatter Keys: [bold]{fm_keys_str}[/] "
        f"([{'red' if z610_violations else 'green'}]{z610_violations} violations[/])\n"
        f"• Forbidden External Domains: [bold]{domains_str}[/] "
        f"([{'red' if z611_violations else 'green'}]{z611_violations} violations[/])\n"
        f"• Global Suppression Cap: [bold]{config.governance.suppression_cap}[/] "
        f"(Fail-Hard: [bold]{config.governance.suppression_cap_fail_hard}[/], Active: [bold]{suppression_audit.total}[/])"
    )
    console.print(
        _shared._ui.make_panel(
            policies_text, title="Governance Policies ([policies])", border_style="magenta"
        )
    )

    # Panel 3: Technical Debt Ledger
    debt_text = (
        f"• Inline Comments (`<!-- zenzic-ignore -->`): [bold]{suppression_audit.inline_count}[/]\n"
        f"• Per-File Ignores (`.zenzic.toml`): [bold]{suppression_audit.per_file_count}[/]\n"
        f"• Directory Policies: [bold]{len(config.governance.directory_policies)}[/] configured\n"
        f"• Debt Points Penalty: [bold red]-{score_report.suppression_debt_pts} pts[/]"
    )
    if suppression_audit.top_offenders():
        debt_text += "\n• Top Suppression Hotspots:\n" + "\n".join(
            f"  - {path}: {count} ignore(s)"
            for path, count in suppression_audit.top_offenders(limit=3)
        )
    console.print(
        _shared._ui.make_panel(debt_text, title="Technical Debt Ledger", border_style="yellow")
    )

    # Panel 4: Architectural State
    custom_rules_str = (
        ", ".join(str(r["code"]) for r in custom_rules_loaded)
        if custom_rules_loaded
        else "None loaded"
    )
    arch_text = (
        f"• Build Engine: [bold]{config.build_context.engine}[/]\n"
        f"• Active Adapter: [bold]{adapter.__class__.__name__}[/]\n"
        f"• Custom SDK v3 Rules: [bold]{custom_rules_str}[/]\n"
        f"• Total Active Rules: [bold]{len(engine._rules) if engine and hasattr(engine, '_rules') else 0}[/] checks"
    )
    console.print(
        _shared._ui.make_panel(arch_text, title="Architectural State", border_style="blue")
    )

    console.print()
    if pass_status == "FAIL":
        raise typer.Exit(1)
