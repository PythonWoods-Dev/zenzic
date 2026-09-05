# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic check all <file>``'s DQS score must not silently mix scopes.

Regression for: when a single-file target was requested, Z-code finding
penalties were correctly scoped to that file (`_findings_counts` is built
from `all_findings` *after* the `_single_file` filter), but the suppression/
technical-debt penalty was NOT — `collect_inline_suppression_stats` was
always called with the full, project-wide `docs_root`, so a file with zero
suppressions of its own could still show a non-zero technical-debt penalty
inherited from unrelated suppressions elsewhere in the project. This is an
undocumented hybrid scope, not a deliberate design choice — confirmed via a
controlled sandbox: full-project scan, the same broken file alone, and a
clean file in the same project alone all produced three different DQS
scores, proving Z-code penalties were already file-scoped while chasing down
whether the suppression penalty was too (it wasn't, until this fix).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def _make_sandbox(tmp_path: Path, files: dict[str, str]) -> Path:
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


_SUPPRESSED_PAGE = """\
    # Page With a Suppression

    This page carries an inline suppression directive on a forbidden-brand
    mention, giving the project real technical debt that a single-file scan
    of an unrelated page should never inherit or be penalized for.

    Legacy brand mention. <!-- zenzic:ignore: Z601 - historical reference -->
"""

_CLEAN_UNRELATED_PAGE = """\
    # Unrelated Clean Page

    This page has no suppressions of its own and no findings of its own —
    it exists purely to prove that scanning it in isolation must not
    inherit debt penalties that belong to a different file in the project.
"""


@pytest.fixture
def suppression_sandbox(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = _make_sandbox(
        tmp_path,
        {
            "docs/suppressed.md": _SUPPRESSED_PAGE,
            "docs/clean.md": _CLEAN_UNRELATED_PAGE,
        },
    )
    return root, root / "docs" / "suppressed.md", root / "docs" / "clean.md"


def test_single_file_score_excludes_unrelated_file_suppressions(
    suppression_sandbox: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanning clean.md alone must not carry suppressed.md's debt penalty."""
    root, _suppressed, _clean = suppression_sandbox
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check", "all", "docs/clean.md", "--format", "json"])

    payload = json.loads(result.stdout)
    assert payload["suppression_count"] == 0, (
        f"clean.md carries no suppressions of its own; suppression_count must "
        f"be 0 for this single-file scan, got {payload['suppression_count']} "
        f"(leaked from suppressed.md elsewhere in the project). Full payload: "
        f"{payload}"
    )


def test_single_file_score_counts_own_suppression(
    suppression_sandbox: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanning suppressed.md alone must count its own suppression (not zero)."""
    root, _suppressed, _clean = suppression_sandbox
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check", "all", "docs/suppressed.md", "--format", "json"])

    payload = json.loads(result.stdout)
    assert payload["suppression_count"] == 1, (
        f"suppressed.md carries exactly one inline suppression of its own; "
        f"single-file suppression_count must reflect it, got "
        f"{payload['suppression_count']}. Full payload: {payload}"
    )


def test_full_project_scan_still_counts_all_suppressions(
    suppression_sandbox: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: the full-project scan (no target) must be unaffected —
    it must still count every suppression across the whole project."""
    root, _suppressed, _clean = suppression_sandbox
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check", "all", "--format", "json"])

    payload = json.loads(result.stdout)
    assert payload["suppression_count"] == 1, (
        f"Full-project scan must still count suppressed.md's one suppression, "
        f"got {payload['suppression_count']}. Full payload: {payload}"
    )
