# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A link to a LICENSE that exists resolves; a link to one that does not still reports.

`SYSTEM_EXCLUDED_FILE_NAMES` keeps LICENSE, NOTICE and COPYING out of the
analysed corpus — they are not documentation, which is right and stays. It also
kept them out of the *static asset* index, which nothing ever argued for, and
`VSMBrokenLinkRule` reports any target absent from the site map as `Z101`. The
result was a broken-link error on a file that exists and whose link works on
GitHub (measured 2026-09-18 with `docs_dir = "docs"` and the standalone engine,
so this is not the `docs_dir = "."` case).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


COVERED = ("LICENSE", "LICENSE.txt", "LICENSE.md", "NOTICE", "NOTICE.txt", "COPYING")


def _project(tmp_path: Path, *, present: tuple[str, ...], links: tuple[str, ...]) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n[build_context]\nengine = "standalone"\n', encoding="utf-8"
    )
    for name in present:
        (root / "docs" / name).write_text("Legal text.\n", encoding="utf-8")
    body = " and ".join(f"[{n}](./{n})" for n in links)
    (root / "docs" / "index.md").write_text(
        f"# Home\n\nSee {body} for the terms.\nMore ordinary prose so that no other rule "
        "fires on this page during the run at all, with enough words to pass the check.\n",
        encoding="utf-8",
    )
    return root


def _findings(root: Path) -> list[dict[str, object]]:
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all", "--no-header", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return list(json.loads(done.stdout).get("findings", []))


@pytest.mark.parametrize("name", COVERED)
def test_a_link_to_a_legal_file_that_exists_reports_nothing(tmp_path: Path, name: str) -> None:
    root = _project(tmp_path, present=(name,), links=(name,))
    broken = [f for f in _findings(root) if f["code"] in ("Z101", "Z104")]
    assert not broken, f"{name} exists and is linked, yet: {broken}"


@pytest.mark.parametrize("name", COVERED)
def test_a_link_to_a_legal_file_that_is_absent_still_reports(tmp_path: Path, name: str) -> None:
    """The positive control the fix must not silence: a genuinely missing LICENSE."""
    root = _project(tmp_path, present=(), links=(name,))
    broken = [f for f in _findings(root) if f["code"] in ("Z101", "Z104")]
    assert broken, f"{name} is absent and linked, and nothing reported it"


def test_the_legal_file_is_still_not_analysed_as_documentation(tmp_path: Path) -> None:
    """The exclusion's own stated purpose survives: the file is indexed as an
    asset, never scanned as a page, so its prose produces no content finding."""
    root = _project(tmp_path, present=("LICENSE",), links=("LICENSE",))
    (root / "docs" / "LICENSE").write_text(
        "# A heading in a licence.\n\n## And another one.\n\nhttp://bare.example.com\n",
        encoding="utf-8",
    )
    findings = _findings(root)
    from_license = [f for f in findings if str(f.get("rel_path", "")).endswith("LICENSE")]
    assert not from_license, f"LICENSE was analysed as documentation: {from_license}"
