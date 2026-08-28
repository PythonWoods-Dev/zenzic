# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Inspect sub-commands: introspect the Zenzic scanner arsenal and plugin registry."""

from __future__ import annotations

import typer
from rich import box
from rich.table import Table
from rich.text import Text

from zenzic.core.codes import CODE_DEFINITIONS, CODE_NAMES, CORE_SCANNERS
from zenzic.core.scanner import find_repo_root
from zenzic.core.ui import ZenzicPalette
from zenzic.models.config import ZenzicConfig

from . import _shared
from ._metadata import COMMAND_BY_NAME


inspect_app = _shared.create_app(
    name="inspect",
    long_help=(f"[bold {ZenzicPalette.BRAND}]Inspect[/] — {COMMAND_BY_NAME['inspect'].long_help}"),
)


def _inspect_capabilities() -> None:
    """Show the full Zenzic scanner arsenal.

    **Section A — Core Scanners (Built-in):** 16 scanners compiled into
    Zenzic itself.  The credential scanner (Z201) exits with code 2; the path
    traversal guard's fatal check (Z203, OS system directories) exits with code 3.
    Z202 (ordinary docs-root-boundary traversal) is also non-suppressible but stays
    at plain Exit 1 — it is deliberately not escalated to Exit 3.
    None of these four are suppressible with ``--exit-zero``.

    **Section B — Extensible Rules (Plugin System):** rules registered via the
    ``zenzic.rules`` entry-point group from any installed third-party package.
    """
    from zenzic import __version__
    from zenzic.core.rules import list_plugin_rules

    _shared._ui.print_header(__version__)
    _shared.console.print()

    # ── Section A: Core Scanners ──────────────────────────────────────────
    core_table = Table(
        title=f"[bold {ZenzicPalette.BRAND}]Core Scanners[/]  [{ZenzicPalette.DIM}](built-in)[/]",
        title_justify="left",
        box=box.ROUNDED,
        border_style=ZenzicPalette.DIM,
        header_style=ZenzicPalette.STYLE_BRAND,
        pad_edge=True,
        padding=(0, 1),
    )
    core_table.add_column("Codes", style="bold cyan", min_width=8, no_wrap=True)
    core_table.add_column("Scanner", style="bold", min_width=16)
    core_table.add_column("Capability")
    core_table.add_column("Exit", min_width=6, justify="center")

    for scanner in CORE_SCANNERS:
        if scanner.non_suppressible:
            exit_cell = Text.from_markup(f"[bold red]{scanner.primary_exit} \u26a0[/bold red]")
        else:
            exit_cell = Text(str(scanner.primary_exit))
        core_table.add_row(scanner.codes, scanner.name, scanner.capability, exit_cell)

    _shared.console.print(core_table)
    _shared.console.print()
    _shared.console.print(
        Text.from_markup(
            f"  [{ZenzicPalette.DIM}]\u26a0  Exit 2 and Exit 3 are non-suppressible \u2014 "
            f"--exit-zero has no effect on credential scanner or path traversal guard.[/{ZenzicPalette.DIM}]"
        )
    )
    _shared.console.print()

    # ── Section B: Extensible Rules ───────────────────────────────────────
    rules = list_plugin_rules()

    rules_table = Table(
        title=(
            f"[bold {ZenzicPalette.BRAND}]Extensible Rules[/]  "
            f"[{ZenzicPalette.DIM}](plugin system — zenzic.rules entry-point group)[/]"
        ),
        title_justify="left",
        box=box.ROUNDED,
        border_style=ZenzicPalette.DIM,
        header_style=ZenzicPalette.STYLE_BRAND,
        pad_edge=True,
        padding=(0, 1),
    )
    rules_table.add_column("Rule", style="bold cyan", min_width=14)
    rules_table.add_column("Code", style="bold", min_width=6)
    rules_table.add_column("Origin", min_width=8)
    rules_table.add_column("Class", style=ZenzicPalette.DIM)

    if rules:
        for info in rules:
            origin_badge = (
                "[cyan](core)[/]" if info.origin == "zenzic" else f"[green]({info.origin})[/]"
            )
            rules_table.add_row(info.source, info.rule_id, origin_badge, info.class_name)
    else:
        rules_table.add_row(
            f"[{ZenzicPalette.DIM}]\u2014[/]",
            f"[{ZenzicPalette.DIM}]\u2014[/]",
            f"[{ZenzicPalette.DIM}]\u2014[/]",
            (
                f"[{ZenzicPalette.DIM}]No third-party plugins installed. "
                f"Register rules via the zenzic.rules entry-point group.[/{ZenzicPalette.DIM}]"
            ),
        )

    _shared.console.print(rules_table)
    _shared.console.print()

    rule_count = len(rules)
    _shared.console.print(
        Text.from_markup(
            f"  [{ZenzicPalette.DIM}]{len(CORE_SCANNERS)} built-in scanners \u00b7 "
            f"{rule_count} extensible rule{'s' if rule_count != 1 else ''} registered"
            f"[/{ZenzicPalette.DIM}]"
        )
    )
    _shared.console.print()

    # ── Section C: Engine-specific Link Bypasses ──────────────────────────
    bypass_table = Table(
        title=(
            f"[bold {ZenzicPalette.BRAND}]Engine-specific Link Bypasses[/]  "
            f"[{ZenzicPalette.DIM}](Rule R21 — Protocol Sovereignty)[/]"
        ),
        title_justify="left",
        box=box.ROUNDED,
        border_style=ZenzicPalette.DIM,
        header_style=ZenzicPalette.STYLE_BRAND,
        pad_edge=True,
        padding=(0, 1),
    )
    bypass_table.add_column("Engine", style="bold cyan", min_width=12, no_wrap=True)
    bypass_table.add_column("Adapter", style="bold", min_width=20)
    bypass_table.add_column("Bypass Schemes")

    _BYPASS_ROWS = [
        (
            "mkdocs",
            "MkDocsAdapter",
            Text.from_markup(f"[{ZenzicPalette.DIM}](none)[/{ZenzicPalette.DIM}]"),
        ),
        (
            "zensical",
            "ZensicalAdapter",
            Text.from_markup(f"[{ZenzicPalette.DIM}](none)[/{ZenzicPalette.DIM}]"),
        ),
        (
            "standalone",
            "StandaloneAdapter",
            Text.from_markup(f"[{ZenzicPalette.DIM}](none)[/{ZenzicPalette.DIM}]"),
        ),
    ]
    for _engine, _adapter, _bypasses in _BYPASS_ROWS:
        bypass_table.add_row(_engine, _adapter, _bypasses)

    _shared.console.print(bypass_table)
    _shared.console.print()
    _shared.console.print(
        Text.from_markup(
            f"  [{ZenzicPalette.DIM}]R21: engine-specific behaviour is declared in the adapter "
            f"via get_link_scheme_bypasses() \u2014 validator.py never hardcodes engine names."
            f"[/{ZenzicPalette.DIM}]"
        )
    )
    _shared.print_footer_hint("inspect")


# Canonical command
inspect_app.command(
    name="capabilities",
    help="Show all built-in scanners, plugin rules, and engine-specific link bypasses.",
)(_inspect_capabilities)


@inspect_app.command(name="codes")
def inspect_codes(
    tier: str = typer.Option(
        "all",
        "--tier",
        help="Filter by tier: core, governance, plugin, custom, or all.",
        show_default=True,
    ),
) -> None:
    """Show code registry grouped by tier with activation status from config."""
    from zenzic.core.rules import list_plugin_rules

    tier_normalized = tier.strip().lower()
    valid_tiers = {"core", "governance", "plugin", "custom", "all"}
    if tier_normalized not in valid_tiers:
        _shared.console.print(
            "[bold red]Error:[/] --tier must be one of: core, governance, plugin, custom, all"
        )
        raise typer.Exit(1)

    repo_root = find_repo_root()
    config, _ = ZenzicConfig.load(repo_root)

    _SEVERITY_STYLE: dict[str, str] = {
        "error": "bold red",
        "warning": "bold yellow",
        "note": "bold blue",
    }

    def _severity_markup(code: str) -> str:
        defn = CODE_DEFINITIONS.get(code)
        if defn is None:
            return f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]"
        if getattr(defn, "status", "active") == "inactive":
            return f"[{ZenzicPalette.DIM}]inactive[/{ZenzicPalette.DIM}]"
        sty = _SEVERITY_STYLE.get(defn.severity, ZenzicPalette.DIM)
        return f"[{sty}]{defn.severity}[/{sty}]"

    def _penalty_markup(code: str) -> str:
        defn = CODE_DEFINITIONS.get(code)
        if defn is None:
            return f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]"
        # Inactive codes are never emitted — show dim dash, not a penalty.
        if getattr(defn, "status", "active") == "inactive":
            return f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]"
        # Z0xx (config abort) and Z2xx (security codes) collapse the score to 0
        # and halt the pipeline unconditionally — show FATAL, not 0.0.
        if code.startswith("Z0") or code.startswith("Z2"):
            return "[bold red]FATAL[/bold red]"
        # warning + 0.0 penalty = governance gate / pipeline block (e.g. Z504,
        # Z902) — show HALT to signal CI exit rather than math cost.
        # Z901 is the one error-severity exception: it also unconditionally
        # blocks the pipeline (via the normal error path, not the
        # governance-gate mechanism warnings need) and also carries a 0.0
        # penalty (never reaches DQS scoring) — same practical HALT outcome,
        # reached a different way. Not a general "error + 0.0 => HALT" rule:
        # Z110/Z111 are also error+0.0 but are genuinely FATAL config-abort
        # codes, a separate category with its own known display gap.
        if (defn.severity == "warning" and defn.penalty == 0.0) or code == "Z901":
            return "[bold red]HALT[/bold red]"
        # note + 0.0 = genuinely informational; never blocks CI (Fail-Visible rule).
        if defn.penalty == 0.0:
            return f"[{ZenzicPalette.DIM}]0.0[/{ZenzicPalette.DIM}]"
        return f"[bold]-{defn.penalty:.1f}[/bold]"

    rows: dict[str, list[tuple[str, str, str, str]]] = {
        "core": [],
        "governance": [],
        "plugin": [],
        "custom": [],
    }

    # Core + Governance (from canonical registry)
    for code in sorted(CODE_NAMES.keys(), key=lambda c: int(c[1:])):
        if code.startswith("Z6"):
            rows["governance"].append(
                (code, CODE_NAMES[code], _severity_markup(code), _penalty_markup(code))
            )
        else:
            rows["core"].append(
                (code, CODE_NAMES[code], _severity_markup(code), _penalty_markup(code))
            )

    # Plugin tier (third-party only; core-origin entry points excluded)
    plugin_infos = [info for info in list_plugin_rules() if info.origin != "zenzic"]
    for info in plugin_infos:
        rows["plugin"].append(
            (
                info.rule_id,
                info.source,
                _severity_markup(info.rule_id),
                _penalty_markup(info.rule_id),
            )
        )

    # Custom tier (local TOML custom rules)
    for cr in config.custom_rules:
        rule_id_str = cr.id or cr.class_name or "ZZ-CUSTOM"
        rows["custom"].append(
            (
                rule_id_str,
                "custom rule",
                f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]",
                f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]",
            )
        )

    if tier_normalized == "all":
        selected_tiers = ["core", "governance", "plugin", "custom"]
    else:
        selected_tiers = [tier_normalized]

    table = Table(
        title=f"[bold {ZenzicPalette.BRAND}]Code Registry[/] · tier view",
        title_justify="left",
        box=box.ROUNDED,
        border_style=ZenzicPalette.DIM,
        header_style=ZenzicPalette.STYLE_BRAND,
        pad_edge=True,
        padding=(0, 1),
    )
    table.add_column("Tier", style="bold cyan", min_width=12, no_wrap=True)
    table.add_column("Code", style="bold", min_width=10, no_wrap=True)
    table.add_column("Name", min_width=20)
    table.add_column("Severity", min_width=9, no_wrap=True)
    table.add_column("Penalty", min_width=7, no_wrap=True, justify="right")

    title_map = {
        "core": "Core",
        "governance": "Governance",
        "plugin": "Plugin",
        "custom": "Custom",
    }
    for idx, tier_name in enumerate(selected_tiers):
        tier_rows = rows[tier_name]
        if not tier_rows:
            table.add_row(
                title_map[tier_name],
                "—",
                "No entries",
                f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]",
                f"[{ZenzicPalette.DIM}]—[/{ZenzicPalette.DIM}]",
            )
        else:
            for code, name, severity, penalty in tier_rows:
                table.add_row(title_map[tier_name], code, name, severity, penalty)
        if idx < len(selected_tiers) - 1:
            table.add_section()

    _shared.console.print()
    _shared.console.print(table)
    _shared.console.print()
    _shared.print_footer_hint("inspect")


@inspect_app.command(name="routes")
def inspect_routes(
    kind: str = typer.Option(
        "all",
        "--kind",
        help="Filter routes by kind: physical, virtual, or all.",
        show_default=True,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output the route map as machine-readable JSON.",
    ),
) -> None:
    """Export the complete site map — URLs, source files, and digest fingerprints.

    Each route entry carries:

    * **url** — the canonical path,
    * **kind** — physical, tag, tag_index, pagination, author, or author_index,
    * **source_files** — repo-relative POSIX paths that activate the route, and
    * **digest** — SHA-256 of ``url + ':' + ','.join(sorted(source_files))``.
    """
    import hashlib
    import json as _json
    import sys
    from pathlib import Path

    from zenzic.core.adapters import get_adapter
    from zenzic.core.discovery import (
        build_content_mounts,
        iter_extra_content_markdown_sources,
        iter_markdown_sources,
    )
    from zenzic.models.vsm import build_vsm

    _VALID_KINDS = frozenset({"physical", "virtual", "all"})
    if kind not in _VALID_KINDS:
        # JSON Purity Invariant: errors always go to stderr, never stdout
        msg = "Error: --kind must be one of: physical, virtual, all\n"
        if as_json:
            sys.stderr.write(msg)
        else:
            _shared.console.print(
                "[bold red]Error:[/] --kind must be one of: physical, virtual, all"
            )
        raise typer.Exit(1)

    repo_root = find_repo_root()
    config, _ = ZenzicConfig.load(repo_root)
    docs_root = (repo_root / config.docs_dir).resolve()
    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)
    adapter = get_adapter(config.build_context, docs_root, repo_root)

    # ── Pass 1: load docs markdown files ──────────────────────────────────────
    md_contents: dict[Path, str] = {}
    for md_file in iter_markdown_sources(docs_root, config, exclusion_mgr):
        try:
            md_contents[md_file.resolve()] = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

    # ── Pass 1c: include extra content roots (blog/, etc.) ────────────────────
    extra_content_roots = adapter.get_extra_content_roots(repo_root)
    extra_content_mounts = build_content_mounts(extra_content_roots, repo_root=repo_root)
    for content_root, url_prefix in extra_content_mounts:
        for abs_path, _ in iter_extra_content_markdown_sources(
            content_root, url_prefix, config, exclusion_mgr
        ):
            try:
                md_contents[abs_path.resolve()] = abs_path.read_text(encoding="utf-8")
            except OSError:
                continue

    # ── Pass 1d: include static assets (HTML, webp, images, etc.) ──────────────
    from zenzic.core.discovery import DOC_SUFFIXES, walk_files

    static_assets: set[Path] = set()
    if docs_root.is_dir():
        for fpath in walk_files(docs_root, set(config.excluded_dirs), exclusion_mgr, config):
            if fpath.suffix.lower() not in DOC_SUFFIXES and not fpath.is_symlink():
                if not exclusion_mgr.should_exclude_file(fpath, docs_root):
                    static_assets.add(fpath)

    vsm = build_vsm(
        adapter,
        docs_root,
        md_contents,
        extra_content_roots=extra_content_roots,
        repo_root=repo_root,
        static_assets=static_assets,
    )

    # ── Virtual route kind lookup (call once; idempotent with build_vsm's call) ─
    virtual_kind_map: dict[str, str] = {}
    if hasattr(adapter, "get_virtual_routes"):
        for vr in adapter.get_virtual_routes(md_contents):
            virtual_kind_map[vr.url] = vr.kind

    # ── Source file normalisation ──────────────────────────────────────────────
    # Extra-content-root files are already repo-relative (e.g. "blog/post.md").
    # Docs-root files are relative to docs/, so prepend docs_dir to make them
    # repo-relative (e.g. "intro.md" → "docs/intro.md").
    _extra_prefixes: frozenset[str] = frozenset(
        prefix.rstrip("/") for _, prefix in extra_content_mounts if prefix
    )
    _docs_prefix = config.docs_dir.as_posix().rstrip("/")

    def _physical_source(route_source: str) -> str:
        for pfx in _extra_prefixes:
            if route_source == pfx or route_source.startswith(pfx + "/"):
                return route_source  # already repo-relative
        return _docs_prefix + "/" + route_source

    def _digest(url: str, source_files: list[str]) -> str:
        raw = url + ":" + ",".join(sorted(source_files))
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── Build records ──────────────────────────────────────────────────────────
    records: list[dict[str, str | list[str]]] = []
    for url, route in sorted(vsm.items()):
        if not url:
            continue
        is_virtual = route.source == "<virtual>"
        if kind == "physical" and is_virtual:
            continue
        if kind == "virtual" and not is_virtual:
            continue
        if is_virtual:
            route_kind: str = virtual_kind_map.get(url, "tag")
            source_files: list[str] = sorted(route.proxy_sources)
        else:
            route_kind = "physical"
            source_files = [_physical_source(route.source)]

        records.append(
            {
                "url": url,
                "kind": route_kind,
                "source_files": source_files,
                "digest": _digest(url, source_files),
            }
        )

    # ── Output ─────────────────────────────────────────────────────────────────
    if as_json:
        # JSON Purity Invariant (Rule R20 Machine Silence):
        # stdout must contain EXCLUSIVELY valid JSON — no Rich markup, no ANSI
        # codes, no banners. Write directly to sys.stdout, bypassing the Rich
        # console entirely.
        sys.stdout.write(_json.dumps({"routes": records}, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stdout.flush()
        return

    label = f"{len(records)} route{'s' if len(records) != 1 else ''}"
    table = Table(
        title=f"[bold]Site Map[/] · {label}",
        title_justify="left",
        box=box.ROUNDED,
        border_style=ZenzicPalette.DIM,
        header_style=ZenzicPalette.STYLE_BRAND,
        pad_edge=True,
        padding=(0, 1),
    )
    table.add_column("URL", style="bold cyan", no_wrap=True)
    table.add_column("Kind", min_width=10)
    table.add_column("Source Files")
    table.add_column("Digest", style=ZenzicPalette.DIM, min_width=12, no_wrap=True)

    for rec in records:
        table.add_row(
            str(rec["url"]),
            str(rec["kind"]),
            ", ".join(str(sf) for sf in rec["source_files"]),
            str(rec["digest"])[:12] + "…",
        )

    _shared.console.print()
    _shared.console.print(table)
    _shared.console.print()
    _shared.print_footer_hint("inspect")
