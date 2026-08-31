# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic doctor`` and ``zenzic adr new`` — repository-health CLI surface.

Presentation and exit codes only; every check and the scaffold itself live in
``zenzic.core.doctor`` and are pure over a path plus config (ADR-075).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from zenzic.cli import _shared
from zenzic.core.doctor import DoctorFinding, next_adr_number, run_all, scaffold_adr
from zenzic.core.ui import ZenzicPalette
from zenzic.models.config import ZenzicConfig, load_config_with_diagnostics


def _load(repo_root: Path) -> ZenzicConfig:
    config, _ = load_config_with_diagnostics(repo_root)
    return config or ZenzicConfig()


def doctor(
    path: str = typer.Argument(None, help="Repository root to inspect (default: current dir)."),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text or json."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output when healthy."),
    no_header: bool = typer.Option(False, "--no-header", help="Suppress the Zenzic banner."),
) -> None:
    """Check repository conventions: ADR citations, redirects, and config schema.

    Complements ``zenzic check``, which analyses documentation content. These
    checks look at the repository's own conventions instead, and all of them read
    public repository content only.
    """
    _shared._validate_output_format(output_format, _shared._BASE_FORMATS[:2])

    repo_root = Path(path).resolve() if path else Path.cwd()
    config = _load(repo_root)
    results = run_all(repo_root, config.doctor)
    findings = [f for group in results.values() for f in group]

    if output_format == "json":
        print(
            json.dumps(
                {
                    "healthy": not findings,
                    "checks": {
                        name: [
                            {"check": f.check, "message": f.message, "location": f.location}
                            for f in group
                        ]
                        for name, group in results.items()
                    },
                },
                indent=2,
            )
        )
        raise typer.Exit(1 if findings else 0)

    if not no_header and not quiet:
        from zenzic import __version__

        _shared._ui.print_header(__version__)

    if not findings:
        if not quiet:
            _shared.console.print("✨ Repository conventions verified: no findings.")
        raise typer.Exit(0)

    for name, group in results.items():
        if not group:
            continue
        _shared.console.print(f"\n[bold]{name}[/]  ({len(group)})")
        for finding in group:
            _shared.console.print(f"  [{ZenzicPalette.DIM}]{finding.render()}[/]")

    _shared.console.print(f"\n{len(findings)} finding(s) across {len(results)} checks.")
    raise typer.Exit(1)


adr_app = typer.Typer(help="Manage architectural decision records.", no_args_is_help=True)


@adr_app.command("new")
def adr_new(
    title: str = typer.Argument(..., help="Title of the decision, e.g. 'Adopt RE2 for matching'."),
    path: str = typer.Option(None, "--path", help="Repository root (default: current dir)."),
) -> None:
    """Scaffold the next ADR record and print its path.

    Allocates the next free number rather than counting records: the vault has
    real gaps, and reusing an identifier that a citation elsewhere already refers
    to would silently repoint that citation at a different decision.
    """
    repo_root = Path(path).resolve() if path else Path.cwd()
    config = _load(repo_root)

    try:
        number = next_adr_number(repo_root, config.doctor)
        created = scaffold_adr(repo_root, config.doctor, number, title)
    except FileExistsError as exc:
        _shared.console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    except OSError as exc:
        _shared.console.print(f"[red]Could not write the record: {exc}[/]")
        raise typer.Exit(1) from exc

    rel = created.relative_to(repo_root)
    _shared.console.print(f"Created {rel}")
    _shared.console.print(
        f"[{ZenzicPalette.DIM}]Fill in Context, Decision, Rationale, Invariants and "
        f"Consequences, then register it in the vault index.[/]"
    )


__all__ = ["DoctorFinding", "adr_app", "adr_new", "doctor"]
