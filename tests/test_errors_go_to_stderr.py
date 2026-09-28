# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""An error message belongs on stderr, where a pipeline looks for it.

`zenzic check all --engine hugo` printed its diagnosis -- the unknown name and
the list of installed adapters -- to *stdout*, while stderr received only
``ERROR: 1``. A caller redirecting stderr to a log, which is what CI does, kept
the useless half and discarded the half that says what went wrong.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    shutil.which("zenzic") is None, reason="the zenzic console script is not on PATH"
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["zenzic", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# T\n\nSome prose here.\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\nfail_under = 0\n\n[build_context]\nengine = "standalone"\n',
        encoding="utf-8",
    )
    return tmp_path


def test_unknown_adapter_diagnosis_is_on_stderr(project: Path) -> None:
    result = _run(["check", "all", "--engine", "hugo", "--no-header"], project)
    assert result.returncode != 0
    assert "Unknown engine adapter" in result.stderr, (
        f"the diagnosis went somewhere else.\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "Unknown engine adapter" not in result.stdout


def test_a_successful_run_still_writes_its_report_to_stdout(project: Path) -> None:
    """Positive control: without it, the test above passes if everything moved.

    Only diagnostics belong on stderr -- the report itself must stay on stdout,
    or `zenzic check ... > report.txt` captures nothing.
    """
    result = _run(["check", "all", "--no-header"], project)
    assert result.returncode == 0
    assert result.stdout.strip(), f"stdout was empty; stderr={result.stderr!r}"
