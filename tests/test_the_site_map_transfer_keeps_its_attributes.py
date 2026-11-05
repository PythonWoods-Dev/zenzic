# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`vsm.update()` copies dict items and no attribute of the wrapper.

`IncrementalAnalysisEngine.process_changes` rebuilds the site map into a fresh
`VirtualSiteMap` and then transfers it into the caller's instance with
`clear()` + `update()`. Every attribute that lives on the wrapper rather than in
the mapping has to be carried across by hand, and the function's own comments
say so twice — once for `incoming_links`, once for `undeclared_sources`, the
second added after the editor turned out to be "the one surface that never
reports it".

`outgoing_links` was the third and was not carried. Measured 2026-09-21 driving
the real language server: the transferred map held **0** link-graph nodes where
the rebuilt one held 10, so `_find_cycles_iterative` ran over an empty graph and
`_cycle_urls` came back empty on every full sync.

**No finding was lost by it**, and that is worth stating rather than
overclaiming: `Z106` is `info`, and the engine drops `info` before any transport
sees it (LSP-FIX-014), so neither the editor nor `zenzic-mcp` would have shown a
cycle either way. What the omission produced was work done and discarded — the
opt-in flag's cost paid for an answer computed over nothing — and a trap set for
the day `Z106`'s severity changes, when the editor would report nothing and the
severity change would take the blame.

This test asserts the attribute, not the finding, because the attribute is what
is actually broken and a test written against `Z106` would pass for the wrong
reason as long as the `info` filter stands.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path


_PROSE = " ".join(["word"] * 60)


def _project(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    # A cycle: index -> alpha -> beta -> alpha.
    (docs / "index.md").write_text(f"# Home\n\n{_PROSE}\n\n[a](alpha.md)\n", encoding="utf-8")
    (docs / "alpha.md").write_text(f"# Alpha\n\n{_PROSE}\n\n[b](beta.md)\n", encoding="utf-8")
    (docs / "beta.md").write_text(f"# Beta\n\n{_PROSE}\n\n[a](alpha.md)\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[policies]\nenable_circular_link_check = true\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _served(project: Path):  # noqa: ANN202
    from zenzic.lsp.server import LanguageServer

    server = LanguageServer()
    server.stdout = io.BytesIO()
    server.repo_root = project
    server._sync_workspace_and_publish()
    return server


def test_the_link_graph_survives_the_transfer(tmp_path: Path) -> None:
    """Driven through the server, because the transfer is on the path it takes.

    A test that built the site map itself would hold the rebuilt instance and
    never see the copy. That is how this survived: the transfer is only on the
    path the server takes.
    """
    server = _served(_project(tmp_path))

    outgoing = getattr(server.vsm, "outgoing_links", {}) or {}
    assert outgoing, (
        "the session's site map has an empty link graph: `build_vsm` computed one "
        "and `clear()` + `update()` dropped it, exactly as `incoming_links` and "
        "`undeclared_sources` were dropped before they were transferred by hand"
    )


def test_cycle_detection_has_a_graph_to_work_on(tmp_path: Path) -> None:
    """The consequence, one step along: the opt-in flag must buy an answer.

    Asserted on `_cycle_urls` rather than on a published `Z106`, because `Z106`
    is `info` and never reaches a transport. A test on the finding would be
    green on an empty graph.
    """
    server = _served(_project(tmp_path))

    engine = server.engine
    assert engine is not None, "the session built no analysis engine"
    assert getattr(engine, "_cycle_urls", set()), (
        "`enable_circular_link_check` is on, the corpus has a cycle, and the "
        "engine found none -- it ran the detector over an empty graph"
    )
