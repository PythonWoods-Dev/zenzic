# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The list-continuation check scans the folders it is given, besides `docs/`.

A folder that is not public (drafts outside the repository's tracked tree) is
passed by the clone that has it, so the public script names no such folder.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_list_continuation.py"


def test_a_folder_given_on_the_command_line_is_scanned(tmp_path: Path) -> None:
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "post.md").write_text(
        "1. An item.\n\n  Its paragraph, indented two spaces, leaves the list.\n", encoding="utf-8"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(drafts)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "post.md:1" in done.stdout, done.stdout
