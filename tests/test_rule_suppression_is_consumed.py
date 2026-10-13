# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""An inline directive that silences a finding is consumed, so it is neither reported dead nor free.

Three rules checked their own line for a directive and skipped the finding without
telling the suppression ledger, so a directive that worked was reported dead
(``Z603``) beneath the finding it had removed. Each case runs the CLI in both
directions: without the directive the finding fires; with it the finding is gone
and no ``Z603`` is raised.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ZENZIC = Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")
BODY = "Neutral paragraph long enough that no short-content check applies to this fixture page.\n"

# code: (page without directive, page with directive, extra toml)
CASES = {
    "Z107": (
        f"# Page\n\n{BODY}\n## Setup\n\nSee [Setup](#setup).\n",
        f"# Page\n\n{BODY}\n## Setup\n\nSee [Setup](#setup). <!-- zenzic:ignore: Z107 -->\n",
        "",
    ),
    "Z506": (
        f"--\ntitle: x\n---\n\n# Page\n\n{BODY}",
        f"-- <!-- zenzic:ignore: Z506 -->\ntitle: x\n---\n\n# Page\n\n{BODY}",
        "",
    ),
    "Z601": (
        f"# Page\n\n{BODY}\nOldBrand is mentioned here.\n",
        f"# Page\n\n{BODY}\nOldBrand is mentioned here. <!-- zenzic:ignore: Z601 -->\n",
        '[governance]\nbrand_obsolescence = ["OldBrand"]\n',
    ),
}


def _codes(tmp_path: Path, page: str, extra: str) -> list[str]:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text(page, encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n' + extra, encoding="utf-8")
    run = subprocess.run(
        [str(ZENZIC), "check", "all", "--no-external", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return [f["code"] for f in json.loads(run.stdout)["findings"]]


@pytest.mark.parametrize("code", sorted(CASES))
def test_without_the_directive_the_finding_fires(tmp_path: Path, code: str) -> None:
    bare, _, extra = CASES[code]
    assert code in _codes(tmp_path, bare, extra)


@pytest.mark.parametrize("code", sorted(CASES))
def test_a_directive_that_silences_is_not_reported_dead(tmp_path: Path, code: str) -> None:
    _, suppressed, extra = CASES[code]
    codes = _codes(tmp_path, suppressed, extra)
    assert code not in codes, f"{code} still fires: {codes}"
    assert "Z603" not in codes, f"the directive silenced {code} and was reported dead: {codes}"


def test_a_directive_on_a_fence_opener_is_a_language_tag_not_a_suppression(tmp_path: Path) -> None:
    """Z505 cannot be suppressed inline: any text after the backticks is an info string.

    The directive therefore produces no finding to silence and no dead directive to
    report -- the case behaves, but not because suppression worked.
    """
    page = f"# Page\n\n{BODY}\n``` <!-- zenzic:ignore: Z505 -->\nplain\n```\n"
    codes = _codes(tmp_path, page, "")
    assert "Z505" not in codes and "Z603" not in codes, codes
