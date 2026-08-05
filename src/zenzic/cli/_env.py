# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Environment diagnostics command for Zenzic (ADR-075 Radical Unawareness)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

import zenzic
from zenzic import __version__
from zenzic.cli._shared import get_console
from zenzic.core.ui import ZenzicPalette


def _find_active_config_path(cwd: Path) -> Path | None:
    """Resolve the active configuration file path in cwd (if present)."""
    zenzic_toml = cwd / ".zenzic.toml"
    if zenzic_toml.is_file():
        return zenzic_toml.resolve()

    zenzic_local = cwd / ".zenzic.local.toml"
    if zenzic_local.is_file():
        return zenzic_local.resolve()

    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        try:
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            if "tool" in data and "zenzic" in data["tool"]:
                return pyproject.resolve()
        except Exception:
            pass

    return None


def env(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output environment diagnostics in machine-readable JSON format.",
        ),
    ] = False,
) -> None:
    """Output core environment diagnostics (Python executable, Zenzic version, config path)."""
    cwd = Path.cwd().resolve()
    python_exec = Path(sys.executable).resolve()
    zenzic_module = Path(zenzic.__file__).resolve()
    config_path = _find_active_config_path(cwd)

    env_data: dict[str, Any] = {
        "zenzic_version": __version__,
        "python_executable": str(python_exec),
        "zenzic_module_path": str(zenzic_module),
        "current_working_directory": str(cwd),
        "active_config_path": str(config_path) if config_path else None,
    }

    if json_output:
        typer.echo(json.dumps(env_data, indent=2))
        return

    console = get_console()
    console.print(f"[bold {ZenzicPalette.BRAND}]Zenzic Environment Diagnostics[/]")
    console.print(f"  [dim]Zenzic Version:[/] {env_data['zenzic_version']}")
    console.print(f"  [dim]Python Executable:[/] {env_data['python_executable']}")
    console.print(f"  [dim]Zenzic Module Path:[/] {env_data['zenzic_module_path']}")
    console.print(f"  [dim]Working Directory:[/] {env_data['current_working_directory']}")
    if config_path:
        console.print(f"  [dim]Active Config:[/] {env_data['active_config_path']}")
    else:
        console.print("  [dim]Active Config:[/] [yellow]None (using built-in defaults)[/]")
