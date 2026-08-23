# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic check all <file>`` must not run the full rule engine on every
file in the project.

Regression for: `check all <file>` correctly scopes its *displayed* findings
and DQS score to the target file (see `test_single_file_dqs_scope.py`), but
the underlying scan cost was never scoped — `scan_docs_references()` (called
unconditionally with the full `docs_root`) runs `rule_engine.run_with_tracker`
against *every* markdown file in the project regardless of which single file
was requested, then discards all but the target's findings after the fact.
Confirmed via direct CLI timing: a full-project scan (267 docs) and a
single-file scan of one of those same files took the same ~4.4s wall time,
proving no scoping occurred. This test proves it structurally (rule-engine
call count), which is deterministic and CI-safe, rather than relying on wall
clock alone.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zenzic.core.rules import AdaptiveRuleEngine
from zenzic.main import app


runner = CliRunner()


def _make_sandbox(tmp_path: Path, num_pages: int) -> Path:
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    for i in range(num_pages):
        (docs / f"page{i}.md").write_text(
            textwrap.dedent(f"""\
                # Page {i}

                This is genuine standalone content for page {i}, long enough
                to clear the minimum word count threshold on its own and
                free of any dependency on the other pages in this sandbox.
                It links to [the next page](./page{(i + 1) % num_pages}.md)
                to avoid tripping any dead-end/orphan topology findings.
            """),
            encoding="utf-8",
        )
    return tmp_path


@pytest.fixture
def many_page_sandbox(tmp_path: Path) -> Path:
    return _make_sandbox(tmp_path, num_pages=20)


def test_single_file_scan_does_not_run_rule_engine_on_unrelated_files(
    many_page_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanning page0.md alone must not execute the rule engine on page1..19."""
    monkeypatch.chdir(many_page_sandbox)

    seen_paths: list[Path] = []
    original = AdaptiveRuleEngine.run_with_tracker

    def _spy(self: AdaptiveRuleEngine, file_path: Path, text: str, tracker: object) -> object:
        seen_paths.append(Path(file_path))
        return original(self, file_path, text, tracker)  # type: ignore[arg-type]

    with patch.object(AdaptiveRuleEngine, "run_with_tracker", _spy):
        result = runner.invoke(app, ["check", "all", "docs/page0.md", "--format", "json"])

    assert result.exit_code in (0, 1), (
        f"Unexpected exit code {result.exit_code} scanning a single clean page. "
        f"Output: {result.stdout}"
    )
    unrelated = [p for p in seen_paths if p.name != "page0.md"]
    assert not unrelated, (
        f"check all docs/page0.md ran the full rule engine on {len(unrelated)} "
        f"unrelated file(s) out of {len(seen_paths)} total invocations: "
        f"{sorted(p.name for p in unrelated)}. A single-file scan must not pay "
        f"the full content-analysis cost of the whole project."
    )


_SHORT_TARGET_PAGE = """\
    # Too Short

    Only a few words here.
"""

_CLEAN_LONG_PAGE = """\
    # A Normal Page

    This page carries genuine, sufficiently long prose content so that it
    clears the minimum word count threshold on its own and does not trip
    any short-content finding when scanned, unlike its sibling page.
"""


@pytest.fixture
def z502_target_sandbox(tmp_path: Path) -> tuple[Path, Path]:
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "short.md").write_text(textwrap.dedent(_SHORT_TARGET_PAGE), encoding="utf-8")
    (docs / "clean.md").write_text(textwrap.dedent(_CLEAN_LONG_PAGE), encoding="utf-8")
    return tmp_path, docs / "short.md"


def test_single_file_scan_still_detects_target_rule_engine_finding(
    z502_target_sandbox: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skipping the rule pass on OTHER files must not skip it on the target
    itself — a rule-engine-only finding (Z502, short content) on the target
    file must still be reported when scoping to that file alone.

    This guards against the exact silent-disable failure mode this fix could
    introduce if the path-equality check used to route the target through
    the rule engine ever silently stops matching (e.g. a normalization
    mismatch between the resolved target path and the paths yielded by the
    file walker) — the symptom would be a falsely clean/perfect score with
    no crash and no test failure elsewhere, the same class of defect as the
    z510-z517 fixture isolation gap found earlier this session.
    """
    root, short_file = z502_target_sandbox
    monkeypatch.chdir(root)

    # NOTE: --format json is deliberately NOT used here. The legacy JSON
    # payload's `references` field is always empty regardless of scoping or
    # findings present — confirmed pre-existing via a direct git-stash/re-run
    # comparison (identical `references: []` before and after this session's
    # fix, both single-file and full-project) and now tracked as its own
    # release-blocking item: V031_CHECK_ALL_JSON_LEGACY_REFERENCES_EMPTY
    # (.claude/state/03-priority-table.md). Text output is the channel
    # confirmed correct here, so it's the correctness oracle for this test.
    result = runner.invoke(app, ["check", "all", "docs/short.md"])

    assert "Z502" in result.stdout, (
        f"docs/short.md is genuinely short and must still trigger Z502 when "
        f"scanned as a single-file target — got no Z502 in output, which "
        f"would mean the rule engine silently never ran on the target file "
        f"either. Full stdout: {result.stdout}"
    )


@pytest.fixture
def z502_target_outside_docs_root_sandbox(tmp_path: Path) -> Path:
    """Same as z502_target_sandbox, but the target lives OUTSIDE docs_dir —
    e.g. a repo-root file like CHANGELOG.md/README.md — the case most at
    risk of a path-normalization mismatch, since the target's relationship
    to docs_root/repo_root differs from an in-tree file."""
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "clean.md").write_text(textwrap.dedent(_CLEAN_LONG_PAGE), encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(textwrap.dedent(_SHORT_TARGET_PAGE), encoding="utf-8")
    return tmp_path


def test_single_file_scan_detects_rule_finding_for_target_outside_docs_root(
    z502_target_outside_docs_root_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target outside docs_dir (e.g. CHANGELOG.md) must still run the rule
    engine on itself and report its own Z502, not silently skip it.

    This is the confirmed regression test for
    V031_SINGLE_FILE_OUTSIDE_DOCS_ROOT_NEVER_RULE_SCANNED
    (.claude/state/03-priority-table.md): `_apply_target()` correctly keeps
    `docs_root` pinned to the full configured tree for VSM/topology
    correctness, but no code path injects an out-of-tree target into
    `scan_docs_references()`'s file enumeration — so the rule engine never
    runs on the target at all, silently reporting a perfect score. Confirmed
    pre-existing via git-stash/re-run (identical zero-findings/100-score
    result before and after this session's performance fix), and confirmed
    NOT caused by docs_root resolution itself — the resolved docs_root is
    structurally identical (`<repo_root>/docs`) in both the real repo's
    mkdocs auto-discovery and this synthetic sandbox's explicit
    `engine = "standalone"` config, printed and compared directly.
    """
    root = z502_target_outside_docs_root_sandbox
    monkeypatch.chdir(root)

    # See NOTE in test_single_file_scan_still_detects_target_rule_engine_finding
    # above: the legacy JSON payload's `references` field is a separate,
    # pre-existing gap (V031_CHECK_ALL_JSON_LEGACY_REFERENCES_EMPTY) — text
    # output is the confirmed-correct oracle here.
    result = runner.invoke(app, ["check", "all", "CHANGELOG.md"])

    assert "Z502" in result.stdout, (
        f"CHANGELOG.md (outside docs_dir) is genuinely short and must still "
        f"trigger Z502 when scanned as a single-file target — got no Z502 "
        f"in output, indicating the rule-engine target match silently failed "
        f"for a target outside docs_root. Full stdout: {result.stdout}"
    )
