# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Entry point for the zenzic CLI application."""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Annotated, Any, cast

import typer
from rich.console import Console

from zenzic import __version__
from zenzic.cli import (
    adr_app,
    audit,
    check_app,
    clean_app,
    config_app,
    configure_console,
    diff,
    doctor,
    env,
    explain,
    fix,
    get_console,
    get_ui,
    guard_app,
    init,
    inspect_app,
    lab,
    lsp,
    score,
)
from zenzic.cli._metadata import COMMANDS, ROOT_EPILOG, ROOT_HELP
from zenzic.core.exceptions import PluginContractError, ZenzicError
from zenzic.core.logging import setup_cli_logging
from zenzic.core.ui import ZenzicPalette, ZenzicUI


# The Exit Code Contract reserves exit 2 for a Credential Scanner Breach, "never
# suppressible". Click's default for a usage error -- unknown option, unknown
# command, missing subcommand -- is also 2, so a typo'd flag and a live AWS key
# were indistinguishable by exit code and no CI gate could discriminate. That is
# not theoretical: the collision misled an adversarial audit of this very
# contract three separate times. Usage errors belong to the quality/error tier,
# so they exit 1 and exit 2 stays exclusive to the security tier.
#
# Set at module scope rather than inside cli_main() so every consumer of `app`
# -- the console entry point, the test runner, zenzic-mcp -- agrees on the
# semantics. A remap that only applies to one entry point is the same
# some-decision-points-but-not-all shape this contract keeps being bitten by.
#
# Typer vendors its own click (`typer._click`), which is a DIFFERENT module
# object from the installed `click` package -- patching only the latter changes
# nothing, because Typer's `_main` reads `e.exit_code` off its own class. Both
# are set: the vendored one is what actually runs today, and the upstream one
# keeps the behaviour correct for any path that reaches real click.
@contextmanager
def _usage_errors_exit_1() -> Iterator[None]:
    """Move Click usage errors off exit 2 -- for this invocation only.

    The Exit Code Contract reserves exit 2 for a Credential Scanner Breach, and
    Click's default for a usage error is also 2, so a typo'd flag and a live key
    were indistinguishable to any CI gate.

    ``exit_code`` is a class attribute on a class Zenzic does not own, so the
    remap is necessarily a mutation of shared state. Doing it at import time
    made it **process-wide**: merely importing ``zenzic.main`` changed the exit
    code of every other Click application in the same interpreter, which is a
    library reaching outside its own boundary. Scoped here instead, it applies
    while Zenzic's own entry point is running and is restored afterwards, so an
    import has no observable effect on anyone else.

    Typer vendors its own click (``typer._click``), a DIFFERENT module object
    from the installed ``click`` package -- patching only the latter changes
    nothing, because Typer's ``_main`` reads ``e.exit_code`` off its own class.
    Both are set, and both are restored to whatever they held before, not to a
    hardcoded 2. Each import is guarded so a Typer version without the vendored
    alias degrades to patching what exists rather than failing at import time.
    """
    modules: list[Any] = []
    try:
        from typer import _click as _typer_click

        modules.append(_typer_click)
    except ImportError:  # pragma: no cover -- older Typer, no vendored module
        pass
    try:
        import click as _click_pkg

        modules.append(_click_pkg)
    except ImportError:  # pragma: no cover -- click is a hard Typer dependency
        pass

    previous = [(module, module.exceptions.UsageError.exit_code) for module in modules]
    for module in modules:
        module.exceptions.UsageError.exit_code = 1

    # The error the user sees is rendered by Typer's rich formatter, not by
    # Click's own `show` -- patching the latter changes nothing, because Typer
    # intercepts first. Extending the renderer mirrors the exit_code patch above
    # rather than adding a second mechanism, and is restored in the same
    # `finally`. If Typer ever stops exposing this, the hint disappears and the
    # bare Click message returns: a lost hint, not a broken CLI.
    import typer.rich_utils as _rich_utils

    _orig_format_error = _rich_utils.rich_format_error

    def _format_error_with_placement_hint(self: Any) -> None:
        # Parameter named `self`, matching Typer's own signature: it is called
        # unbound as rich_format_error(exc), so the name is part of the contract
        # mypy checks against.
        _orig_format_error(self)
        hint = _global_option_hint(self, sys.argv)
        if hint:
            _err_console.print(
                f"[dim]{getattr(self, 'option_name', '')} is a global option: "
                f"it goes before the subcommand.[/dim]\n    [bold]{hint}[/bold]"
            )

    _rich_utils.rich_format_error = _format_error_with_placement_hint
    try:
        yield
    finally:
        _rich_utils.rich_format_error = _orig_format_error
        for module, code in previous:
            module.exceptions.UsageError.exit_code = code


# The options declared on the root callback. A user reaching for one of these
# mid-command gets Click's bare "No such option", which is true and useless: the
# option exists, it is simply global, and nothing in the message says so or shows
# where it goes. Deriving that from a Typer/Click convention is not something a
# user can be expected to do.
_GLOBAL_OPTIONS = frozenset({"--version", "-V", "--no-color", "--force-color"})


def _global_option_hint(exc: Any, argv: list[str]) -> str | None:
    """Return a corrected invocation when a *global* option was placed too late.

    Returns None for a genuinely unknown option, so the hint stays specific: a
    message that called every typo "a global option" would be worse than the
    bare error it replaces.
    """
    name = getattr(exc, "option_name", None)
    if name not in _GLOBAL_OPTIONS:
        return None
    rest = [a for a in argv[1:] if a != name]
    return "zenzic " + " ".join([name, *rest])


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"Zenzic v{__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="zenzic",
    help=ROOT_HELP,
    rich_markup_mode="rich",
    no_args_is_help=True,
    rich_help_panel="Core",
    epilog=ROOT_EPILOG,
)


@app.callback()
def _main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show the Zenzic version and exit.",
        ),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option(
            "--no-color",
            help="Disable ANSI color and style output (also respects the NO_COLOR env var).",
            envvar="NO_COLOR",
        ),
    ] = False,
    force_color: Annotated[
        bool,
        typer.Option(
            "--force-color",
            help="Force ANSI color output even when stdout is not a TTY (also respects FORCE_COLOR env var).",
            envvar="FORCE_COLOR",
        ),
    ] = False,
) -> None:
    configure_console(no_color=no_color, force_color=force_color)


_SUB_APPS = {
    "adr": adr_app,
    "check": check_app,
    "clean": clean_app,
    "config": config_app,
    "guard": guard_app,
    "inspect": inspect_app,
}

_STANDALONE_COMMANDS = {
    "audit": audit,
    "lab": lab,
    "score": score,
    "diff": diff,
    "env": env,
    "explain": explain,
    "fix": fix,
    "init": init,
    "lsp": lsp,
    "doctor": doctor,
}

for cmd in COMMANDS:
    if cmd.name in _SUB_APPS:
        app.add_typer(
            _SUB_APPS[cmd.name],
            name=cmd.name,
            rich_help_panel=cmd.panel,
            help=cmd.short_help,
        )
    elif cmd.name in _STANDALONE_COMMANDS:
        _handler = cast(Callable[..., Any], _STANDALONE_COMMANDS[cmd.name])
        app.command(
            name=cmd.name,
            rich_help_panel=cmd.panel,
            help=cmd.short_help,
        )(_handler)


_err_console = Console(
    stderr=True,
    highlight=False,
    no_color=os.environ.get("NO_COLOR") is not None,
    force_terminal=True
    if os.environ.get("FORCE_COLOR") and not os.environ.get("NO_COLOR")
    else None,
)

_err_ui = ZenzicUI(_err_console)


def bootstrap_unicode() -> None:
    """Force UTF-8 stdio on Windows before Rich/logging start.

    This prevents code-page related crashes (e.g., cp1252) when Rich emits
    box drawing symbols or emoji in local terminals and CI runners.
    """
    if sys.platform != "win32":
        return

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _error_panel(exc: ZenzicError, *, border_style: str, title: str) -> None:
    """Render a styled error alert panel for a ZenzicError."""
    _err_ui.print_exception_alert(
        str(exc.message),
        context=dict(exc.context) if exc.context else None,
        title=title,
        border_style=border_style,
    )


def _print_banner() -> None:
    """Print the Zenzic Frame banner to stdout (same console as commands)."""
    get_ui().print_header(__version__)
    get_console().print()


def _handle_machine_readable_error(exc: ZenzicError, output_format: str) -> bool:
    """If the output format is json or sarif, serialize the error to stdout and return True.

    Otherwise, return False.
    """
    import json
    from pathlib import Path as _Path

    from rich.text import Text as _Text

    from zenzic.core.codes import CODE_DEFINITIONS
    from zenzic.core.validator import repo_relative_label

    filename = exc.context.get(
        "file", exc.context.get("file_path", exc.context.get("config_path", ".zenzic.toml"))
    )
    # Relative and POSIX, for the same reason every finding is: an absolute path
    # publishes the runner's directory layout to whoever reads the SARIF, and makes
    # two machines checking one commit produce payloads that do not compare equal.
    # The text panel deliberately keeps the absolute path -- config discovery walks
    # upward, so for a fatal startup diagnostic the full path is the answer a human
    # needs. Only the machine-readable forms are normalised here.
    filename = repo_relative_label(_Path(str(filename)), _Path.cwd())

    # The message was composed for a terminal. Serialising it unchanged handed
    # `[bold red]`, `[#64748b]` and `[/]` to every JSON and SARIF consumer, and a
    # code-scanning service renders those literally.
    message = _Text.from_markup(exc.message).plain
    # The message body repeats the path, so normalising only the `file` field
    # above left the absolute path in the payload anyway -- which is how the first
    # version of this fix passed its own markup test and failed its path test.
    # Both separator forms: the message was built from a Path, so on Windows it
    # carries `C:\\dir\\file` while `as_posix()` yields `C:/dir/file`. Stripping only
    # the POSIX form would leave the absolute path in the payload on exactly the
    # platform nobody checks by hand.
    _cwd_posix = _Path.cwd().as_posix()
    _cwd_native = str(_Path.cwd())
    for _form in (_cwd_posix + "/", _cwd_posix, _cwd_native + os.sep, _cwd_native):
        if _form:
            message = message.replace(_form, "")

    line = exc.context.get("line", exc.context.get("line_no", 1))
    code = getattr(exc, "code", "Z001") or "Z001"

    severity = exc.context.get("severity")
    if not severity:
        if code.startswith("Z0"):
            severity = "fatal"
        else:
            defn = CODE_DEFINITIONS.get(code)
            if defn:
                severity = "info" if defn.severity == "note" else defn.severity
            else:
                severity = "error"

    tier = exc.context.get("tier")
    if not tier:
        if code.startswith("Z0"):
            tier = "Core"
        elif code.startswith("Z1"):
            tier = "Link Integrity"
        elif code.startswith("Z2"):
            tier = "Security"
        elif code.startswith("Z3"):
            tier = "Reference Integrity"
        elif code.startswith("Z4"):
            tier = "Structure"
        elif code.startswith("Z5"):
            tier = "Content Quality"
        elif code.startswith("Z6"):
            tier = "Governance"
        else:
            tier = "Core"

    if output_format == "json":
        report = {
            "file": filename,
            "line": line,
            "code": code,
            "tier": tier,
            "severity": severity,
            "message": message,
        }
        print(json.dumps(report, indent=2))
        return True

    elif output_format == "sarif":
        sarif_level = "error"
        if severity in ("error", "fatal"):
            sarif_level = "error"
        elif severity == "warning":
            sarif_level = "warning"
        elif severity in ("info", "note"):
            sarif_level = "note"

        report = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "zenzic",
                            "version": __version__,
                            "informationUri": "https://zenzic.dev",
                            "rules": [],
                        }
                    },
                    "invocations": [
                        {
                            "executionSuccessful": False,
                            "toolExecutionNotifications": [
                                {
                                    "descriptor": {"id": code},
                                    "level": sarif_level,
                                    "message": {"text": message},
                                }
                            ],
                        }
                    ],
                    "results": [],
                }
            ],
        }
        print(json.dumps(report, indent=2))
        return True

    return False


def cli_main() -> None:
    """Wired as the `zenzic` console_scripts entry point."""
    from rich.traceback import install as _rich_tb_install

    bootstrap_unicode()
    _rich_tb_install(show_locals=True, suppress=[typer], word_wrap=True)
    setup_cli_logging()

    # Show an elegant banner on zero args, --help/-h at any nesting level,
    # or when a sub-app (check/clean/inspect) is invoked with no further args
    # — those hit no_args_is_help=True and show only Typer help without our frame.
    _SUBAPPS_WITH_MENU = frozenset({"check", "clean", "inspect"})
    if (
        len(sys.argv) == 1
        or any(arg in sys.argv for arg in ("--help", "-h"))
        or (len(sys.argv) == 2 and sys.argv[1] in _SUBAPPS_WITH_MENU)
    ):
        _print_banner()

    try:
        with _usage_errors_exit_1():
            app()
    except (SystemExit, KeyboardInterrupt):
        raise
    except PluginContractError as exc:
        _error_panel(
            exc,
            border_style=ZenzicPalette.STYLE_BRAND,
            title="Zenzic Plugin Contract Violation",
        )
        sys.exit(1)
    except ZenzicError as exc:
        output_format = "text"
        for i, arg in enumerate(sys.argv):
            if arg in ("--format", "-f") and i + 1 < len(sys.argv):
                output_format = sys.argv[i + 1]
            elif arg.startswith("--format="):
                output_format = arg.split("=", 1)[1]

        if _handle_machine_readable_error(exc, output_format):
            sys.exit(1)

        _error_panel(
            exc,
            border_style=ZenzicPalette.STYLE_ERR,
            title="Zenzic Error",
        )
        sys.exit(1)
    # Unexpected exceptions propagate to the global rich traceback handler
    # installed above — identical output to bump-my-version.


if __name__ == "__main__":  # pragma: no cover
    cli_main()
