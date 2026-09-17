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
from zenzic.core.codes import CODE_DEFINITIONS, code_severity
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
#:    different cycles and create a divergence rather than close one.
#:
#:    **Re-measured after a proposal to close it now**, which held the difference
#:    was one nameable class -- edges named ``alias_to_canonical``, added for URL
#:    resolution rather than navigation -- and that filtering them would leave the
#:    graphs identical at 668 edges. **That symbol does not exist anywhere in
#:    src/**, and the measurement does not support the shape: CLI 668 edges, VSM
#:    796, **VSM-only 352 and CLI-only 224** -- a symmetric difference of 576,
#:    not a net of 126. Filtering the one class that *is* nameable -- non-page
#:    targets, which this graph excludes by design, being Markdown-to-Markdown
#:    only -- removes 234 and leaves **118 VSM-only, 224 CLI-only**, four of them
#:    blog-related. Edges such as ``/developers/explanation/`` ->
#:    ``/developers/how-to/write-a-check/`` are in one graph and not the other for
#:    reasons no examined filter explains.
#:
#:    So the deferral rests on two measurements, the second having tested the
#:    first's premise rather than inheriting it. Closing this means giving both
#:    graphs one node identity -- routing through the adapter rather than the file
#:    path -- which is not a filter change. It was deferred to v0.31.1 on that,
#:    not on cost (the DFS itself is 0.47 ms), and then closed on this branch:
#:    see the paragraph below on the trailing-slash defect.
#: **`Z106` was removed from this set on 2026-09-13** and is now compared like any
#: other code. The reason it was excluded -- that the CLI's graph and the VSM's were
#: too different to share the cycle algorithm -- was measured and found to be an
#: artefact: the 576-edge symmetric difference came from an empty anchor cache, which
#: makes every fragment look missing so `_build_link_graph` discards the edge. With
#: real anchors the difference was 236 link occurrences, 235 of them one
#: trailing-slash defect in `resolve_link_to_canonical` and the rest reference
#: definitions missing from the CLI's graph input. Both fixed; the graphs now differ
#: by **one** edge out of ~790, a query-only `?q=` link the CLI mis-resolves to the
#: parent index where a browser stays on the current page.
#:
#: **What actually keeps `Z106` off the editor surface is not the graph.** Implementing
#: the cycle pass on the incremental path proved it: the finding is produced there
#: correctly and then dropped at the transport boundary, because
#: `_findings_to_diagnostics` discards every `info`-severity finding by design
#: (LSP-FIX-014 -- an editor PROBLEMS panel is reserved for what a reader must act on,
#: and the CLI report is the authoritative record of the rest). `Z106` is `note` in
#: `CODE_DEFINITIONS`, which `code_severity` reports as `info`.
#:
#: So the exclusion is a **severity floor**, not a list of names, and it is measured:
#: exactly **four** codes are `note`/`info` -- `Z106`, `Z123`, `Z401`, `Z906` -- and all
#: four are unreachable on the LSP surface for the same stated reason. Naming `Z106`
#: specifically hid that, which is how it was read for a year as a graph problem.
#:
#: What remains excluded, and why -- each measured rather than inherited:
#:
#: * **`Z402`/`Z403`** (CLI, nav-membership) against **`Z410`/`Z411`/`Z412`** (LSP,
#:   VSM-graph reachability). Two different questions, not two answers: "is this page
#:   in the nav?" and "can this page be reached by following links?" A page can
#:   legitimately be one and not the other. Unifying them is an architectural
#:   decision with its own tracked row, not something this guard should pre-empt by
#:   pretending the codes already correspond.
#: * **Every `info`-severity code**, for the transport reason above. This is a
#:   deliberate asymmetry between two surfaces, not a disagreement about a fact: both
#:   paths compute the same finding and only one is allowed to show it.
_TOPOLOGY_FAMILY_CODES = frozenset({"Z402", "Z403", "Z410", "Z411", "Z412"})

#: Codes the LSP transport drops by design, so the CLI side must drop them too before
#: any comparison. Derived from the registry rather than hardcoded, so a code whose
#: severity changes cannot silently start or stop being compared.
_LSP_UNTRANSPORTED_CODES = frozenset(
    code for code in CODE_DEFINITIONS if code_severity(code) == "info"
)


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
        if r["ruleId"] not in _TOPOLOGY_FAMILY_CODES and r["ruleId"] not in _LSP_UNTRANSPORTED_CODES
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
    return sorted(
        d.code
        for d in all_diags
        if d.code not in _TOPOLOGY_FAMILY_CODES and d.code not in _LSP_UNTRANSPORTED_CODES
    )


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


def test_both_paths_detect_the_same_cycle_even_though_only_one_may_show_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `Z106` opted in, the editor must compute the cycle the CLI reports.

    This is the divergence the topology exclusion was hiding, and it had two layers.
    The first was real and is fixed: cycle detection lived only in `scanner.py`, so
    the editor had no cycle pass at all -- a capability missing on one side, not two
    implementations disagreeing. It runs on the incremental path now, over the VSM's
    own reverse index, using the same generic DFS.

    The second layer only became visible once the first was fixed: the finding is
    produced on the editor path and then dropped at the transport boundary, because
    `Z106` is `note`/`info` severity and `_findings_to_diagnostics` discards every
    info finding by design. So the editor will still not *display* it, for a stated
    reason that has nothing to do with graphs -- which is why the exclusion is now a
    severity floor rather than this code's name.

    The deferral rested on the belief that the graphs were too different to share the
    algorithm (a symmetric difference of 576 edges, "reasons no filter explains").
    That was an artefact of an empty anchor cache; the real difference was one
    trailing-slash defect plus reference definitions, and with both fixed the graphs
    differ by one edge out of ~790.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    body = " ".join(["word"] * 55)
    (docs / "index.md").write_text(f"# Home\n\n[Other](other.md). {body}\n", encoding="utf-8")
    (docs / "other.md").write_text(f"# Other\n\n[Home](index.md). {body}\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        "[policies]\nenable_circular_link_check = true\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    # The CLI finds the cycle. Read raw SARIF, without the transport floor applied,
    # or this precondition would filter out the very code it is asserting.
    import json

    result = runner.invoke(app, ["check", "all", "--format", "sarif"])
    raw_ids = sorted(r["ruleId"] for r in json.loads(result.stdout)["runs"][0]["results"])
    assert "Z106" in raw_ids, f"the fixture produces no Z106 on the CLI path: {raw_ids}"

    # The editor computes the same cycle. Asserted on the engine's own cycle set,
    # because the diagnostics it returns have already had the info floor applied.
    config, _ = ZenzicConfig.load(tmp_path)
    adapter = get_adapter(config.build_context, docs, tmp_path)
    md_contents = {p: p.read_text(encoding="utf-8") for p in docs.rglob("*.md")}
    vsm = build_vsm(
        adapter,
        docs,
        md_contents,
        anchors_cache={p: set() for p in md_contents},
        repo_root=tmp_path,
    )
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=_build_rule_engine(config),
        adapter=adapter,
        docs_root=docs,
        repo_root=tmp_path,
    )
    engine.process_changes(vsm, VirtualBufferOverlay(vsm))
    assert getattr(engine, "_cycle_urls", set()) == {"/", "/other/"}, (
        "the editor path did not detect the cycle the CLI reports: "
        f"{getattr(engine, '_cycle_urls', None)}"
    )

    # And the transported surfaces still agree, which is what the guard is for.
    _assert_parity(tmp_path, docs, monkeypatch)
