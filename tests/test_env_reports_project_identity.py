# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`zenzic env` reports what Zenzic takes the project to be, and agrees with a scan.

Until 2026-09-19 the engine appeared in exactly one place a user could read it:
the telemetry line of a scan. An editor extension had no way to ask, and a user
whose engine did not match their generator had to infer the mismatch from the
findings. These pin the two new fields and, more importantly, pin them to the
answer `zenzic check` gives for the same project.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _env(cwd: Path) -> dict[str, object]:
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "env", "--json"],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    parsed: dict[str, object] = json.loads(out.stdout[out.stdout.find("{") :])
    return parsed


def _astro(tmp_path: Path) -> Path:
    (tmp_path / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")
    docs = tmp_path / "src" / "content" / "docs"
    docs.mkdir(parents=True)
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "src/content/docs"\n', encoding="utf-8")
    return tmp_path


def test_a_detected_generator_is_named(tmp_path: Path) -> None:
    assert _env(_astro(tmp_path))["generator"] == "astro"


def test_a_native_engine_reports_that_the_question_does_not_apply(tmp_path: Path) -> None:
    """Three states, not two.

    "none detected" on an MkDocs project reads as a detection that failed. The
    engine reads its generator's own configuration, so nothing was looked for.
    Reported as a field rather than re-derived per surface, so the CLI and the
    editor extension cannot disagree about which engines are native.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Probe\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")

    env = _env(tmp_path)

    assert env["engine"] == "mkdocs"
    assert env["generator"] is None
    assert env["generator_applies"] is False


def test_a_generator_agnostic_engine_reports_that_it_does_apply(tmp_path: Path) -> None:
    assert _env(_astro(tmp_path))["generator_applies"] is True


def test_a_project_with_no_generator_says_so_rather_than_guessing(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / ".zenzic.toml").touch()

    assert _env(tmp_path)["generator"] is None


def test_the_engine_is_the_resolved_one_not_the_declared_one(tmp_path: Path) -> None:
    """`auto` is resolved here, because a scan resolves it before printing it.

    Reporting `"auto"` would make this command disagree with the telemetry line
    for the same project — two answers to one question.
    """
    env = _env(_astro(tmp_path))

    assert env["engine"] == "standalone"
    assert env["engine_source"] == "auto-detected"


def test_a_configured_engine_is_reported_as_configured(tmp_path: Path) -> None:
    project = _astro(tmp_path)
    (project / ".zenzic.toml").write_text(
        'docs_dir = "src/content/docs"\n\n[build_context]\nengine = "prebuilt"\n',
        encoding="utf-8",
    )

    env = _env(project)

    assert env["engine"] == "prebuilt"
    assert env["engine_source"] == "configured"


def test_env_and_the_scan_name_the_same_engine(tmp_path: Path) -> None:
    """The claim that makes the field worth having.

    A diagnostics command that reports a different engine from the one the scan
    runs is worse than no diagnostics command: it is a confident wrong answer.
    """
    project = _astro(tmp_path)
    subprocess.run(["git", "init", "-q", "."], cwd=project, check=True)  # noqa: S607

    env_engine = _env(project)["engine"]
    scan = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )

    telemetry = next(
        (ln for ln in scan.stdout.splitlines() if "files" in ln and "s" in ln and "•" in ln),
        "",
    )
    assert telemetry, f"no telemetry line in:\n{scan.stdout}"
    assert str(env_engine) in telemetry


def test_a_broken_configuration_does_not_break_the_diagnostics(tmp_path: Path) -> None:
    """`env` is what a user runs when something else is already wrong."""
    (tmp_path / ".zenzic.toml").write_text("this is not [valid toml\n", encoding="utf-8")

    env = _env(tmp_path)  # must not raise, must not exit non-zero

    assert env["zenzic_version"]
    assert env["engine"]
