# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Cross-path parity between the CLI's ``check_all`` pipeline and
``IncrementalAnalysisEngine`` (the LSP-shared, single-file analysis primitive
also used directly by ``zenzic-mcp``'s ``check_document``).

The two paths do not share a common orchestration primitive (tracked as an
architectural question in ``.claude/state/03-priority-table.md``,
``V031_CLI_LSP_CHECK_LOGIC_DUPLICATION``) — this is the cheap near-term guard
that finding's own recommendation proposed: a fixture-based parity test so a
future change wired into one path but not the other fails loudly here,
instead of silently desynchronizing CLI, LSP, and MCP results. It codifies a
comparison already done manually once (three fixtures, all matched) as a
permanent regression test rather than a one-off finding.

This is not a substitute for the longer-term recommendation (extracting a
shared orchestration primitive both paths converge on) — see that row for
the architectural disposition, which remains open pending Tech Lead sign-off.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.core.adapters import get_adapter
from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.scanner import _build_rule_engine
from zenzic.main import app
from zenzic.models.config import ZenzicConfig
from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap


runner = CliRunner()

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples"

#: CLI topology detection is nav-membership-based (Z402/Z403); LSP topology
#: detection is VSM-graph-reachability-based (Z410/Z411/Z412) — a known,
#: already-tracked divergence (03-priority-table.md,
#: V031_CLI_LSP_CHECK_LOGIC_DUPLICATION), not a new bug this test should
#: fail on. Live-verified while building this suite that Z106 (CIRCULAR_LINK)
#: belongs to the same divergent family: a 2-page mutual-reference fixture
#: produces Z106 on the CLI path but Z411 on the LSP path for the identical
#: graph shape — logged as a newly-identified member of the family, not
#: previously named explicitly in the tracked row. Excluded from parity
#: comparison; unifying topology detection is the row's own longer-term
#: architectural recommendation, not something this guard should mask or
#: silently paper over by pretending these codes already agree.
_TOPOLOGY_FAMILY_CODES = frozenset({"Z106", "Z402", "Z403", "Z410", "Z411", "Z412"})


def _cli_sarif_rule_ids(repo_root: Path) -> list[str]:
    """Run the real `zenzic check all --format sarif` CLI path and return ruleIds."""
    import json

    result = runner.invoke(app, ["check", "all", "--format", "sarif"])
    assert result.exit_code in (0, 1, 2, 3), (
        f"Unexpected crash (exit {result.exit_code}) scanning {repo_root}:\n{result.output}"
    )
    sarif = json.loads(result.stdout)
    return sorted(
        r["ruleId"]
        for r in sarif["runs"][0]["results"]
        if r["ruleId"] not in _TOPOLOGY_FAMILY_CODES
    )


def _lsp_engine_rule_ids(repo_root: Path, docs_root: Path) -> list[str]:
    """Run the IncrementalAnalysisEngine path (LSP/zenzic-mcp's shared primitive) directly."""
    config, _ = ZenzicConfig.load(repo_root)
    rule_engine = _build_rule_engine(config)
    assert rule_engine is not None
    adapter = get_adapter(config.build_context, docs_root, repo_root)
    vsm = VirtualSiteMap()
    overlay = VirtualBufferOverlay(vsm)
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=rule_engine,
        adapter=adapter,
        docs_root=docs_root,
        repo_root=repo_root,
    )
    results = engine.process_changes(vsm, overlay)
    all_diags = [d for diags in results.values() for d in diags]
    return sorted(d.code for d in all_diags if d.code not in _TOPOLOGY_FAMILY_CODES)


def _assert_parity(repo_root: Path, docs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(repo_root)
    cli_codes = _cli_sarif_rule_ids(repo_root)
    lsp_codes = _lsp_engine_rule_ids(repo_root, docs_root)
    assert cli_codes == lsp_codes, (
        f"CLI (check_all) and LSP (IncrementalAnalysisEngine) diverged for {repo_root}:\n"
        f"  CLI: {cli_codes}\n  LSP: {lsp_codes}"
    )


def test_parity_clean_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean file with no findings must agree on both paths (0 findings, 0 findings)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    body = " ".join(["word"] * 55)
    (docs / "index.md").write_text(f"# Home\n\n[Other](other.md). {body}\n", encoding="utf-8")
    (docs / "other.md").write_text(f"# Other\n\n[Home](index.md). {body}\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").touch()

    _assert_parity(tmp_path, docs, monkeypatch)


def test_parity_content_defect_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """examples/z521-required-table-column: a real content-policy violation fixture."""
    repo_root = _EXAMPLES_ROOT / "z521-required-table-column"
    _assert_parity(repo_root, repo_root / "docs", monkeypatch)


def test_parity_security_breach_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """examples/z201-credentials: a real leaked-credential fixture (Z201, Exit 2)."""
    repo_root = _EXAMPLES_ROOT / "z201-credentials"
    _assert_parity(repo_root, repo_root / "docs", monkeypatch)
