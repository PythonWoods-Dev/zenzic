# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Behaviour that only a real terminal can distinguish.

Every other test in this suite runs under captured output, where ``isatty()`` is
False and ``get_terminal_size()`` returns its fallback. Code branching on those
answers therefore produces **identical output in its broken and correct states**,
and the assertion passes either way. That is how ``color_system=None`` disabled
colour for every interactive user with a fully green suite, from v0.8.0.

Four sites read the terminal. This file exercises each under a real pty, and
each test carries a control that can observe the *wrong* branch -- without one,
a passing assertion says nothing, which is the defect class being closed rather
than a stylistic preference.

Two harnesses, because the sites need different things:

``_tty_stdin`` gives the child a pty on **stdin** while stdout and stderr stay
separate pipes. ``script`` cannot be used for that: it merges both streams into
the pty, and the whole point of the language-server test is to prove which
stream a message landed on.

``_tty_stdout`` makes **stdout** the pty, at a caller-chosen width, because
``get_terminal_size`` interrogates the stdout descriptor.
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import struct
import subprocess
import sys
import tempfile
import termios

import pytest


pytestmark = pytest.mark.skipif(
    not hasattr(os, "openpty"), reason="needs a real pty; unavailable on Windows"
)


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain_lines(text: str) -> list[str]:
    """Rendered lines with colour codes removed and the pty's CR stripped."""
    return [_ANSI.sub("", ln).rstrip("\r") for ln in text.splitlines()]


def _widest_plain_line(text: str) -> int:
    """Widest rendered line, with colour codes removed.

    Measuring the raw string counts escape sequences as visible characters and
    reports a width the reader never sees -- which is how this assertion first
    "found" a 131-column line inside a 61-column terminal that was in fact
    exactly 61 columns wide.
    """
    return max((len(ln) for ln in _plain_lines(text)), default=0)


def _write_snippet(code: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(code)
        return fh.name


def _child_env(**extra: str) -> dict[str, str]:
    env = os.environ.copy()
    # COLUMNS short-circuits shutil.get_terminal_size before it ever asks the
    # terminal, so a width assertion would measure the environment instead of
    # the pty and pass whatever the code did.
    env.pop("COLUMNS", None)
    env.pop("LINES", None)
    env.setdefault("TERM", "xterm-256color")
    env.update(extra)
    return env


def _tty_stdin(code: str, **env: str) -> tuple[str, str]:
    """Run a snippet with a pty on stdin; return (stdout, stderr) separately."""
    path = _write_snippet(code)
    master, slave = pty.openpty()
    try:
        proc = subprocess.run(  # noqa: S603
            [sys.executable, path],
            stdin=slave,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=_child_env(**env),
        )
        return proc.stdout, proc.stderr
    finally:
        os.close(master)
        os.close(slave)
        os.unlink(path)


def _tty_stdout(code: str, cols: int = 143, rows: int = 24, **env: str) -> str:
    """Run a snippet with a pty on stdout, sized exactly ``cols`` x ``rows``."""
    path = _write_snippet(code)
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    try:
        proc = subprocess.Popen(  # noqa: S603
            [sys.executable, path],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=_child_env(**env),
        )
        os.close(slave)
        chunks: list[bytes] = []
        while True:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
        proc.wait(timeout=60)
        return b"".join(chunks).decode("utf-8", errors="replace")
    finally:
        os.close(master)
        if os.path.exists(path):
            os.unlink(path)


# ── Site 1: cli/_lsp.py -- sys.stdin.isatty() ────────────────────────────────


class TestTheLanguageServerHint:
    """The hint is cosmetic; the stream it uses is not.

    ``zenzic lsp`` speaks JSON-RPC over **stdout**. Anything else written there
    corrupts the wire, and an editor shows an extension that installed correctly
    and does nothing. The isatty() branch exists so a human who runs the command
    by hand is told what it is -- so it must write to stderr, and the test that
    matters is which stream, not whether the words appear.
    """

    SNIPPET = (
        "import sys\n"
        "sys.argv = ['zenzic', 'lsp']\n"
        "print('STDOUT-SENTINEL', flush=True)\n"
        "from zenzic.cli import _lsp\n"
        "print('ISATTY=', sys.stdin.isatty(), flush=True)\n"
    )

    def test_stdin_is_a_terminal_under_this_harness(self) -> None:
        """Control: without this, every assertion below tests the wrong branch."""
        out, _ = _tty_stdin(self.SNIPPET)
        assert "ISATTY= True" in out, (
            "the harness did not give the child a terminal on stdin, so the "
            f"interactive branch was never taken. stdout={out!r}"
        )

    def test_the_harness_can_tell_the_two_streams_apart(self) -> None:
        """Control: prove stdout and stderr are separable here.

        ``script`` merges them, which would make the next test pass no matter
        which stream the hint used.
        """
        out, err = _tty_stdin(
            "import sys\nsys.stdout.write('ON-STDOUT')\nsys.stderr.write('ON-STDERR')\n"
        )
        assert "ON-STDOUT" in out and "ON-STDOUT" not in err, f"streams merged: {out!r} {err!r}"
        assert "ON-STDERR" in err and "ON-STDERR" not in out, f"streams merged: {out!r} {err!r}"

    def test_the_hint_never_reaches_stdout(self) -> None:
        code = (
            "import sys, io\n"
            "from zenzic.lsp.server import LanguageServer\n"
            "import zenzic.cli._lsp as m\n"
            "LanguageServer.serve = lambda self: None\n"
            "LanguageServer.exit_code = 0\n"
            "try:\n"
            "    m.lsp()\n"
            "except SystemExit:\n"
            "    pass\n"
            "except Exception as exc:\n"
            "    sys.stderr.write('EXC:' + type(exc).__name__)\n"
        )
        out, err = _tty_stdin(code)
        assert "Language Server" not in out, (
            "the interactive hint was written to stdout, which is the JSON-RPC "
            f"wire -- this corrupts the protocol for every editor client. stdout={out!r}"
        )
        assert "Language Server" in err, (
            f"the hint did not appear on stderr either, so it was lost: stderr={err!r}"
        )

    def test_no_hint_when_stdin_is_not_a_terminal(self) -> None:
        """The editor case: a pipe must produce no chatter on either stream."""
        code = (
            "from zenzic.lsp.server import LanguageServer\n"
            "import zenzic.cli._lsp as m\n"
            "LanguageServer.serve = lambda self: None\n"
            "LanguageServer.exit_code = 0\n"
            "try:\n"
            "    m.lsp()\n"
            "except SystemExit:\n"
            "    pass\n"
        )
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=_child_env(),
        )
        assert "Language Server" not in proc.stdout
        assert "Language Server" not in proc.stderr, (
            "the hint fired for a non-interactive stdin, so an editor client "
            f"receives it too: {proc.stderr!r}"
        )


# ── Site 2: core/reporter.py -- shutil.get_terminal_size ─────────────────────


class TestTerminalWidthIsActuallyRead:
    SNIPPET = (
        "import shutil\nprint('COLS=', shutil.get_terminal_size(fallback=(120, 24)).columns)\n"
    )

    def test_a_narrow_and_a_wide_pty_are_distinguishable(self) -> None:
        """Control: the harness must observe two different widths.

        If both came back 120 the width assertions would be measuring the
        fallback, which is the state every captured-output test is already in.
        """
        narrow = _tty_stdout(self.SNIPPET, cols=61)
        wide = _tty_stdout(self.SNIPPET, cols=143)
        assert "COLS= 61" in narrow, f"narrow pty not observed: {narrow!r}"
        assert "COLS= 143" in wide, f"wide pty not observed: {wide!r}"

    def test_capture_sees_only_the_fallback(self) -> None:
        """The baseline this file exists to escape, asserted rather than assumed."""
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-c", self.SNIPPET],
            capture_output=True,
            text=True,
            check=False,
            env=_child_env(),
        )
        assert "COLS= 120" in proc.stdout, (
            "under capture the fallback was not used, so the contrast this file "
            f"draws does not hold: {proc.stdout!r}"
        )

    def test_the_source_excerpt_adapts_to_a_narrow_terminal(self) -> None:
        """reporter.py truncates the source line against the real width."""
        long_line = "ZXQV" * 75  # a token that appears nowhere else in the report
        code = (
            "from rich.console import Console\n"
            "from zenzic.core.reporter import ZenzicReporter, Finding\n"
            "import pathlib, tempfile\n"
            "d = pathlib.Path(tempfile.mkdtemp())\n"
            f"(d / 'a.md').write_text('# T\\n\\n{long_line}\\n', encoding='utf-8')\n"
            "r = ZenzicReporter(Console(), d)\n"
            "f = Finding(rel_path='a.md', line_no=3, code='Z101', severity='error',\n"
            f"            message='m', source_line='{long_line}', col_start=1)\n"
            "r.render([f], version='0.0.0', elapsed=0.0)\n"
        )
        for cols in (61, 143):
            rendered = _tty_stdout(code, cols=cols)
            lines = _plain_lines(rendered)
            carets = [ln for ln in lines if "\u2771" in ln]
            assert len(carets) == 1, f"expected one caret row at {cols} cols, got {len(carets)}"

            # This is the assertion that can see the wrong branch, and the width
            # of the output is not. Rich already crops to the console width, so a
            # reporter that truncates against a *hardcoded* 120 still produces
            # lines no wider than the terminal -- measuring width therefore passes
            # in both states, which is the vacuity this file exists to avoid.
            #
            # What actually changes is whether the excerpt fits on its own row.
            # Truncated against the real width it does. Truncated against 120 in a
            # 61-column terminal it wraps: the caret row is left empty and the
            # source spills onto continuation lines, so the caret no longer points
            # at the column it names -- the defect reporter.py's own comment cites.
            assert "ZXQV" in carets[0], (
                f"at {cols} columns the caret row carries no source text, so the "
                "excerpt wrapped onto continuation lines and the caret is "
                f"misaligned from the column it marks. Row: {carets[0]!r}"
            )
            spills = [ln for ln in lines if "ZXQV" in ln and "\u2771" not in ln]
            assert not spills, (
                f"at {cols} columns the source excerpt spilled onto "
                f"{len(spills)} continuation line(s): {spills!r}"
            )

        assert _widest_plain_line(_tty_stdout(code, cols=61)) <= 61
        assert _widest_plain_line(_tty_stdout(code, cols=143)) <= 143


# ── Sites 3 and 4: core/ui.py and the console construction paths ─────────────


class TestEveryDetectionPathAgrees:
    """Three independent detections exist. Disagreement is the failure mode.

    ``core/ui.py`` derives SUPPORTS_COLOR from ``sys.stderr``; the console in
    ``cli/_shared.py`` and the one reached through ``main.py`` derive their own.
    Nothing makes them consult each other, so they can drift apart silently --
    and under capture they agree on "no colour" whatever they do.
    """

    SNIPPET = (
        "from zenzic.core import ui\n"
        "from zenzic.cli import _shared\n"
        "import zenzic.main  # third construction path\n"
        "print('SUPPORTS_COLOR=', ui.SUPPORTS_COLOR)\n"
        "print('CONSOLE=', _shared.get_console().color_system)\n"
        "print('STDERR_CONSOLE=', _shared.stderr_console.color_system)\n"
    )

    def test_all_three_detect_colour_in_a_real_terminal(self) -> None:
        out = _tty_stdout(self.SNIPPET)
        assert "SUPPORTS_COLOR= True" in out, f"ui.py saw no terminal: {out!r}"
        assert "CONSOLE= None" not in out, f"the main console has no colour system: {out!r}"
        assert "STDERR_CONSOLE= None" not in out, f"the stderr console has none: {out!r}"

    def test_plain_rich_colours_here(self) -> None:
        """Positive control: if this fails the assertions above prove nothing."""
        out = _tty_stdout("from rich.console import Console\nConsole().print('[red]CTRL[/red]')")
        assert "\x1b[" in out, f"the harness cannot observe colour at all: {out!r}"

    def test_all_three_agree_that_a_pipe_has_no_colour(self) -> None:
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-c", self.SNIPPET],
            capture_output=True,
            text=True,
            check=False,
            env=_child_env(),
        )
        assert "SUPPORTS_COLOR= False" in proc.stdout, proc.stdout
        assert "CONSOLE= None" in proc.stdout, proc.stdout
