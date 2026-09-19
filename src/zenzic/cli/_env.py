# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Environment diagnostics command for Zenzic (ADR-075 Radical Unawareness)."""

from __future__ import annotations

import contextlib
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
        with contextlib.suppress(Exception):
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            if "tool" in data and "zenzic" in data["tool"]:
                return pyproject.resolve()

    return None


def _project_identity(cwd: Path) -> tuple[str, str, str | None]:
    """Return ``(engine, engine_source, generator)`` for the project at *cwd*.

    ``engine`` is the **effective** engine — the one a scan actually runs, with
    ``auto`` already resolved through ``discover_engine()``. Reporting the
    declared value instead would make this command disagree with the telemetry
    line a scan prints for the same project ("auto" here, "standalone" there),
    which is two answers to one question and the shape of divergence this
    codebase keeps paying for. ``engine_source`` keeps the distinction that
    resolving would otherwise erase: whether a human chose it or a marker file
    did.

    ``generator`` is what the repository shows, read through the same
    ``detect_generator`` registry ``zenzic init`` uses, so setup and
    diagnostics cannot disagree about what this project is.

    No lookup here may fail the command: ``env`` is what a user runs when
    something else is already broken, and a diagnostics command that raises on
    a malformed config is absent exactly when it is needed.
    """
    engine = "auto"
    engine_source = "default"
    generator: str | None = None
    with contextlib.suppress(Exception):
        from zenzic.models.config import ZenzicConfig

        config, _ = ZenzicConfig.load(cwd)
        engine = config.build_context.engine
        engine_source = "configured" if engine != "auto" else "default"
    if engine == "auto":
        with contextlib.suppress(Exception):
            from zenzic.core.adapters._factory import discover_engine

            engine = discover_engine(cwd)
            engine_source = "auto-detected"
    with contextlib.suppress(Exception):
        from zenzic.cli._standalone import detect_generator

        found = detect_generator(cwd)
        if found is not None:
            generator = found[0]
    return engine, engine_source, generator


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

    # What Zenzic thinks this project *is*, beside where Zenzic itself lives.
    # Both were invisible outside a scan's telemetry line until 2026-09-19: an
    # editor extension had no way to ask, and a user whose engine did not match
    # their generator had to infer the mismatch from the findings. `engine` is
    # configured and `generator` is detected, so the two can disagree — which is
    # exactly the state worth being able to read.
    engine, engine_source, generator = _project_identity(cwd)

    # Whether "which documentation generator is this?" is a question that
    # applies at all. An engine with a native adapter has already answered it
    # by reading that generator's own configuration, so nothing was looked for
    # -- and reporting "none detected" there reads as a detection that failed.
    # Exposed as a field rather than re-derived per surface, so the CLI and the
    # editor extension cannot disagree about which engines are native.
    from zenzic.core.adapters._factory import NATIVE_GENERATOR_ENGINES

    generator_applies = engine not in NATIVE_GENERATOR_ENGINES

    env_data: dict[str, Any] = {
        "zenzic_version": __version__,
        "python_executable": str(python_exec),
        "zenzic_module_path": str(zenzic_module),
        "current_working_directory": str(cwd),
        "active_config_path": str(config_path) if config_path else None,
        "engine": engine,
        "engine_source": engine_source,
        "generator": generator,
        "generator_applies": generator_applies,
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
    console.print(f"  [dim]Engine:[/] {env_data['engine']} ({env_data['engine_source']})")
    if generator:
        _generator_line = str(generator)
    elif generator_applies:
        _generator_line = "[yellow]none detected[/]"
    else:
        # "none detected" on an MkDocs project reads as a detection that failed.
        # Nothing was looked for: the engine reads its generator's own
        # configuration, so the question does not arise.
        _generator_line = f"[dim]not applicable — {engine} has its own adapter[/]"
    console.print(f"  [dim]Generator:[/] {_generator_line}")
