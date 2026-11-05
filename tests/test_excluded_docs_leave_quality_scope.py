# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A page MkDocs never builds is not analysed, but is still scanned for secrets.

``exclude_docs`` removes a file from the site entirely (``InclusionLevel.EXCLUDED``
in MkDocs' ``structure/files.py``); ``draft_docs`` removes it from ``mkdocs build``
while ``mkdocs serve`` still renders it (``InclusionLevel.DRAFT``, selected by
``build.py``'s ``inclusion = is_in_serve if serve_url else is_included``).

Zenzic analyses a repository, not a running command, so it cannot know which of
the two will be invoked and adopts **build** semantics: a draft page is not in
the published site.

The security boundary is the same one ``site_dir`` already draws. A quality
finding on a page no reader can reach is a false positive; a credential in that
same file is still a credential in the repository, so ``security_view`` strips
this exclusion exactly as it strips the declared output directory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ZENZIC = Path(sys.executable).parent / "zenzic"


def _project(root: Path, key: str) -> Path:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
    (root / "docs" / "hidden.md").write_text(
        "# Hidden\n\nAWS key: AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8"
    )
    (root / "mkdocs.yml").write_text(
        f"site_name: T\n{key}: |\n  hidden.md\nnav:\n  - Home: index.md\n", encoding="utf-8"
    )
    (root / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    return root


def _codes_on(root: Path, rel: str) -> set[str]:
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "all", ".", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    start = proc.stdout.find("{")
    assert start >= 0, proc.stdout[:300]
    payload = json.loads(proc.stdout[start:])
    return {f["code"] for f in payload.get("findings", []) if rel in f.get("rel_path", "")}


@pytest.mark.parametrize("key", ["exclude_docs", "draft_docs"])
def test_quality_findings_disappear(tmp_path: Path, key: str) -> None:
    codes = _codes_on(_project(tmp_path / key, key), "hidden.md")
    assert "Z402" not in codes, f"{key}: orphan-page finding on a page the build omits"
    assert "Z410" not in codes, f"{key}: dead-end finding on a page the build omits"


@pytest.mark.parametrize("key", ["exclude_docs", "draft_docs"])
def test_the_credential_is_still_found(tmp_path: Path, key: str) -> None:
    """Positive control: user scoping never silences the security tier."""
    codes = _codes_on(_project(tmp_path / f"{key}-sec", key), "hidden.md")
    assert "Z201" in codes, f"{key}: a credential in an unbuilt file must still be reported"


def test_an_undeclared_page_still_reports(tmp_path: Path) -> None:
    """Positive control: the exclusion must not swallow ordinary orphans."""
    root = tmp_path / "control"
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
    (root / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    (root / "mkdocs.yml").write_text("site_name: T\nnav:\n  - Home: index.md\n", encoding="utf-8")
    (root / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    assert "Z402" in _codes_on(root, "orphan.md")
