# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Single Source of Truth for CLI command metadata and help surface."""

from __future__ import annotations

from dataclasses import dataclass

from zenzic.core.ui import ZenzicPalette


@dataclass(frozen=True, slots=True)
class CommandMeta:
    """Declarative metadata for top-level CLI command registration."""

    name: str
    panel: str
    short_help: str
    long_help: str
    usage_hint: str


ROOT_HELP = (
    f"[bold {ZenzicPalette.BRAND}]Zenzic[/] — Engine-agnostic static analyzer and credential scanner "
    "for Markdown documentation.\n\n"
    "Run [bold cyan]zenzic check all[/] for a full audit, or pick individual "
    "checks below."
)

ROOT_EPILOG = (
    f"[bold {ZenzicPalette.BRAND}]PythonWoods[/]  "
    f"[{ZenzicPalette.DIM}]·  Apache-2.0  ·  https://zenzic.dev[/]"
)


COMMANDS: tuple[CommandMeta, ...] = (
    CommandMeta(
        name="lab",
        panel="Core",
        short_help="Run interactive lab scenarios for bundled documentation examples.",
        long_help="Run the interactive Zenzic Lab and bundled documentation scenarios.",
        usage_hint="Try 'zenzic lab --help' for options.",
    ),
    CommandMeta(
        name="lsp",
        panel="SDK & Extensibility",
        short_help="Start the Zenzic Language Server (ZLS) over stdio.",
        long_help="Start the Zenzic Language Server (ZLS) over stdio for editor integration.",
        usage_hint="This command is intended for editor clients, not interactive use.",
    ),
    CommandMeta(
        name="check",
        panel="Core",
        short_help="Run documentation quality checks.",
        long_help="Run documentation quality checks.",
        usage_hint="Refer to https://zenzic.dev/docs/reference/finding-codes for remediation · Try 'zenzic check --help' for options.",
    ),
    CommandMeta(
        name="clean",
        panel="Core",
        short_help="Safely remove unused documentation files.",
        long_help="Safely remove unused documentation files.",
        usage_hint="Try 'zenzic clean --help' for options.",
    ),
    CommandMeta(
        name="score",
        panel="Quality",
        short_help="Compute a 0–100 documentation quality score across all checks.",
        long_help="Compute a 0–100 documentation quality score across all checks.",
        usage_hint="Try 'zenzic score --help' for options.",
    ),
    CommandMeta(
        name="audit",
        panel="Governance",
        short_help="Generate a formal compliance audit report of workspace governance, DQS, and technical debt.",
        long_help="Generate a formal compliance audit report detailing active policies, DQS score calculation, technical debt suppressions, and architectural adapter state.",
        usage_hint="Try 'zenzic audit --help' for options.",
    ),
    CommandMeta(
        name="fix",
        panel="Core",
        short_help="Auto-fix deterministic structural violations.",
        long_help="Auto-fix deterministic structural violations.",
        usage_hint="Try 'zenzic fix --help' for options.",
    ),
    CommandMeta(
        name="diff",
        panel="Quality",
        short_help="Compare current documentation score against the saved snapshot.",
        long_help="Compare current documentation score against the saved snapshot.",
        usage_hint="Try 'zenzic diff --help' for options.",
    ),
    CommandMeta(
        name="explain",
        panel="Quality",
        short_help="Show rule metadata, scoring weight, and config genealogy for a rule code.",
        long_help="Show rule metadata, scoring weight, and config genealogy for a rule code.",
        usage_hint="Try 'zenzic explain --help' for options.",
    ),
    CommandMeta(
        name="init",
        panel="SDK & Extensibility",
        short_help="Scaffold a Zenzic configuration in the current project.",
        long_help="Scaffold a Zenzic configuration in the current project.",
        usage_hint="Try 'zenzic init --help' for options.",
    ),
    CommandMeta(
        name="config",
        panel="Introspection",
        short_help="Inspect the active Zenzic configuration and the origin of each value.",
        long_help="Inspect the active Zenzic configuration and the origin of each value.",
        usage_hint="Try 'zenzic config --help' for options.",
    ),
    CommandMeta(
        name="guard",
        panel="Introspection",
        short_help="Run the fast pre-commit secret guard for Markdown/MDX files.",
        long_help="Run the fast pre-commit secret guard for Markdown/MDX files.",
        usage_hint="Try 'zenzic guard --help' for options.",
    ),
    CommandMeta(
        name="inspect",
        panel="Introspection",
        short_help="Introspect the Zenzic scanner arsenal and plugin registry.",
        long_help="Introspect the Zenzic scanner arsenal and plugin registry.",
        usage_hint="Try 'zenzic inspect --help' for options.",
    ),
    CommandMeta(
        name="env",
        panel="Introspection",
        short_help="Output core environment diagnostics.",
        long_help="Output core environment diagnostics (Python executable, Zenzic version, config path).",
        usage_hint="Try 'zenzic env --help' for options.",
    ),
)


COMMAND_BY_NAME: dict[str, CommandMeta] = {cmd.name: cmd for cmd in COMMANDS}
