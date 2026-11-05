# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic doctor`` and ``zenzic adr new`` — repository-health CLI surface.

Presentation and exit codes, and the one question to git the checks need; every
check and the scaffold itself live in ``zenzic.core.doctor`` and are pure over a
path plus config (ADR-075, ADR 096).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import typer
from rich.markup import escape

from zenzic.cli import _shared
from zenzic.core.doctor import DoctorFinding, next_adr_number, run_all, scaffold_adr
from zenzic.core.ui import ZenzicPalette
from zenzic.models.config import ZenzicConfig, load_config_with_diagnostics


def _load(repo_root: Path) -> ZenzicConfig:
    config, _ = load_config_with_diagnostics(repo_root)
    return config or ZenzicConfig()


def _git_on_path() -> str | None:
    """A git from an absolute entry of PATH that is not the current folder, or None.

    A folder being scanned may hold a file named git: Windows looks in the current
    folder before PATH, and a relative entry of PATH does the same anywhere.
    """
    here = Path.cwd().resolve()
    for entry in os.get_exec_path():
        folder = Path(entry)
        if not folder.is_absolute() or folder.resolve() == here:
            continue
        for name in ("git", "git.exe"):
            candidate = folder / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


#: What a repository may not decide for this one question. ``ls-tree`` reads objects and
#: never the index, so ``core.fsmonitor`` has no way in, and it is off in case that changes;
#: a bare repository delivered inside a clone brings a config of its own.
_GIT_LOCKED = ("-c", "core.fsmonitor=false", "-c", "safe.bareRepository=explicit")


def _tracked_files(repo_root: Path) -> tuple[frozenset[str] | None, str | None]:
    """What the last commit tracks under *repo_root*, and what stopped git from saying.

    A clone gets the last commit, never the index. A submodule is an entry ending in
    ``/``. ``(None, None)`` outside a repository or without git, where there is nothing
    to compare with. A git that refuses for another reason, a checkout of another user in
    a CI container, gives its first line: silence there would pass the very case the
    check exists for. The names are bytes from git, never the locale's encoding.
    """
    git = _git_on_path()
    if git is None:
        return None, None
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
    }
    try:
        proc = subprocess.run(  # noqa: S603  # An absolute git, fixed hardcoded arguments
            [git, *_GIT_LOCKED, "ls-tree", "-r", "-z", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            env={**environment, "LC_ALL": "C", "GIT_NO_LAZY_FETCH": "1"},
        )
    except OSError:
        return None, None
    if proc.returncode != 0:
        if "not a git repository" in proc.stderr:
            return None, None
        if "Not a valid object name HEAD" in proc.stderr:
            return frozenset(), None
        return None, (proc.stderr.splitlines() or [f"exit {proc.returncode}"])[0]
    names = set()
    for entry in proc.stdout.split("\0"):
        if entry:
            header, _, name = entry.partition("\t")
            names.add(f"{name}/" if header.startswith("160000 ") else name)
    return frozenset(names), None


def doctor(
    path: str = typer.Argument(None, help="Repository root to inspect (default: current dir)."),
    output_format: str = typer.Option(
        "text", "--format", "-f", help="Output format: text or json."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output when healthy."),
    no_header: bool = typer.Option(False, "--no-header", help="Suppress the Zenzic banner."),
) -> None:
    """Check repository conventions: ADR citations, redirects, config schema, tracked paths.

    Complements ``zenzic check``, which analyses documentation content. These
    checks look at the repository's own conventions instead, and a configured path
    git does not track is reported: the verdict must not depend on the clone.
    """
    _shared._validate_output_format(output_format, _shared._BASE_FORMATS[:2])

    repo_root = Path(path).resolve() if path else Path.cwd()
    config = _load(repo_root)
    tracked, git_problem = _tracked_files(repo_root)
    results = run_all(repo_root, config.doctor, tracked)
    if git_problem:
        results["tracked-paths"].append(
            DoctorFinding(
                check="tracked-paths",
                message=f"git could not list the tracked files: {git_problem}",
            )
        )
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
            _shared.console.print(f"  [{ZenzicPalette.DIM}]{escape(finding.render())}[/]")

    _shared.console.print(f"\n{len(findings)} finding(s) across {len(results)} checks.")
    raise typer.Exit(1)


adr_app = typer.Typer(help="Manage architectural decision records.", no_args_is_help=True)


@adr_app.command("new")
def adr_new(
    title: str = typer.Argument(..., help="Title of the decision, e.g. 'Adopt RE2 for matching'."),
    path: str = typer.Option(None, "--path", help="Repository root (default: current dir)."),
) -> None:
    """Allocate the next free ADR number and scaffold its record.

    The allocation is the point, not the template. Numbers are issued one past
    the highest present, never by counting records and never filling gaps: the
    vault has real ones, and re-issuing an identifier that existing prose
    already cites would silently repoint that citation at a different decision —
    a reference resolving to the wrong target, which is the defect class this
    engine exists to prevent. Creating a second record under a number already in
    use is refused for the same reason.

    The five-section skeleton it writes afterwards is convenience; the record
    still has to be filled in and registered in the vault index by hand.
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
