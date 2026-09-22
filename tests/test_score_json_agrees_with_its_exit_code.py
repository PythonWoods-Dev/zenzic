# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic score --format json`` must not contradict its own exit code.

Measured 2026-09-18 on a project with ``fail_under = 97`` and a real score of
96: the command exited **1** while its payload said ``"threshold": 0`` and
``"status": "success"``. Three statements about the same run, two of them
false — and a consumer deciding on ``status`` rather than on the exit code got
the opposite verdict.

The cause was a single misplaced line: ``report.threshold = effective_threshold``
lived inside ``if save:``, so the threshold that decided the exit code reached
the payload only when ``--save`` was also passed. The field's own comment said
"fail_under value at save time", which described the defect rather than the
intent.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()

_FIVE_EMPTY_SECTIONS = "# Title\n\n## One\n\n## Two\n\n## Three\n\n## Four\n\n## Five\n\nBody.\n"


def _project(tmp_path: Path, *, fail_under: int) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text(_FIVE_EMPTY_SECTIONS, encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        f'docs_dir = "docs"\nfail_under = {fail_under}\n\n[governance]\nsuppression_cap = 0\n',
        encoding="utf-8",
    )
    return tmp_path


def _score_json(project: Path) -> tuple[int, dict[str, object]]:
    result = runner.invoke(
        app, ["score", "--format", "json"], catch_exceptions=False, env={"PWD": str(project)}
    )
    start = result.stdout.index("{")
    return result.exit_code, json.loads(result.stdout[start:])


def test_threshold_in_the_payload_is_the_one_that_decided_the_exit(
    tmp_path: Path, monkeypatch
) -> None:
    """A payload reporting ``threshold: 0`` on a run gated at 97 is a false statement."""
    project = _project(tmp_path, fail_under=97)
    monkeypatch.chdir(project)
    exit_code, payload = _score_json(project)

    assert payload["score"] == 96, "the fixture must score below the threshold"
    assert payload["threshold"] == 97, "the payload must name the threshold that was applied"
    assert exit_code == 1, "96 is below 97, so the run fails"


def test_status_agrees_with_the_exit_code(tmp_path: Path, monkeypatch) -> None:
    """``status`` is what a consumer reads instead of the exit code; it must not disagree."""
    project = _project(tmp_path, fail_under=97)
    monkeypatch.chdir(project)
    exit_code, payload = _score_json(project)

    assert (payload["status"] == "success") == (exit_code == 0), (
        f"status={payload['status']!r} contradicts exit={exit_code}"
    )
    assert payload["status"] == "failing"


def test_a_run_above_its_threshold_still_reports_success(tmp_path: Path, monkeypatch) -> None:
    """The positive control: the assertion above must not pass by always demanding failure."""
    project = _project(tmp_path, fail_under=50)
    monkeypatch.chdir(project)
    exit_code, payload = _score_json(project)

    assert payload["threshold"] == 50
    assert payload["status"] == "success"
    assert exit_code == 0
