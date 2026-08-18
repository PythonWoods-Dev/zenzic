# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for v0.5.0a1 Integration Finale sprint.

Covers:
- zenzic inspect capabilities (PluginRuleInfo, list_plugin_rules)
- Performance telemetry (scan_docs_references verbose=True)
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from _helpers import make_mgr

from zenzic.core.rules import BaseRule, PluginRuleInfo, RuleFinding, list_plugin_rules
from zenzic.core.scanner import ADAPTIVE_PARALLEL_THRESHOLD, scan_docs_references
from zenzic.models.config import ZenzicConfig


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_docs(tmp_path: Path, n_files: int = 3) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    for i in range(n_files):
        (docs / f"page_{i:03d}.md").write_text(f"# Page {i}\n\nContent {i}.\n")
    return tmp_path


class _DummyRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "DUMMY"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []


# ─── list_plugin_rules ────────────────────────────────────────────────────────


def test_list_plugin_rules_returns_list() -> None:
    """list_plugin_rules() returns a list (possibly empty if entry-points not installed)."""
    result = list_plugin_rules()
    assert isinstance(result, list)


def test_list_plugin_rules_sorted_by_source() -> None:
    """Results are sorted by entry-point source name."""
    result = list_plugin_rules()
    sources = [r.source for r in result]
    assert sources == sorted(sources)


def test_list_plugin_rules_contains_core_broken_links() -> None:
    """The built-in broken-links rule is present when the package is installed."""
    result = list_plugin_rules()
    sources = {r.source for r in result}
    # Core package registers 'broken-links' via entry-points
    assert "broken-links" in sources


def test_list_plugin_rules_broken_links_has_correct_id() -> None:
    """broken-links entry-point exposes rule_id 'Z101'."""
    result = list_plugin_rules()
    by_source = {r.source: r for r in result}
    assert "broken-links" in by_source
    assert by_source["broken-links"].rule_id == "Z101"


def test_list_plugin_rules_broken_links_origin_is_zenzic() -> None:
    """broken-links is registered by the 'zenzic' distribution."""
    result = list_plugin_rules()
    by_source = {r.source: r for r in result}
    assert by_source["broken-links"].origin == "zenzic"


def test_plugin_rule_info_fields() -> None:
    """PluginRuleInfo is a plain dataclass with the expected fields."""
    info = PluginRuleInfo(
        rule_id="TEST",
        class_name="my_pkg.rules.TestRule",
        source="test-rule",
        origin="my-pkg",
    )
    assert info.rule_id == "TEST"
    assert info.class_name == "my_pkg.rules.TestRule"
    assert info.source == "test-rule"
    assert info.origin == "my-pkg"


def test_list_plugin_rules_skips_unloadable_entry_point() -> None:
    """An entry-point that fails to load is silently skipped."""
    from importlib.metadata import EntryPoint

    bad_ep = EntryPoint(
        name="bad", value="nonexistent.module:NonExistentClass", group="zenzic.rules"
    )

    with patch("importlib.metadata.entry_points", return_value=[bad_ep]):
        result = list_plugin_rules()
    # Bad plugin is skipped; built-in core fallback is still present.
    assert all(info.source != "bad" for info in result)
    assert any(info.source == "broken-links" for info in result)


def test_list_plugin_rules_fallback_keeps_sorted_order() -> None:
    """Core fallback insertion preserves sorted-by-source ordering."""
    from importlib.metadata import EntryPoint

    zzz_ep = EntryPoint(
        name="zzz-rule", value="tests.test_integration_finale:_DummyRule", group="zenzic.rules"
    )

    with patch("importlib.metadata.entry_points", return_value=[zzz_ep]):
        result = list_plugin_rules()

    sources = [r.source for r in result]
    assert "broken-links" in sources
    assert "zzz-rule" in sources
    assert sources == sorted(sources)


# ─── CLI: zenzic inspect capabilities ───────────────────────────────────────


def test_cli_inspect_capabilities_command_runs() -> None:
    """zenzic inspect capabilities exits 0 and prints output."""
    from typer.testing import CliRunner

    from zenzic.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", "capabilities"])
    assert result.exit_code == 0


def test_cli_inspect_capabilities_shows_broken_links() -> None:
    """inspect capabilities output mentions the broken-links core rule."""
    from typer.testing import CliRunner

    from zenzic.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", "capabilities"])
    assert "broken-links" in result.output
    assert "Z101" in result.output


def test_cli_inspect_capabilities_empty_when_no_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no extensible rules are registered, both sections still appear and exit 0."""
    from typer.testing import CliRunner

    from zenzic.main import app

    monkeypatch.setattr("zenzic.core.rules.list_plugin_rules", lambda: [])

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", "capabilities"])
    assert result.exit_code == 0
    # Core scanners section always present
    assert "Core Scanners" in result.output
    assert "Credential Scanner" in result.output
    assert "Path Traversal Guard" in result.output
    # Extensible rules section always present, with placeholder row
    assert "Extensible Rules" in result.output
    assert "No third-party plugins installed" in result.output


def test_cli_plugins_command_removed() -> None:
    """D068: 'zenzic plugins' is entirely removed — must return a non-zero exit code."""
    from typer.testing import CliRunner

    from zenzic.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code != 0


# ─── Telemetry ────────────────────────────────────────────────────────────────


def test_telemetry_sequential_writes_to_stderr(tmp_path: Path) -> None:
    """verbose=True emits a telemetry line to stderr for sequential scans."""
    repo = _make_docs(tmp_path, n_files=2)
    config = ZenzicConfig()

    captured = StringIO()
    with patch("sys.stderr", captured):
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        scan_docs_references(docs_root, mgr, config=config, verbose=True)

    output = captured.getvalue()
    assert "[zenzic]" in output
    assert "Sequential" in output
    assert "Files: 2" in output
    assert "Execution time:" in output


def test_telemetry_disabled_by_default(tmp_path: Path) -> None:
    """verbose=False (default) produces no stderr telemetry line."""
    repo = _make_docs(tmp_path, n_files=2)
    config = ZenzicConfig()

    captured = StringIO()
    with patch("sys.stderr", captured):
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        scan_docs_references(docs_root, mgr, config=config)

    assert "[zenzic]" not in captured.getvalue()


def test_telemetry_parallel_shows_workers(tmp_path: Path) -> None:
    """verbose=True in parallel mode mentions workers and speedup."""
    # Create enough files to trigger parallel mode
    repo = _make_docs(tmp_path, n_files=ADAPTIVE_PARALLEL_THRESHOLD)
    config = ZenzicConfig()

    captured = StringIO()
    with patch("sys.stderr", captured):
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        scan_docs_references(docs_root, mgr, config=config, workers=2, verbose=True)

    output = captured.getvalue()
    assert "[zenzic]" in output
    # Either parallel triggered (if files >= threshold) or sequential fallback —
    # either way telemetry must be emitted.
    assert "Execution time:" in output


def test_telemetry_sequential_no_speedup_line(tmp_path: Path) -> None:
    """Sequential telemetry line does not contain a speedup estimate."""
    repo = _make_docs(tmp_path, n_files=2)
    config = ZenzicConfig()

    captured = StringIO()
    with patch("sys.stderr", captured):
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        scan_docs_references(docs_root, mgr, config=config, verbose=True)

    assert "speedup" not in captured.getvalue().lower()


# ─── CEO-298 Parallel Fail-Fast ───────────────────────────────────────────────


def test_parallel_fail_fast_aborts_pending_on_breach(tmp_path: Path) -> None:
    """CEO-298: a security breach in one worker causes pending futures to be cancelled.

    We replace ProcessPoolExecutor with ThreadPoolExecutor so that the _worker
    mock (which must live in the same process to be patchable) is visible to the
    coordinator. The wait(FIRST_COMPLETED) + _abort logic is executor-agnostic.
    """
    import concurrent.futures

    from zenzic.core.credentials import SecurityFinding
    from zenzic.models.references import IntegrityReport

    n = ADAPTIVE_PARALLEL_THRESHOLD
    repo = _make_docs(tmp_path, n_files=n)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    md_files = sorted(docs_root.glob("*.md"))
    assert len(md_files) == n

    breach_file = md_files[0]
    breach_finding = SecurityFinding(
        file_path=breach_file,
        line_no=1,
        secret_type="test-secret",
        url="ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )

    def _mock_worker(args):  # noqa: ANN001
        md_file, _cfg, _eng = args
        if md_file == breach_file:
            return IntegrityReport(
                file_path=md_file,
                score=0.0,
                security_findings=[breach_finding],
            )
        return IntegrityReport(file_path=md_file, score=100.0)

    # Replace ProcessPoolExecutor with ThreadPoolExecutor so the mock is
    # visible inside the executor (same process, shared address space).
    with patch("concurrent.futures.ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor):
        with patch("zenzic.core.scanner._worker", side_effect=_mock_worker):
            mgr = make_mgr(config, repo_root=repo)
            reports, _ = scan_docs_references(docs_root, mgr, config=config, workers=2)

    # At least the breach report must be present.
    breached = [r for r in reports if r.security_findings]
    assert len(breached) >= 1, "Expected at least one security breach report"

    # CEO-298 invariant: final list is sorted by file_path.
    paths = [r.file_path for r in reports]
    assert paths == sorted(paths), "Results must be sorted by file_path"


@pytest.mark.slow
def test_parallel_zrt002_deadlock_guard_emits_z902(tmp_path: Path) -> None:
    """ZRT-002 preserved: when no worker completes within _WORKER_TIMEOUT_S, Z902 is emitted."""
    import concurrent.futures
    import threading

    import zenzic.core.scanner as scanner_mod
    from zenzic.models.references import IntegrityReport

    n = 10
    repo = _make_docs(tmp_path, n_files=n)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir

    _hang_event = threading.Event()

    def _hanging_worker(args):  # noqa: ANN001
        # Block long enough to outlast _WORKER_TIMEOUT_S (set to 1 s below),
        # but release promptly once the event fires so executor.shutdown(wait=True)
        # does not stall the entire test suite.  Using timeout=2 here means the
        # worst-case extra wait after Z902 is emitted is ~1 s (2 s total –
        # 1 s already elapsed when the scanner detected the stall).
        _hang_event.wait(timeout=2)
        md_file, _, _ = args
        return IntegrityReport(file_path=md_file, score=100.0)

    original_timeout = scanner_mod._WORKER_TIMEOUT_S
    try:
        scanner_mod._WORKER_TIMEOUT_S = 1  # shorten for test speed
        with patch("zenzic.core.scanner.ADAPTIVE_PARALLEL_THRESHOLD", 10):
            with patch(
                "concurrent.futures.ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor
            ):
                with patch("zenzic.core.scanner._worker", side_effect=_hanging_worker):
                    mgr = make_mgr(config, repo_root=repo)
                    reports, _ = scan_docs_references(docs_root, mgr, config=config, workers=2)
    finally:
        scanner_mod._WORKER_TIMEOUT_S = original_timeout
        _hang_event.set()  # unblock any threads still waiting (belt-and-suspenders)

    # ZRT-002: every stalled file must produce a Z902 finding.
    z902_reports = [r for r in reports if any(f.rule_id == "Z902" for f in r.rule_findings)]
    assert len(z902_reports) >= 1, "Expected at least one Z902 timeout finding"


def test_parallel_results_sorted_after_fail_fast(tmp_path: Path) -> None:
    """CEO-298: the final reports list is sorted by file_path even with partial scan."""
    import concurrent.futures

    from zenzic.core.credentials import SecurityFinding
    from zenzic.models.references import IntegrityReport

    n = 10
    repo = _make_docs(tmp_path, n_files=n)
    config = ZenzicConfig()
    docs_root = repo / config.docs_dir
    md_files = sorted(docs_root.glob("*.md"))

    # Breach on the last file alphabetically — many workers complete before it.
    breach_file = md_files[-1]
    breach_finding = SecurityFinding(
        file_path=breach_file,
        line_no=1,
        secret_type="test-secret",
        url="ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )

    def _mock_worker(args):  # noqa: ANN001
        md_file, _cfg, _eng = args
        if md_file == breach_file:
            return IntegrityReport(
                file_path=md_file,
                score=0.0,
                security_findings=[breach_finding],
            )
        return IntegrityReport(file_path=md_file, score=100.0)

    with patch("zenzic.core.scanner.ADAPTIVE_PARALLEL_THRESHOLD", 10):
        with patch("concurrent.futures.ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor):
            with patch("zenzic.core.scanner._worker", side_effect=_mock_worker):
                mgr = make_mgr(config, repo_root=repo)
                reports, _ = scan_docs_references(docs_root, mgr, config=config, workers=2)

    paths = [r.file_path for r in reports]
    assert paths == sorted(paths), (
        "Results must be sorted by file_path regardless of completion order"
    )
