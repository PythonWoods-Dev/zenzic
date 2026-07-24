# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Integration and performance tests for the incremental ZLS sync pipeline."""

import time
from pathlib import Path

from zenzic.models.config import ZenzicConfig
from zenzic.models.diagnostics import ZenzicDiagnostic


def _make_server(tmp_path: Path) -> object:
    """Construct a ready-to-use LanguageServer pointed at tmp_path."""
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.lsp.server import LanguageServer

    config = ZenzicConfig(docs_dir="docs")
    server = LanguageServer()
    server.repo_root = tmp_path
    server.config = config
    server.rule_engine = _build_rule_engine(config)
    server._build_vsm_sync()
    return server


def test_route_diagnostics_are_strictly_typed(tmp_path: Path) -> None:
    """Route.diagnostics must only contain ZenzicDiagnostic instances."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("[Broken](#bad-anchor)", encoding="utf-8")

    server = _make_server(tmp_path)
    server._sync_workspace_and_publish()  # type: ignore[union-attr]

    for route in server.vsm.values():  # type: ignore[union-attr]
        for diag in route.diagnostics:
            assert isinstance(diag, ZenzicDiagnostic), (
                f"Route.diagnostics must contain ZenzicDiagnostic, got {type(diag)}"
            )


def test_cross_file_link_invalidation(tmp_path: Path) -> None:
    """Removing a heading anchor in file B must trigger Z102 in file A."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    file_a = docs_dir / "a.md"
    file_a.write_text("[Link to B](b.md#target)", encoding="utf-8")

    file_b = docs_dir / "b.md"
    file_b.write_text("# Target\nSome text.", encoding="utf-8")

    server = _make_server(tmp_path)
    server._sync_workspace_and_publish()  # type: ignore[union-attr]

    # Confirm no Z102 initially
    route_a = next(
        (r for r in server.vsm.values() if r.source == "a.md"),  # type: ignore[union-attr]
        None,
    )
    assert route_a is not None
    assert not any(d.code == "Z102" for d in route_a.diagnostics), (
        "a.md should have no Z102 violations before the anchor is removed"
    )

    # Simulate didChange: B loses its '#target' anchor
    uri_b = file_b.resolve().as_uri()
    server.overlay.update(uri_b, "No heading here.")  # type: ignore[union-attr]
    server._sync_workspace_and_publish({uri_b})  # type: ignore[union-attr]

    route_a = next(
        (r for r in server.vsm.values() if r.source == "a.md"),  # type: ignore[union-attr]
        None,
    )
    assert route_a is not None
    assert any(d.code == "Z102" for d in route_a.diagnostics), (
        "a.md must report Z102 after b.md's '#target' anchor is removed"
    )


def test_incremental_latency_large_workspace(tmp_path: Path) -> None:
    """A single didChange in a 1000-file workspace must complete in <50ms."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    for i in range(1000):
        (docs_dir / f"file_{i}.md").write_text(f"# Heading {i}\nSome text.", encoding="utf-8")

    server = _make_server(tmp_path)
    server._sync_workspace_and_publish()  # type: ignore[union-attr]  # Full warm-up

    # Single file patch
    target = docs_dir / "file_0.md"
    uri_target = target.resolve().as_uri()
    server.overlay.update(uri_target, "# Modified Heading 0\nNew text.")  # type: ignore[union-attr]

    start = time.perf_counter()
    server._sync_workspace_and_publish({uri_target})  # type: ignore[union-attr]
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50.0, (
        f"Performance invariant violated: incremental didChange took {elapsed_ms:.2f}ms"
    )


def test_no_incoming_links_in_language_server(tmp_path: Path) -> None:
    """LanguageServer must not store incoming_links or file_diagnostics (ADR-075)."""
    server = _make_server(tmp_path)
    server._sync_workspace_and_publish()  # type: ignore[union-attr]

    assert not hasattr(server, "incoming_links"), (
        "LanguageServer must not manage graph topology (ADR-075 Radical Unawareness)"
    )
    assert not hasattr(server, "file_diagnostics"), (
        "LanguageServer must not cache diagnostic payloads in parallel store (Mirror Law)"
    )
