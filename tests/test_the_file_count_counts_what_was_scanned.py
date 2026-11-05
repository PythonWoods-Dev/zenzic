# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The telemetry line must count the trees the run actually read.

`docs/how-to/configure-adapter.md` uses the file count as the signal that a
second content tree is being missed — "it does not appear in the file count and
produces no findings either way" — and tells the reader to add it with
`content_roots`. Measured 2026-09-21: adding it makes the tree produce findings
and leaves the count unchanged, so the one confirmation the documentation offers
does not arrive.

`_count_docs_assets` walks `docs_root` and, since locale support landed, the
adapter's locale source roots. `content_roots` is a third mechanism and was not
walked: a Docusaurus `blog/`, or any tree a generator publishes that `docs_dir`
does not name, is scanned and not counted.

The direction that matters is asymmetric. An undercount on a tree that *is*
scanned is a reader told less than the run did; the reverse — counting a tree
nothing reads — would be the worse defect, so the second test pins it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_PROSE = " ".join(["word"] * 60)


def _project(tmp_path: Path, *, declare: bool, extra_pages: int) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text(f"# d\n\n{_PROSE}\n", encoding="utf-8")
    (tmp_path / "second").mkdir()
    for i in range(extra_pages):
        (tmp_path / "second" / f"p{i}.md").write_text(f"# s{i}\n\n{_PROSE}\n", encoding="utf-8")
    roots = 'content_roots = ["second"]\n' if declare else ""
    (tmp_path / ".zenzic.toml").write_text(
        f'docs_dir = "docs"\n{roots}\n[build_context]\nengine = "standalone"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _pages_reported(project: Path) -> int:
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )
    for line in (out.stdout + out.stderr).splitlines():
        if "pages" in line and "file" in line:
            for token in line.replace("(", " ").replace(",", " ").split():
                if token.isdigit():
                    continue
            parts = line.split("(", 1)[1].split()
            return int(parts[0])
    raise AssertionError(f"no telemetry line in:\n{out.stdout}\n{out.stderr}")


def test_a_declared_content_root_is_counted(tmp_path: Path) -> None:
    """Six pages are read; six is what the reader must be told."""
    project = _project(tmp_path, declare=True, extra_pages=5)

    assert _pages_reported(project) == 6, (
        "the run scanned `second/` -- it reports findings there -- and the count "
        "still describes `docs/` alone, which is the confirmation the how-to "
        "promises when it tells you to add the tree"
    )


def test_an_undeclared_tree_is_not_counted(tmp_path: Path) -> None:
    """The other direction, and the worse defect if it broke.

    A tree nothing reads must not appear in the count: that would be a reader
    told the run covered something it never opened.
    """
    project = _project(tmp_path, declare=False, extra_pages=5)

    assert _pages_reported(project) == 1, "the count includes a tree the run never read"
