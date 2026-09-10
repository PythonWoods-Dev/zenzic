# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A global option used after a subcommand must say where it belongs.

`zenzic lab z201 --force-color` failed with "No such option: --force-color" and
nothing else. The option exists; it is global, so it has to precede the
subcommand. A user has no way to derive that from the message, and the four
global options are exactly the ones a user reaches for mid-command.

This is the third instance of one shape in this cycle -- `--only` validated then
ignored, `--format` accepted then inert, and now an option that exists where
nobody looks. The first two were about a flag that did nothing; this one is
about a flag that does something, somewhere the error refuses to name.

The hint is asserted on more than one subcommand, because a fix written against
`lab` alone would pass a single-subcommand test and leave every other command
with the bare message.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


GLOBALS = ("--force-color", "--no-color")
SUBCOMMANDS = ("lab", "check", "score", "fix", "doctor")


def _run(*args: str) -> str:
    """Invoke the real console script -- the path a user actually takes."""
    exe = shutil.which("zenzic") or str(Path(sys.executable).parent / "zenzic")
    proc = subprocess.run([exe, *args], capture_output=True, text=True)
    return proc.stdout + proc.stderr


class TestPlacementHint:
    def test_every_subcommand_names_the_correct_position(self) -> None:
        """The message must show the working invocation, not merely say 'global'."""
        for sub in SUBCOMMANDS:
            out = _run(sub, "--force-color")
            assert "--force-color" in out, (sub, out)
            assert "global option" in out.lower(), (sub, out)
            assert f"zenzic --force-color {sub}" in out, (
                f"{sub}: the hint must show the position that works, got:\n{out}"
            )

    def test_no_color_gets_the_same_hint(self) -> None:
        out = _run("lab", "--no-color")
        assert "zenzic --no-color lab" in out, out

    def test_a_genuinely_unknown_option_is_not_given_a_false_hint(self) -> None:
        """Control: the hint must be specific to real global options."""
        out = _run("lab", "--not-a-real-option")
        assert "global option" not in out.lower(), (
            f"a nonexistent option was described as global:\n{out}"
        )

    def test_the_working_position_actually_works(self) -> None:
        """The hint would be worthless if the position it names also failed."""
        out = _run("--force-color", "score", "--help")
        assert "No such option" not in out, out
