# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Suppression debt counts declared exceptions that are in use -- every kind, and only those.

A suppression is one declared decision to look away, and it costs one point. Two
things contradicted that: a directory policy, which is exactly such a declaration,
cost nothing; and an inline directive or a per-file entry that silenced nothing
still cost a point, although it is also reported as dead. Each case below runs the
real CLI on a one-page project with a broken link, in both directions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ZENZIC = Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")

LIVE = "# Page\n\nSee [missing](missing.md) here.\n"
LIVE_INLINE = "# Page\n\nSee [missing](missing.md) here. <!-- zenzic:ignore: Z101 -->\n"
CLEAN = "# Other\n\nNothing broken on this page.\n"
CLEAN_INLINE = "# Other\n\nNothing broken on this page. <!-- zenzic:ignore: Z101 -->\n"

CASES = {
    # name: (page.md, other.md, extra toml, expected suppression_count, code that must be reported)
    "no-suppression": (LIVE, CLEAN, "", 0, "Z101"),
    "inline-in-use": (LIVE_INLINE, CLEAN, "", 1, None),
    "inline-dead": (LIVE, CLEAN_INLINE, "", 0, "Z603"),
    "per-file-in-use": (
        LIVE,
        CLEAN,
        '[governance.per_file_ignores]\n"docs/page.md" = ["Z101"]\n',
        1,
        None,
    ),
    "per-file-dead": (
        LIVE,
        CLEAN,
        '[governance.per_file_ignores]\n"docs/other.md" = ["Z101"]\n',
        0,
        "Z620",
    ),
    "directory-policy-in-use": (
        LIVE,
        CLEAN,
        '[governance.directory_policies]\n"docs/**" = ["Z101"]\n',
        1,
        None,
    ),
    "directory-policy-dead": (
        LIVE,
        CLEAN,
        '[governance.directory_policies]\n"docs/none/**" = ["Z101"]\n',
        0,
        "Z620",
    ),
}


def _project(tmp_path: Path, page: str, other: str, extra: str) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text(page, encoding="utf-8")
    (tmp_path / "docs" / "other.md").write_text(other, encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n' + extra, encoding="utf-8")
    return tmp_path


def _json(args: list[str], cwd: Path) -> dict[str, Any]:
    run = subprocess.run([str(ZENZIC), *args], cwd=cwd, capture_output=True, text=True, check=False)
    payload: dict[str, Any] = json.loads(run.stdout)
    return payload


@pytest.mark.parametrize("name", sorted(CASES))
def test_score_counts_only_suppressions_in_use(tmp_path: Path, name: str) -> None:
    page, other, extra, expected, _ = CASES[name]
    project = _project(tmp_path, page, other, extra)
    report = _json(["score", "--format", "json"], project)
    assert report["suppression_count"] == expected, (
        f"{name}: {report['suppression_count']} != {expected}"
    )


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_dead_suppression_is_still_reported(tmp_path: Path, name: str) -> None:
    """Not charging a dead suppression must not hide it: the dead-configuration codes still fire."""
    page, other, extra, _, must_report = CASES[name]
    if must_report is None:
        pytest.skip("a suppression in use silences its finding; nothing to report")
    project = _project(tmp_path, page, other, extra)
    codes = [
        f["code"]
        for f in _json(["check", "all", "--no-external", "--format", "json"], project)["findings"]
    ]
    assert must_report in codes, f"{name}: {must_report} missing from {codes}"


def test_the_check_all_payload_counts_the_same_way(tmp_path: Path) -> None:
    page, other, extra, expected, _ = CASES["directory-policy-in-use"]
    project = _project(tmp_path, page, other, extra)
    report = _json(["check", "all", "--no-external", "--format", "json"], project)
    assert report["suppression_count"] == expected
