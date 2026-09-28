# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic score`` must be able to run without validating external URLs.

Measured on CI run 35455833729, commit ``d99a008``: the ``Verify Badge
Freshness`` step computed **89/100** on Ubuntu 3.10 while Ubuntu 3.14 and
Windows computed 97 on the same commit, and a re-run of the identical commit
with no change produced 97 on all three. The gap is exactly one ``Z104``
(penalty 8.0) -- an external URL that did not answer from that runner.

The cause is that ``_run_all_checks()``, the path ``score`` takes, hardcoded
``check_external=True``, and ``score`` had no flag to turn it off. Three steps
above it in the same workflow, ``zenzic check all`` already runs
``--no-external`` with the reason written out: *the PR gate must not depend on
third-party uptime*, decided on run 34860816951 after nine github.com timeouts
turned a merge queue red. That decision was applied to one step and not to the
other, and the badge gate is the one that also writes a number into README.md.

This test does not assert that a network call happens -- it asserts the flag
reaches the scan, which is what the gate needs and what was missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text(
        "# Title\n\nA [link](https://zenzic-does-not-exist.invalid/page) to nowhere.\n",
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    return tmp_path


def test_score_accepts_no_external(tmp_path: Path, monkeypatch) -> None:
    """The flag exists on ``score`` and the command runs to a score with it."""
    monkeypatch.chdir(_project(tmp_path))
    result = runner.invoke(app, ["score", "--no-external", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "score" in payload, payload


def test_no_external_is_reflected_in_the_payload(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.chdir(project)

    seen: list[bool] = []
    from zenzic.cli import _standalone

    original = _standalone._run_all_checks

    def spy(*args, **kwargs):
        seen.append(bool(kwargs.get("check_external", True)))
        return original(*args, **kwargs)

    monkeypatch.setattr(_standalone, "_run_all_checks", spy)

    runner.invoke(app, ["score", "--no-external", "--json"], catch_exceptions=False)
    assert seen == [False], f"score did not pass check_external=False: {seen}"

    seen.clear()
    runner.invoke(app, ["score", "--json"], catch_exceptions=False)
    assert seen == [True], f"score changed its default: {seen}"
