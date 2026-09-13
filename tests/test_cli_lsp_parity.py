# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Cross-path parity between the CLI's ``check_all`` pipeline and
``IncrementalAnalysisEngine`` (the LSP-shared, single-file analysis primitive
also used directly by ``zenzic-mcp``'s ``check_document``).

The two paths do not share a common orchestration primitive (tracked
internally as an open architectural question) — this is the cheap near-term
guard that finding's own recommendation proposed: a fixture-based parity test so a
future change wired into one path but not the other fails loudly here,
instead of silently desynchronizing CLI, LSP, and MCP results. It codifies a
comparison already done manually once (three fixtures, all matched) as a
permanent regression test rather than a one-off finding.

This is not a substitute for the longer-term recommendation (extracting a
shared orchestration primitive both paths converge on) — see that row for
the architectural disposition, which remains open pending internal sign-off.
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
from zenzic.models.vsm import VirtualBufferOverlay, build_vsm


runner = CliRunner()

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples"

#: CLI topology detection is nav-membership-based (Z402/Z403); LSP topology
#: detection is VSM-graph-reachability-based (Z410/Z411/Z412) — a known,
#: already-tracked divergence, not a new bug this test should
#: fail on. Live-verified while building this suite that Z106 (CIRCULAR_LINK)
#: belongs to the same divergent family: a 2-page mutual-reference fixture
#: produces Z106 on the CLI path but Z411 on the LSP path for the identical
#: graph shape — logged as a newly-identified member of the family, not
#: previously named explicitly in the tracked row. Excluded from parity
#: comparison; unifying topology detection is the row's own longer-term
#: architectural recommendation, not something this guard should mask or
#: silently paper over by pretending these codes already agree.
#:
#: Re-measured 2026-09-13, because the exclusion had never been checked against
#: what it actually hides. Two separate things were behind it:
#:
#: 1. **An artifact of this harness.** It built a bare ``VirtualSiteMap()``,
#:    which has no routes and no entry points, so topology detection saw every
#:    page as unreachable or dead-ended -- **157 Z410/Z411 on this repository's
#:    own corpus that the language server never emits** (server.py:288 builds
#:    the VSM properly; with a built VSM the same run yields **0**). Fixed here:
#:    the harness now builds the VSM the way the server does. Driving the LSP
#:    along a path no server takes is part of why three divergences got through.
#:
#: 2. **One real, user-visible divergence, which this exclusion does hide.**
#:    With a correctly built VSM the remaining difference is ``Z106``: the CLI
#:    reports a circular link, the editor reports nothing, because cycle
#:    detection runs only in ``scanner.py``'s ``_find_cycles_iterative`` and the
#:    incremental engine has no equivalent pass.
#:
#:    **This is a missing capability on one side, not two implementations
#:    disagreeing** -- the distinction matters to whoever acts on it. The editor
#:    does not detect cycles at all; it does not compute a different answer. No
#:    user of *this* repository meets it either way: ``.zenzic.toml`` exempts
#:    ``Z106`` for ``docs/**``, so the CLI reports none here (it would otherwise
#:    find 72 nodes in cycles). A user whose own docs contain a cycle and who
#:    has not exempted the code sees it in CI and not in the editor.
#:
#:    Costed 2026-09-13, and the algorithm is not the expense: the DFS runs in
#:    **0.47 ms median** over this corpus, and the VSM already maintains an
#:    adjacency map (``outgoing_links``), so no new structure is needed. The
#:    work is that **the two graphs are not the same graph** -- the CLI's is
#:    keyed by ``Path`` with Ghost Routes and non-source targets excluded
#:    (300 nodes, 668 edges), the VSM's is keyed by canonical URL (300 nodes,
#:    **794** edges). Running the existing DFS over the VSM graph would produce
#:    different cycles and create a divergence rather than close one. Deferred
#:    to v0.31.1 for that reason, not for the cost.
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
    # Build the VSM the way the language server does (server.py:288). A bare
    # `VirtualSiteMap()` has no routes and no entry points, so topology
    # detection sees every page as unreachable or dead-ended: on this
    # repository's own corpus that produced 157 Z410/Z411 the server never
    # emits, and it is the reason the topology family had to be excluded below.
    # Driving the LSP along a path no server takes is what let three
    # divergences through, so the harness now takes the real one.
    md_contents = {
        p: p.read_text(encoding="utf-8", errors="replace") for p in docs_root.rglob("*.md")
    }
    vsm = build_vsm(
        adapter,
        docs_root,
        md_contents,
        anchors_cache={p: set() for p in md_contents},
        extra_content_roots=[],
        repo_root=repo_root,
        static_assets=set(),
    )
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


def test_parity_uppercase_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Extension case, the divergence the first three fixtures could not reach.

    `discovery.py` compared `path.suffix` verbatim while the LSP compared
    `path.suffix.lower()`, so a credential in `notes.MD` was analysed by the
    editor and invisible to `zenzic check all` -- exit 1 where the Exit Code
    Contract owes exit 2. Every original fixture used lowercase `.md`, so all
    three agreed while the class diverged (V031_FIX_SUFFIX_CASE_BYPASS).
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    body = " ".join(["word"] * 55)
    (docs / "index.md").write_text(f"# Home\n\n[Notes](notes.MD). {body}\n", encoding="utf-8")
    (docs / "notes.MD").write_text(f"# Notes\n\n[Home](index.md). {body}\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").touch()

    _assert_parity(tmp_path, docs, monkeypatch)
