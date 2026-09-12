# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A fatal config error must serialise for a machine, not for a terminal.

Found while sweeping the external-link path fix for other occurrences of the same
construction. Ordinary findings were clean; the fatal config path was not, and it
is the one that reaches a machine consumer in two ways at once.

``--format json`` and ``--format sarif`` emitted the config file's **absolute**
path, so a SARIF file uploaded from CI carried the runner's directory layout and
two runs of the same commit on different machines compared unequal.

The same records carried **raw Rich markup** in ``message`` -- ``[bold red]``,
``[#64748b]``, ``[/]`` -- because the string was written for a terminal and
handed to a serialiser unchanged. GitHub Code Scanning renders that literally.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    shutil.which("zenzic") is None, reason="needs the installed zenzic console script"
)

BROKEN_TOML = 'docs_dir = "docs"\nfail_under = not-a-value\n'
_MARKUP = re.compile(r"\[/?[a-z#][^\]]*\]")


@pytest.fixture
def broken_project(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# T\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(BROKEN_TOML, encoding="utf-8")
    return tmp_path


ZENZIC = shutil.which("zenzic")


def _run(project: Path, fmt: str) -> str:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["COLUMNS"] = "400"
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "all", "--no-header", "--format", fmt],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return proc.stdout + proc.stderr


def test_the_instrument_reaches_the_fatal_config_path(broken_project: Path) -> None:
    """Control: without a real config error the assertions below are vacuous."""
    out = _run(broken_project, "json")
    assert "Z110" in out or "Z001" in out or "Z111" in out, (
        f"no fatal config code was emitted, so this fixture is not exercising "
        f"the path under test: {out[:400]!r}"
    )


class TestJson:
    def test_the_file_field_is_not_absolute(self, broken_project: Path) -> None:
        payload = json.loads(_run(broken_project, "json"))
        assert not Path(payload["file"]).is_absolute(), (
            f"the JSON report names the config file by absolute path "
            f"({payload['file']!r}), leaking the machine's directory layout and "
            "making two runs of one commit incomparable."
        )
        assert str(broken_project) not in json.dumps(payload), (
            "the project's absolute root appears somewhere in the JSON payload"
        )

    def test_the_message_carries_no_terminal_markup(self, broken_project: Path) -> None:
        payload = json.loads(_run(broken_project, "json"))
        leftover = _MARKUP.findall(payload["message"])
        assert not leftover, (
            f"Rich markup reached the JSON consumer: {leftover!r}. The message was "
            "written for a terminal and serialised unchanged."
        )


class TestSarif:
    def test_no_absolute_path_anywhere_in_the_sarif(self, broken_project: Path) -> None:
        raw = _run(broken_project, "sarif")
        assert str(broken_project) not in raw, (
            "the SARIF payload contains the absolute project root; uploaded to a "
            "code-scanning service it publishes the runner's directory layout."
        )

    def test_no_terminal_markup_anywhere_in_the_sarif(self, broken_project: Path) -> None:
        raw = _run(broken_project, "sarif")
        leftover = _MARKUP.findall(raw)
        assert not leftover, f"Rich markup reached the SARIF consumer: {leftover[:5]!r}"

    def test_the_sarif_is_still_valid_json_naming_the_file(self, broken_project: Path) -> None:
        """The fix must not empty the field it was cleaning."""
        payload = json.loads(_run(broken_project, "sarif"))
        blob = json.dumps(payload)
        assert ".zenzic.toml" in blob, (
            "the config file is no longer identifiable in the SARIF output, so the "
            "path was removed rather than made relative"
        )


def test_the_human_panel_still_tells_the_user_which_file(broken_project: Path) -> None:
    """Positive control for the other direction: text output must stay useful.

    The absolute path is deliberately kept here. Config discovery walks upward,
    so the file that failed may sit above the working directory, and for a fatal
    startup diagnostic the full path is the answer the reader needs.
    """
    out = _run(broken_project, "text")
    assert ".zenzic.toml" in out, f"the text panel no longer names the file: {out[:300]!r}"
