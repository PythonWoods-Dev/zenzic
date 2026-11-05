# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The source distribution takes the tracked tree and nothing else.

Hatchling leaves out what `.gitignore` names, and nothing else: a folder a clone excludes only locally, through its own
`info/exclude`, went into an sdist built on that clone (207 files, measured on 2026-11-04). The sdist is therefore an
explicit list of the tracked top-level entries, and this test keeps the list equal to what git tracks: a new top-level
file or folder has to join it, and nothing untracked can.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _tracked_top_level() -> set[str]:
    names = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    return {name.split("/")[0] for name in names if name}


def test_the_sdist_lists_exactly_the_tracked_top_level_entries() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sdist = config["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert set(sdist["only-include"]) == _tracked_top_level()
