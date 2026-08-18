# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""config sub-commands: explain — active-value hierarchy introspection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # PEP 680 backport

import typer
from rich import box
from rich.table import Table
from rich.text import Text

from zenzic.core.scanner import find_repo_root
from zenzic.core.ui import ZenzicPalette, emoji
from zenzic.models.config import (
    BuildContext,
    GovernanceConfig,
    PoliciesConfig,
    ZenzicConfig,
)

from . import _shared
from ._metadata import COMMAND_BY_NAME


config_app = _shared.create_app(
    name="config",
    long_help=(f"[bold {ZenzicPalette.BRAND}]Config[/] — {COMMAND_BY_NAME['config'].long_help}"),
)


# ── Source resolution ────────────────────────────────────────────────────────

_SOURCE_BADGE: dict[str, tuple[str, str]] = {
    "local": (
        f"[bold {ZenzicPalette.WARNING}]local[/]",
        f"[{ZenzicPalette.WARNING}].zenzic.local.toml (Override)[/]",
    ),
    "global": (
        f"[bold {ZenzicPalette.BRAND}]global[/]",
        f"[{ZenzicPalette.BRAND}].zenzic.toml[/]",
    ),
    "default": (f"[{ZenzicPalette.DIM}]default[/]", f"[{ZenzicPalette.DIM}]built-in[/]"),
}


def _load_raw_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file into a raw dict, silently returning {} on any error."""
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def _source_of(
    field: str,
    raw_global: dict[str, Any],
    raw_local: dict[str, Any],
    *,
    section: str | None = None,
) -> str:
    """Determine where *field* originates: 'local', 'global', or 'default'."""
    local_section_data = raw_local.get(section, {}) if section else {}
    global_section_data = raw_global.get(section, {}) if section else {}

    if section:
        if isinstance(local_section_data, dict) and field in local_section_data:
            return "local"
        if isinstance(global_section_data, dict) and field in global_section_data:
            return "global"
    else:
        if field in raw_local:
            return "local"
        if field in raw_global:
            return "global"
    return "default"


def _value_repr(value: Any, *, max_len: int = 60) -> str:
    """Compact, human-readable representation of a config value."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        if not value:
            return "[]"
        items = ", ".join(str(v) for v in value)
        summary = f"[{items}]"
        if len(summary) > max_len:
            return f"[{len(value)} items]"
        return summary
    if isinstance(value, dict):
        if not value:
            return "{}"
        return f"{{{len(value)} keys}}"
    return str(value)


# ── Table builder ─────────────────────────────────────────────────────────────


def _make_table(title: str) -> Table:
    return Table(
        title=f"[bold {ZenzicPalette.BRAND}]{title}[/]",
        title_justify="left",
        box=box.ROUNDED,
        border_style=ZenzicPalette.DIM,
        header_style=ZenzicPalette.STYLE_BRAND,
        pad_edge=True,
        padding=(0, 1),
        expand=False,
    )


def _add_row(
    table: Table,
    field: str,
    value: Any,
    source: str,
) -> None:
    badge_markup, origin_markup = _SOURCE_BADGE[source]
    table.add_row(
        Text.from_markup(f"[bold]{field}[/]"),
        Text(_value_repr(value)),
        Text.from_markup(badge_markup),
        Text.from_markup(origin_markup),
    )


# ── explain command ──────────────────────────────────────────────────────────


@config_app.command(name="explain")
def explain(
    path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Repository root to inspect (default: current working directory).",
        show_default=True,
    ),
) -> None:
    """Show the active configuration and the origin of every value.

    For each field the source is one of:

    \\b
    - [bold amber]local[/bold amber]   — set in .zenzic.local.toml (machine-local, git-ignored)
    - [bold indigo]global[/bold indigo]  — set in .zenzic.toml (shared, version-controlled)
    - [dim]default[/dim]  — built-in Zenzic default (no explicit declaration)
    """
    from zenzic import __version__

    repo_root = find_repo_root(search_from=Path(path).resolve(), fallback_to_cwd=True)

    raw_global = _load_raw_toml(repo_root / ".zenzic.toml")
    raw_local = _load_raw_toml(repo_root / ".zenzic.local.toml")

    # Canonical local core keys live under [core] in .zenzic.local.toml.
    # Legacy: top-level forbidden_patterns is also local.
    local_core = raw_local.get("core", {})
    if isinstance(local_core, dict) and local_core:
        # Promote core keys to local root for source resolution
        pass

    config, _ = ZenzicConfig.load(repo_root)

    console = _shared.get_console()
    _shared.get_ui().print_header(__version__)
    console.print()

    # ── config origin summary ─────────────────────────────────────────────
    global_file = repo_root / ".zenzic.toml"
    local_file = repo_root / ".zenzic.local.toml"
    global_status = (
        f"[{ZenzicPalette.SUCCESS}]{global_file.name}[/] [{ZenzicPalette.DIM}]({global_file})[/]"
        if global_file.is_file()
        else f"[{ZenzicPalette.DIM}]not found — using built-in defaults[/]"
    )
    local_status = (
        f"[{ZenzicPalette.WARNING}]{local_file.name}[/] [{ZenzicPalette.DIM}]({local_file})[/]"
        if local_file.is_file()
        else f"[{ZenzicPalette.DIM}]not found — no local overrides active[/]"
    )
    console.print(f"  {emoji('info')}  [bold]Global config:[/] {global_status}")
    console.print(f"  {emoji('info')}  [bold]Local overlay:[/] {local_status}")
    console.print()

    # ── Section A: Core ───────────────────────────────────────────────────
    core_fields: list[tuple[str, Any, str]] = []
    for field in (
        "docs_dir",
        "strict",
        "exit_zero",
        "fail_under",
        "snippet_min_lines",
        "placeholder_max_words",
        "validate_same_page_anchors",
        "respect_vcs_ignore",
        "forbidden_patterns",
    ):
        value = getattr(config, field)
        # forbidden_patterns can come from local [core] or top-level local
        if field == "forbidden_patterns":
            local_fp_core = isinstance(local_core, dict) and "forbidden_patterns" in local_core
            local_fp_top = "forbidden_patterns" in raw_local
            global_fp = "forbidden_patterns" in raw_global
            if local_fp_core or local_fp_top:
                source = "local"
            elif global_fp:
                source = "global"
            else:
                source = "default"
        else:
            # Try [core] section in local first, then top-level local, then global
            if isinstance(local_core, dict) and field in local_core:
                source = "local"
            else:
                source = _source_of(field, raw_global, raw_local)
        core_fields.append((field, value, source))

    core_table = _make_table(f"{emoji('info')}  Core")
    core_table.add_column("Field", style="bold", min_width=28, no_wrap=True)
    core_table.add_column("Active Value", min_width=30)
    core_table.add_column("Source", min_width=8, justify="center")
    core_table.add_column("Origin", min_width=22)

    for field, value, source in core_fields:
        _add_row(core_table, field, value, source)
    console.print(core_table)
    console.print()

    # ── Section B: Build Context ──────────────────────────────────────────
    bc = config.build_context
    bc_table = _make_table(f"{emoji('info')}  Build Context")
    bc_table.add_column("Field", style="bold", min_width=20, no_wrap=True)
    bc_table.add_column("Active Value", min_width=24)
    bc_table.add_column("Source", min_width=8, justify="center")
    bc_table.add_column("Origin", min_width=22)

    for field in BuildContext.model_fields:
        value = getattr(bc, field)
        source = _source_of(field, raw_global, raw_local, section="build_context")
        _add_row(bc_table, field, value, source)
    console.print(bc_table)
    console.print()

    # ── Section C: Governance ─────────────────────────────────────────────
    gov = config.governance
    gov_table = _make_table(f"{emoji('brand')}  Governance")
    gov_table.add_column("Field", style="bold", min_width=24, no_wrap=True)
    gov_table.add_column("Active Value", min_width=24)
    gov_table.add_column("Source", min_width=8, justify="center")
    gov_table.add_column("Origin", min_width=22)

    for field in GovernanceConfig.model_fields:
        value = getattr(gov, field)
        source = _source_of(field, raw_global, raw_local, section="governance")
        _add_row(gov_table, field, value, source)
    console.print(gov_table)
    console.print()

    # ── Section D: Policy-as-Code ─────────────────────────────────────────
    pol = config.policies
    pol_table = _make_table(f"{emoji('brand')}  Policy-as-Code")
    pol_table.add_column("Field", style="bold", min_width=28, no_wrap=True)
    pol_table.add_column("Active Value", min_width=24)
    pol_table.add_column("Source", min_width=8, justify="center")
    pol_table.add_column("Origin", min_width=22)

    for field in PoliciesConfig.model_fields:
        value = getattr(pol, field)
        source = _source_of(field, raw_global, raw_local, section="policies")
        _add_row(pol_table, field, value, source)
    console.print(pol_table)
    console.print()

    _shared.print_footer_hint("config")
