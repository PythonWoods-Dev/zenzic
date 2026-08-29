# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for IncrementalAnalysisEngine in complete isolation.

No LSP server, no mocked stdout/stdin, no JSON-RPC.
The engine is exercised purely through its programmatic API.
"""

from __future__ import annotations

import time
from pathlib import Path

from zenzic.core.adapters import get_adapter
from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.scanner import _build_rule_engine
from zenzic.models.config import ZenzicConfig
from zenzic.models.diagnostics import ZenzicDiagnostic
from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap


def _make_engine(
    tmp_path: Path,
    config: ZenzicConfig | None = None,
) -> tuple[IncrementalAnalysisEngine, VirtualSiteMap, VirtualBufferOverlay]:
    """Construct a ready-to-use engine, VSM, and overlay for a workspace at tmp_path."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(exist_ok=True)
    if config is None:
        config = ZenzicConfig(docs_dir="docs")
    rule_engine = _build_rule_engine(config)
    assert rule_engine is not None
    adapter = get_adapter(config.build_context, docs_dir, tmp_path)
    vsm = VirtualSiteMap()
    overlay = VirtualBufferOverlay(vsm)
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=rule_engine,
        adapter=adapter,
        docs_root=docs_dir,
        repo_root=tmp_path,
    )
    return engine, vsm, overlay


def test_engine_full_sync_produces_diagnostics(tmp_path: Path) -> None:
    """Full sync on a workspace with known violations returns expected findings."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("[Broken](#bad-anchor)", encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    results = engine.process_changes(vsm, overlay)

    # Must produce at least one diagnostic for the broken anchor
    assert len(results) > 0, "Full sync must return results"
    all_diags = [d for diags in results.values() for d in diags]
    assert any(d.code == "Z102" for d in all_diags), "Must detect broken anchor Z102"
    # All diagnostics must be ZenzicDiagnostic instances
    for d in all_diags:
        assert isinstance(d, ZenzicDiagnostic)


def test_engine_detects_forbidden_terms(tmp_path: Path) -> None:
    """Z204 FORBIDDEN_TERM must be detected via the LSP/incremental path too, not
    only the CLI's check_all pipeline (03-priority-table.md,
    V031_LIVE_EXECUTION_BUG_REMEDIATION: a forbidden term configured in
    .zenzic.local.toml previously produced no real-time LSP diagnostic at all
    while editing the same file in VS Code).
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text(
        "# Setup\n\nThe system uses ProjectOmniInternal for backend routing.\n",
        encoding="utf-8",
    )
    # process_changes() reloads config from disk on every call (hot-reload of
    # live .zenzic.toml edits) — a config object passed only to the
    # constructor is overwritten by that reload, so forbidden_patterns must
    # exist in a real file for a full sync to pick it up.
    (tmp_path / ".zenzic.toml").write_text(
        'forbidden_patterns = ["ProjectOmniInternal"]\n', encoding="utf-8"
    )
    config = ZenzicConfig(docs_dir="docs", forbidden_patterns=["ProjectOmniInternal"])

    engine, vsm, overlay = _make_engine(tmp_path, config)
    results = engine.process_changes(vsm, overlay)

    all_diags = [d for diags in results.values() for d in diags]
    z204 = [d for d in all_diags if d.code == "Z204"]
    assert len(z204) == 1, f"Expected exactly one Z204 diagnostic, got: {all_diags}"
    assert "ProjectOmniInternal" in z204[0].message


def test_engine_forbidden_term_and_credential_same_line_first_match_wins(
    tmp_path: Path,
) -> None:
    """A line matching both a credential pattern and a forbidden term must
    yield exactly one finding (the credential scan takes priority), matching
    scanner.py's harvest() first-match-wins semantics — not double-reported.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text(
        "export AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLEwJalrXUtnFEMI  "
        "# ProjectOmniInternal\n",
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.toml").write_text(
        'forbidden_patterns = ["ProjectOmniInternal"]\n', encoding="utf-8"
    )
    config = ZenzicConfig(docs_dir="docs", forbidden_patterns=["ProjectOmniInternal"])

    engine, vsm, overlay = _make_engine(tmp_path, config)
    results = engine.process_changes(vsm, overlay)

    all_diags = [d for diags in results.values() for d in diags]
    security_diags = [d for d in all_diags if d.code in ("Z201", "Z204")]
    assert len(security_diags) == 1, f"Expected exactly one finding, got: {security_diags}"
    assert security_diags[0].code == "Z201"


def test_engine_incremental_returns_only_affected(tmp_path: Path) -> None:
    """After full sync, modifying one file returns diagnostics for that file and dependents only."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# Alpha\nSome text.", encoding="utf-8")
    (docs_dir / "b.md").write_text("# Beta\nSome text.", encoding="utf-8")
    (docs_dir / "c.md").write_text("# Gamma\nSome text.", encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    engine.process_changes(vsm, overlay)  # Full sync

    # Modify only file a.md
    uri_a = (docs_dir / "a.md").resolve().as_uri()
    overlay.update(uri_a, "# Modified Alpha\nNew text.")
    results = engine.process_changes(vsm, overlay, {uri_a})

    # Only a.md (and its dependents, if any) should be in results
    from zenzic.lsp.server import uri_to_path

    returned_filenames = {uri_to_path(uri).name for uri in results}
    assert "a.md" in returned_filenames, "Modified file must be in results"


def test_engine_cross_file_anchor_invalidation(tmp_path: Path) -> None:
    """Removing an anchor in file B produces Z102 in file A (topological dependent)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("[Link to B](b.md#target)", encoding="utf-8")
    (docs_dir / "b.md").write_text("# Target\nSome text.", encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    results = engine.process_changes(vsm, overlay)  # Full sync

    # Confirm no Z102 initially for a.md
    uri_a = (docs_dir / "a.md").resolve().as_uri()
    initial_diags = results.get(uri_a, [])
    assert not any(d.code == "Z102" for d in initial_diags), (
        "a.md should have no Z102 before anchor removal"
    )

    # Remove the '#target' anchor from b.md
    uri_b = (docs_dir / "b.md").resolve().as_uri()
    overlay.update(uri_b, "No heading here.")
    results = engine.process_changes(vsm, overlay, {uri_b})

    # a.md must now report Z102
    a_diags = results.get(uri_a, [])
    assert any(d.code == "Z102" for d in a_diags), (
        "a.md must report Z102 after b.md's '#target' anchor is removed"
    )


def test_engine_deterministic_output(tmp_path: Path) -> None:
    """Identical inputs produce identical diagnostics (ordering, content)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("[Broken](#bad)\n[Also broken](#worse)", encoding="utf-8")

    engine1, vsm1, overlay1 = _make_engine(tmp_path)
    results1 = engine1.process_changes(vsm1, overlay1)

    engine2, vsm2, overlay2 = _make_engine(tmp_path)
    results2 = engine2.process_changes(vsm2, overlay2)

    # Same keys
    assert set(results1.keys()) == set(results2.keys()), (
        "Determinism violation: different URIs returned"
    )

    # Same diagnostics per URI
    for uri in results1:
        diags1 = [(d.code, d.message, d.range.start.line) for d in results1[uri]]
        diags2 = [(d.code, d.message, d.range.start.line) for d in results2[uri]]
        assert diags1 == diags2, f"Determinism violation for {uri}: {diags1} != {diags2}"


def test_engine_no_lsp_imports() -> None:
    """Verify the engine module's import graph contains no LSP/JSON-RPC references."""
    import ast

    import zenzic.core.incremental as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Collect all imported module names
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)

    # Must not import from zenzic.lsp (ADR-075)
    for mod_name in imported_modules:
        assert not mod_name.startswith("zenzic.lsp"), (
            f"ADR-075 violation: engine imports '{mod_name}'"
        )

    # Must not import json (JSON-RPC transport concern)
    assert "json" not in imported_modules, (
        "ADR-075 violation: engine imports json (transport concern)"
    )

    # Must not import sys (stdio concern)
    assert "sys" not in imported_modules, (
        "ADR-075 violation: engine imports sys (transport concern)"
    )

    # Must not import subprocess (Zero Subprocess)
    assert "subprocess" not in imported_modules, (
        "Zero Subprocess violation: engine imports subprocess"
    )

    # Must not import re (ADR-013)
    assert "re" not in imported_modules, "ADR-013 violation: engine imports 're'"


def test_engine_latency_benchmark(tmp_path: Path) -> None:
    """1000-file workspace, single-file change completes in <50ms."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    for i in range(1000):
        (docs_dir / f"file_{i}.md").write_text(f"# Heading {i}\nSome text.", encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    engine.process_changes(vsm, overlay)  # Full warm-up

    # Single file patch
    target = docs_dir / "file_0.md"
    uri_target = target.resolve().as_uri()
    overlay.update(uri_target, "# Modified Heading 0\nNew text.")

    start = time.perf_counter()
    engine.process_changes(vsm, overlay, {uri_target})
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50.0, (
        f"Performance invariant violated: incremental change took {elapsed_ms:.2f}ms (limit: 50ms)"
    )


def test_engine_virtual_route_for_out_of_bounds(tmp_path: Path) -> None:
    """Files outside docs_root get virtual routes (Mirror Law)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# Alpha\nSome text.", encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)

    # Simulate an open buffer outside docs_root
    external_file = tmp_path / "README.md"
    external_file.write_text("# External\nSome text.", encoding="utf-8")
    uri_ext = external_file.resolve().as_uri()
    overlay.update(uri_ext, "# External\nSome text.")

    engine.process_changes(vsm, overlay)

    # The external file should have a virtual route

    found_virtual = False
    for route in vsm.values():
        if route.url.startswith("/_virtual/") and "README" in route.source:
            found_virtual = True
            break
    assert found_virtual, "Mirror Law violation: out-of-bounds file must get a virtual route"


def test_engine_deleted_file_route_removal(tmp_path: Path) -> None:
    """Deleted file's route is removed from VSM."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# Alpha\nSome text.", encoding="utf-8")
    (docs_dir / "b.md").write_text("# Beta\nSome text.", encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    engine.process_changes(vsm, overlay)  # Full sync

    # Verify b.md has a route
    b_sources = [r.source for r in vsm.values()]
    assert any("b.md" in s for s in b_sources), "b.md must have a route after full sync"

    # Simulate deletion of b.md
    uri_b = (docs_dir / "b.md").resolve().as_uri()
    engine.remove_file_cache((docs_dir / "b.md").resolve())
    engine.process_changes(vsm, overlay, {uri_b})

    # b.md route should be removed
    b_sources_after = [r.source for r in vsm.values()]
    assert not any(s == "b.md" for s in b_sources_after), (
        "Deleted file's route must be removed from VSM"
    )
