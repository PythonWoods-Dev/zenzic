# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Auto-detected colour must survive in a real terminal.

Rich's `color_system` parameter defaults to the STRING "auto". Passing None
explicitly does not mean "auto-detect" -- it means "this console has no colour
system", which disables colour unconditionally. The two look identical in a
conditional expression, and the difference is invisible in any test whose
stdout is a pipe, because there is no colour either way.

That is why this shipped: every existing test runs under pytest with captured
output, where `is_terminal` is False and the expected output is monochrome
regardless. Only a real TTY distinguishes the two.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import pytest


# `script` is a util-linux tool: it does not exist on Windows, and there is no
# drop-in equivalent that gives a child process a real pty from pytest. Skipping
# is honest here -- the alternative is a test that silently proves nothing on
# that platform, which is the defect class this file was written to catch.
pytestmark = pytest.mark.skipif(
    shutil.which("script") is None,
    reason="needs `script` for a real pty; absent on Windows",
)


def _in_pty(code: str, **env: str) -> str:
    """Run a snippet under a real pty so Rich sees a terminal.

    The snippet is written to a file rather than inlined: quoting Python source
    through `script -c` and a shell mangles brackets, and a quoting failure
    would look exactly like the defect under test.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(code)
        script_path = fh.name
    assignments = "".join(f"{k}={v} " for k, v in env.items())
    try:
        return subprocess.run(
            [
                "script",
                "-qec",
                f"TERM=xterm-256color {assignments}{sys.executable} {script_path}",
                "/dev/null",
            ],
            capture_output=True,
            # encoding/errors are explicit: on Windows `text=True` decodes with the
            # locale codec (cp1252), which cannot read the CLI's UTF-8 box-drawing
            # output. The decode fails, stdout comes back None, and every assertion
            # below dies on a TypeError that names nothing real.
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
    finally:
        os.unlink(script_path)


def test_auto_console_has_a_colour_system_in_a_terminal() -> None:
    """The defect: color_system is None, so nothing is ever coloured."""
    out = _in_pty('from zenzic.cli._shared import console; print("CS=", console.color_system)')
    assert "CS= None" not in out, (
        "auto console has no colour system in a real terminal -- "
        f"colour is disabled for every user by default. Got: {out.strip()}"
    )


def test_auto_console_emits_ansi_in_a_terminal() -> None:
    out = _in_pty("from zenzic.cli._shared import console; console.print('[red]X[/red]')")
    assert "\x1b[" in out, f"no ANSI emitted in a real terminal: {out!r}"


def test_no_color_env_still_suppresses_colour() -> None:
    """The fix must not break NO_COLOR (https://no-color.org)."""
    out = _in_pty(
        "from zenzic.cli._shared import console\nconsole.print('[red]X[/red]')",
        NO_COLOR="1",
    )
    assert "\x1b[31m" not in out, f"NO_COLOR did not suppress colour: {out!r}"


def test_the_pty_harness_itself_works() -> None:
    """Positive control: plain Rich MUST colour here, or the tests above are vacuous."""
    out = _in_pty("from rich.console import Console\nConsole().print('[red]CTRL[/red]')")
    assert "\x1b[" in out, f"harness cannot observe colour at all: {out!r}"
