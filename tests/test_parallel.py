# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the parallel scanner and idempotency guarantees.

Dev 4 mandate: running the scan 100 times in parallel must produce
bit-identical output every time.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pytest
from _helpers import make_mgr

from zenzic.core import regex as re
from zenzic.core.rules import AdaptiveRuleEngine, BaseRule, RuleFinding
from zenzic.core.scanner import scan_docs_references
from zenzic.models.config import ZenzicConfig
from zenzic.models.references import IntegrityReport


# Module-level BoomRule: pickleable (defined at module level) but raises
# during check().  Used to test that the engine isolates runtime exceptions.
class _BoomRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "BOOM"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        raise RuntimeError("intentional failure")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_docs(tmp_path: Path, n_files: int = 5) -> Path:
    """Create a docs tree with *n_files* Markdown files."""
    docs = tmp_path / "docs"
    docs.mkdir()
    for i in range(n_files):
        (docs / f"page_{i:03d}.md").write_text(
            f"# Page {i}\n\nThis is page {i}.\n\n[link][ref]\n\n[ref]: https://example.com\n"
        )
    return tmp_path


def _report_fingerprint(reports: list[IntegrityReport]) -> list[tuple[str, float, int]]:
    """Return a canonical fingerprint for a list of reports (path, score, n_findings)."""
    return sorted((str(r.file_path), round(r.score, 6), len(r.findings)) for r in reports)


# ─── Correctness ──────────────────────────────────────────────────────────────


def test_parallel_matches_sequential(tmp_path: Path) -> None:
    """Parallel scan produces the same reports as the sequential scan."""
    repo = _make_docs(tmp_path, n_files=10)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    sequential, _ = scan_docs_references(docs_root, mgr, config=config)
    parallel, _ = scan_docs_references(docs_root, mgr, config=config, workers=2)

    assert _report_fingerprint(sequential) == _report_fingerprint(parallel)


def test_parallel_empty_docs(tmp_path: Path) -> None:
    """Parallel scan on a repo with no docs returns empty results."""
    (tmp_path / "docs").mkdir()
    config = ZenzicConfig()
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    reports, _ = scan_docs_references(docs_root, mgr, config=config, workers=2)
    assert reports == []


def test_parallel_docs_not_exist(tmp_path: Path) -> None:
    """Parallel scan returns empty results when docs_dir does not exist."""
    config = ZenzicConfig()
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    reports, _ = scan_docs_references(docs_root, mgr, config=config, workers=2)
    assert reports == []


def test_parallel_single_worker_is_sequential(tmp_path: Path) -> None:
    """workers=1 disables parallelism but still returns correct results."""
    repo = _make_docs(tmp_path, n_files=4)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)
    result, _ = scan_docs_references(docs_root, mgr, config=config, workers=1)
    assert len(result) == 4
    # All refs should resolve (we defined [ref] in every file)
    for report in result:
        assert report.score == 100.0


def test_parsing_label_agrees_with_its_own_elapsed_column(tmp_path: Path) -> None:
    """The Parsing label must not report a window wider than its own progress row.

    Rich stamps ``finished_time`` on the final ``advance()`` — i.e. when the last
    file is parsed — and ``TimeElapsedColumn`` renders that. The label used to be
    written after the VSM/URP pass instead, so a single row showed two figures
    measuring different windows (observed on this repository: label 3405.8ms,
    column 0:00:02 from a real finished_time of 2047.6ms). The VSM pass now has
    its own line, so the label must agree with the column to within rounding.
    """
    from rich.progress import Progress

    repo = _make_docs(tmp_path, n_files=6)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    progress = Progress()
    scan_docs_references(docs_root, mgr, config=config, workers=1, progress_instance=progress)

    parsing = [t for t in progress.tasks if t.description.startswith("Parsing")]
    assert parsing, "no Parsing task was created"
    match = re.search(r"\(([\d.]+)ms\)", parsing[0].description)
    assert match, f"Parsing label carries no duration: {parsing[0].description!r}"
    label_ms = float(match.group(1))
    finished_time = parsing[0].finished_time
    assert finished_time is not None, "Parsing task never reached Rich's finished state"
    column_ms = finished_time * 1000

    # The label is stamped microseconds after the final advance(), so allow a
    # small delta — but nothing like the whole VSM pass, which is what this
    # regression guards against.
    assert abs(label_ms - column_ms) < 100, (
        f"Parsing label ({label_ms:.1f}ms) disagrees with its own elapsed column "
        f"({column_ms:.1f}ms) — the label is measuring past the end of parsing again"
    )


def test_vsm_pass_has_its_own_progress_line(tmp_path: Path) -> None:
    """The VSM/URP resolution pass must be visible as its own phase.

    Measured at ~1.4s on this repository's own docs tree — previously the single
    largest stretch of work with no progress line, silently folded into Parsing.
    """
    from rich.progress import Progress

    repo = _make_docs(tmp_path, n_files=4)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    progress = Progress()
    scan_docs_references(docs_root, mgr, config=config, workers=1, progress_instance=progress)

    vsm = [t for t in progress.tasks if t.description.startswith("Building VSM")]
    assert vsm, f"no VSM task: {[t.description for t in progress.tasks]!r}"
    assert "ms)" in vsm[0].description, f"VSM line reports no duration: {vsm[0].description!r}"


def test_sequential_validate_links_task_shows_elapsed_ms(tmp_path: Path) -> None:
    """The 'Validating links' progress task must report its own elapsed time on
    completion in the sequential path, matching every sibling task (parsing,
    orphans, snippets, unused assets) and matching the parallel path's own
    equivalent update at scanner.py:2091-2096. The sequential branch currently
    updates the task's description once at start (without a duration) and
    never again — the task never receives a finishing description with
    ``(X.Yms)``, unlike the identical parallel-path logic which does.
    """
    from rich.progress import Progress

    # No http(s) links in the fixture — n_urls stays 0, so the test exercises
    # the task's start/finish description bookkeeping without any real network
    # call (validate() with an empty registry does no I/O).
    repo = tmp_path
    docs = repo / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("# Page\n\nNo links here.\n")
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    progress = Progress()
    scan_docs_references(
        docs_root,
        mgr,
        config=config,
        validate_links=True,
        workers=1,  # forces the sequential path regardless of file count
        progress_instance=progress,
    )

    validate_tasks = [t for t in progress.tasks if t.description.startswith("Validating links")]
    assert validate_tasks, "no 'Validating links' task was created"
    assert "ms)" in validate_tasks[0].description, (
        "the 'Validating links' task's final description never shows its own "
        f"elapsed time, unlike every other progress line: {validate_tasks[0].description!r}"
    )


@pytest.mark.parametrize("workers", [0, -1, -8])
def test_parallel_invalid_workers_raise_clear_error(tmp_path: Path, workers: int) -> None:
    """workers must be None or >= 1 to avoid opaque executor errors."""
    repo = _make_docs(tmp_path, n_files=2)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    with pytest.raises(ValueError, match="workers must be None or an integer >= 1"):
        scan_docs_references(docs_root, mgr, config=config, workers=workers)


def test_parallel_sorted_output(tmp_path: Path) -> None:
    """Output is sorted by file_path regardless of worker scheduling order."""
    repo = _make_docs(tmp_path, n_files=8)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)
    result, _ = scan_docs_references(docs_root, mgr, config=config, workers=4)
    paths = [r.file_path for r in result]
    assert paths == sorted(paths)


# ─── Idempotency (Dev 4 mandate) ──────────────────────────────────────────────


@pytest.mark.slow
def test_idempotency_sequential_100_runs(tmp_path: Path) -> None:
    """Sequential scan: 100 identical runs produce bit-identical fingerprints."""
    repo = _make_docs(tmp_path, n_files=10)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    baseline = _report_fingerprint(scan_docs_references(docs_root, mgr, config=config)[0])
    for _ in range(99):
        result = _report_fingerprint(scan_docs_references(docs_root, mgr, config=config)[0])
        assert result == baseline, "Sequential scan is not deterministic"


def test_idempotency_parallel_10_runs(tmp_path: Path) -> None:
    """Parallel scan: 10 runs produce identical fingerprints (fast, not marked slow)."""
    repo = _make_docs(tmp_path, n_files=5)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    baseline = _report_fingerprint(
        scan_docs_references(docs_root, mgr, config=config, workers=2)[0]
    )
    for _ in range(9):
        result = _report_fingerprint(
            scan_docs_references(docs_root, mgr, config=config, workers=2)[0]
        )
        assert result == baseline, "Parallel scan is not deterministic"


def test_idempotency_concurrent_invocations(tmp_path: Path) -> None:
    """Launching multiple scans concurrently from threads produces identical results.

    Simulates the scenario where two CI jobs trigger Zenzic simultaneously
    on the same repo (read-only access, different processes).
    """
    repo = _make_docs(tmp_path, n_files=6)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)

    baseline = _report_fingerprint(scan_docs_references(docs_root, mgr, config=config)[0])

    def run_scan() -> list[tuple[str, float, int]]:
        return _report_fingerprint(scan_docs_references(docs_root, mgr, config=config)[0])

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_scan) for _ in range(8)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    for result in results:
        assert result == baseline, "Concurrent invocations produce different results"


# ─── Plugin exception isolation (Dev 4 mandate) ──────────────────────────────


def test_parallel_rule_exception_isolated(tmp_path: Path) -> None:
    """A module-level rule that raises at runtime does not abort other files."""
    from zenzic.core.scanner import _scan_single_file

    docs = tmp_path / "docs"
    docs.mkdir()
    files = [docs / f"p{i}.md" for i in range(3)]
    for f in files:
        f.write_text("# page\n")

    config = ZenzicConfig()
    engine = AdaptiveRuleEngine([_BoomRule()])

    # All files should produce a report with one Z901 finding
    for f in files:
        report, _ = _scan_single_file(f, config, engine)
        assert len(report.rule_findings) == 1
        assert report.rule_findings[0].rule_id == "Z901"
        assert report.rule_findings[0].is_error
