# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""What a command does when `docs_dir` is not there, decided once.

Five answers across the CLI on 2026-09-19, of which four said nothing about
having chosen:

* `check all` raised `Z111` and exited 1 — the one that had been corrected;
* `audit` set `docs_root = repo_root` and reported on a corpus nobody named;
* **`guard scan` returned zero targets and exited 0** — a passing secret scan
  over a tree it never opened, byte-identical in its output to a clean run;
* the language server widened to the repository, silently;
* the telemetry counter reported zero pages.

The three that must fail now do so through `_shared.docs_dir_missing_error`.
The editor, which has no channel to fail through, widens *and says so* on the
configuration file.

The separation `Z111`/`Z906` holds throughout: a directory that does not exist
is a configuration error; a directory that exists and holds nothing scannable
is a project in setup, and keeps exit 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _project(tmp_path: Path, *, make_docs: bool) -> Path:
    (tmp_path / "src" / "content" / "docs").mkdir(parents=True)
    (tmp_path / "src" / "content" / "docs" / "index.md").write_text(
        "# Home\n\n" + " ".join(["word"] * 60) + "\n", encoding="utf-8"
    )
    if make_docs:
        (tmp_path / "docs").mkdir()
    (tmp_path / ".zenzic.toml").write_text("# docs_dir left at its default\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", *args],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )


@pytest.mark.parametrize(
    "command",
    [["check", "all"], ["audit"], ["guard", "scan"]],
    ids=["check", "audit", "guard"],
)
def test_a_command_that_examined_nothing_fails(tmp_path: Path, command: list[str]) -> None:
    out = _run(_project(tmp_path, make_docs=False), *command)

    assert out.returncode == 1, f"exit {out.returncode}\n{out.stdout}\n{out.stderr}"
    assert "Z111" in (out.stdout + out.stderr)


@pytest.mark.parametrize(
    "command",
    [["check", "all"], ["guard", "scan"]],
    ids=["check", "guard"],
)
def test_a_directory_that_exists_and_is_empty_is_not_an_error(
    tmp_path: Path, command: list[str]
) -> None:
    """The other half of the separation, and the reason it is not just
    'fail when there is nothing': a project in setup is not misconfigured."""
    out = _run(_project(tmp_path, make_docs=True), *command)

    assert out.returncode == 0, f"exit {out.returncode}\n{out.stdout}\n{out.stderr}"
    assert "Z111" not in (out.stdout + out.stderr)


def test_the_message_names_the_generator_it_found(tmp_path: Path) -> None:
    """One message, so the advice cannot drift between the three commands."""
    project = _project(tmp_path, make_docs=False)
    (project / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")

    for command in (["check", "all"], ["audit"], ["guard", "scan"]):
        out = _run(project, *command)
        combined = out.stdout + out.stderr
        assert "Astro" in combined, f"{command}: {combined}"
        assert "src/content/docs" in combined, f"{command}: {combined}"


def test_the_editor_widens_and_says_so(tmp_path: Path) -> None:
    """The language server has no channel to fail through, so it reports.

    Going dark would leave the author with no diagnostics at all; widening in
    silence made the editor and CI disagree with nothing on screen to explain
    it. It now publishes Z111 on the configuration file.
    """
    from zenzic.core.adapter import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.models.config import ZenzicConfig
    from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap

    project = _project(tmp_path, make_docs=False)
    config, _ = ZenzicConfig.load(project)
    docs_root = project.resolve()  # what the server falls back to

    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=_build_rule_engine(config, containers=None),
        adapter=get_adapter(config.build_context, docs_root, project),
        docs_root=docs_root,
        repo_root=project,
    )
    vsm = VirtualSiteMap()
    results = engine.process_changes(vsm, VirtualBufferOverlay(vsm, tabs=None))

    codes = {d.code for diags in results.values() for d in diags}
    assert "Z111" in codes, f"the editor widened in silence; codes were {sorted(codes)}"
