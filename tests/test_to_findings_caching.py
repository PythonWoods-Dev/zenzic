# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``_to_findings`` must not re-read the same file's content more than once.

Regression for: `_to_findings` independently calls `.read_text()` for
`snippet_errors` (to recover `source_line`) and again for each
`reference_reports` entry (same purpose) — if the same file appears in both
result categories (a realistic case: a page can have both a snippet error
and a reference-integrity finding), its content was read from disk twice
within a single `_to_findings` call. This is the narrow, safely-scoped part
of the CLI/LSP Step-4-caching finding that's reachable without touching
`scanner.py`/`validator.py`/`models/references.py` (those functions don't
expose raw file content on their result objects, so deduplicating reads
*across* the seven sub-checks in `_collect_all_results` is out of this
fix's scope — only the redundant re-read *inside* `_to_findings` itself is
addressed here).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from zenzic.cli._check import _AllCheckResults, _to_findings
from zenzic.core.validator import SnippetError
from zenzic.models.config import ZenzicConfig
from zenzic.models.references import IntegrityReport, ReferenceFinding


def _empty_results(**overrides: object) -> _AllCheckResults:
    base: dict[str, object] = {
        "link_errors": [],
        "orphans": [],
        "snippet_errors": [],
        "unused_assets": [],
        "nav_contract_errors": [],
        "reference_reports": [],
        "security_events": 0,
        "directory_index_issues": [],
    }
    base.update(overrides)
    return _AllCheckResults(**base)  # type: ignore[arg-type]


def test_to_findings_reads_shared_file_content_only_once(tmp_path: Path) -> None:
    """A file appearing in both snippet_errors and reference_reports must
    only be read from disk once within a single _to_findings call."""
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    shared_file = docs_root / "index.md"
    shared_file.write_text("# Home\n\nSome line.\n[dangling][missing]\n", encoding="utf-8")

    results = _empty_results(
        snippet_errors=[
            SnippetError(file_path=shared_file, line_no=2, message="untagged code block"),
        ],
        reference_reports=[
            IntegrityReport(
                file_path=shared_file,
                score=90.0,
                findings=[
                    ReferenceFinding(
                        file_path=shared_file,
                        line_no=4,
                        issue="Z301",
                        detail="Reference 'missing' is undefined.",
                        is_warning=True,  # Z301 is "warning" per codes.py's CODE_DEFINITIONS
                    )
                ],
            )
        ],
    )

    real_read_text = Path.read_text
    call_count = 0

    def _counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        nonlocal call_count
        if self == shared_file:
            call_count += 1
        return real_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", _counting_read_text):
        findings = _to_findings(results, docs_root, tmp_path, ZenzicConfig())

    assert call_count <= 1, (
        f"Expected shared_file to be read from disk at most once within "
        f"_to_findings, got {call_count} reads."
    )
    codes = {f.code for f in findings}
    assert "Z503" in codes
    assert "Z301" in codes
