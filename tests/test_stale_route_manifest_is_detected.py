# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A route manifest that no longer lists every source is detected and said so.

`PrebuiltVSMAdapter` routes a source it does not find in `.zenzic-vsm.json`
to `status="IGNORED"`, and a link whose target is IGNORED is reported
`Z101 ... UNREACHABLE_LINK`. The consequence: a user adds `docs/new.md`, links
to it from an existing page, and Zenzic reports an error on a link that is
correct. The run named the link; the fix it implied — edit the link — was the
wrong one, and nothing anywhere said the manifest was the reason.

These tests pin the detection (`build_vsm` knows both sets) and the four
surfaces that report it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from zenzic.core.adapters._prebuilt import PrebuiltVSMAdapter
from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.models.config import BuildContext
from zenzic.models.vsm import build_vsm


def _adapter(tmp_path: Path, routes: dict[str, dict[str, str]]) -> PrebuiltVSMAdapter:
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(routes), encoding="utf-8")
    return PrebuiltVSMAdapter(BuildContext(), tmp_path / "docs", repo_root=tmp_path)


def test_a_source_absent_from_the_manifest_is_reported_as_drift(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    adapter = _adapter(tmp_path, {"index.md": {"url": "/", "status": "REACHABLE"}})

    vsm = build_vsm(
        adapter,
        docs,
        {docs / "index.md": "# Home", docs / "new.md": "# Just added"},
    )

    assert vsm.undeclared_sources == ["new.md"]


def test_a_manifest_that_lists_every_source_reports_no_drift(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    adapter = _adapter(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "new.md": {"url": "/new/", "status": "REACHABLE"},
        },
    )

    vsm = build_vsm(
        adapter,
        docs,
        {docs / "index.md": "# Home", docs / "new.md": "# Just added"},
    )

    assert vsm.undeclared_sources == []


def test_an_adapter_that_derives_routes_from_disk_can_never_be_stale(tmp_path: Path) -> None:
    """Drift is a property of a *declared* routing table, not of every adapter.

    `standalone` computes each URL from the path it just read, so there is no
    second copy to fall behind. Reporting drift there would be a finding no
    user could act on.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    adapter = StandaloneAdapter()

    vsm = build_vsm(adapter, docs, {docs / "a.md": "# A"})

    assert vsm.undeclared_sources == []
    assert adapter.declared_sources() is None


def test_an_empty_manifest_is_not_a_manifest(tmp_path: Path) -> None:
    """A `prebuilt` engine with no manifest file falls back to standalone
    routing (every source REACHABLE), which is a different defect with its own
    warning. It must not also be reported as total drift."""
    docs = tmp_path / "docs"
    docs.mkdir()
    adapter = PrebuiltVSMAdapter(BuildContext(), docs, repo_root=tmp_path)

    vsm = build_vsm(adapter, docs, {docs / "a.md": "# A"})

    assert vsm.undeclared_sources == []


# ── The surfaces ───────────────────────────────────────────────────────────────


def _project(tmp_path: Path) -> Path:
    """A `prebuilt` project whose manifest has fallen one page behind."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\nSee the [guide](new.md).\n", encoding="utf-8")
    (docs / "new.md").write_text("# Just added\n", encoding="utf-8")
    (tmp_path / ".zenzic-vsm.json").write_text(
        json.dumps({"index.md": {"url": "/", "status": "REACHABLE"}}), encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )
    return tmp_path


def test_the_cli_names_the_manifest_rather_than_only_the_broken_link(
    tmp_path: Path, monkeypatch: object
) -> None:
    """The user story §9 describes, end to end.

    Before Z115 the only output was `Z101 LINK_BROKEN` on `[guide](new.md)` —
    a link that is correct. The page it points at exists; the manifest simply
    had not been regenerated. The run must now also say so, and name the file
    to regenerate.
    """
    import os
    import subprocess
    import sys

    project = _project(tmp_path)
    subprocess.run(["git", "init", "-q", "."], cwd=project, check=True)  # noqa: S607
    # `encoding`/`errors` explicitly: `text=True` alone decodes with the locale
    # codec, which is cp1252 on the Windows runner and cannot read the box-drawing
    # characters this output carries. The environment is inherited rather than
    # constructed, for the reason recorded in
    # tests/test_a_child_process_inherits_its_environment.py.
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )

    assert "Z115" in (out.stdout or ""), (
        f"no Z115 in stdout.\n  returncode={out.returncode}\n"
        f"  stdout={out.stdout!r}\n  stderr={out.stderr!r}"
    )
    assert "new.md" in out.stdout
    assert ".zenzic-vsm.json" in out.stdout


def test_the_engine_reports_drift_even_when_handed_a_bare_site_map(tmp_path: Path) -> None:
    """Engine-level on purpose, and it says so since 2026-09-21: it was named
    `test_the_editor_…` while never starting the editor. The server's agreement
    is asserted separately, below.

    `server.py` has a fallback that hands `process_changes()` a bare
    `VirtualSiteMap()` (server.py:~850) rather than one `build_vsm` produced.

    `vsm.update(new_vsm)` copies dict items and no attribute of the wrapper, so
    on that path the drift computed during the rebuild is dropped unless it is
    transferred explicitly — exactly as `incoming_links` already is. The
    CLI/LSP parity test does not cover this: its harness builds the map itself
    and the attribute survives from that construction, so it passes with the
    transfer removed. This one does not.
    """
    from zenzic.core.adapter import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.models.config import ZenzicConfig
    from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap

    project = _project(tmp_path)
    docs = project / "docs"
    config, _ = ZenzicConfig.load(project)
    adapter = get_adapter(config.build_context, docs, project)

    vsm = VirtualSiteMap()  # the fallback shape, with no drift of its own
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=_build_rule_engine(config, containers=None),
        adapter=adapter,
        docs_root=docs,
        repo_root=project,
    )
    results = engine.process_changes(vsm, VirtualBufferOverlay(vsm, tabs=None))

    codes = {d.code for diags in results.values() for d in diags}
    assert "Z115" in codes


def test_adding_a_page_reports_drift_without_a_full_rebuild(
    tmp_path: Path,
) -> None:
    """The engine's incremental API, driven directly. Renamed 2026-09-21 for the
    same reason as the test above; the server's own incremental path is asserted
    below.

    Creating a file is the incremental path, and it is the exact moment the
    manifest goes stale.

    `process_changes(changed_uris={...})` patches routes in place and does not
    call `build_vsm`, so a drift recomputed only on a full sync would reach CI
    and not the editor until the next restart — the user would be typing the
    link that Zenzic is about to call broken, with no explanation on screen.
    """
    from zenzic.core.adapter import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.models.config import ZenzicConfig
    from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap, build_vsm

    project = tmp_path
    docs = project / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (project / ".zenzic-vsm.json").write_text(
        json.dumps({"index.md": {"url": "/", "status": "REACHABLE"}}), encoding="utf-8"
    )
    (project / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )

    config, _ = ZenzicConfig.load(project)
    adapter = get_adapter(config.build_context, docs, project)
    md = {(docs / "index.md").resolve(): "# Home\n"}
    vsm = build_vsm(adapter, docs, md)
    assert vsm.undeclared_sources == []  # the manifest is current, to begin with

    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=_build_rule_engine(config, containers=None),
        adapter=adapter,
        docs_root=docs,
        repo_root=project,
    )
    overlay = VirtualBufferOverlay(vsm, tabs=None)
    engine.process_changes(vsm, overlay)  # first call is always a full sync

    # The user adds a page in the editor. The generator has not run again.
    added = docs / "new.md"
    added.write_text("# Just added\n", encoding="utf-8")
    added_uri = added.resolve().as_uri()
    overlay.update(added_uri, "# Just added\n")  # what didOpen does
    results = engine.process_changes(vsm, overlay, {added_uri})

    codes = {d.code for diags in results.values() for d in diags}
    assert "Z115" in codes
    assert isinstance(vsm, VirtualSiteMap)


def test_the_editor_reports_drift_on_its_own_incremental_path(tmp_path: Path) -> None:
    """The two tests above are faithful, and this is what keeps them faithful.

    They reproduce shapes the server uses — a bare `VirtualSiteMap()`, and
    `process_changes` with a changed-URI set — by constructing them. Measured
    2026-09-21, the real server reaches the same answer on both. But neither
    would notice if the server stopped taking those paths: they build the
    arguments themselves, and a test that chooses its own inputs cannot find a
    defect in the choosing.

    So this one drives `LanguageServer` and asserts the sequence an author
    actually performs: open a project whose manifest is current, add a page, and
    see the drift without restarting. `Z115` must be absent on the first sync
    and present on the second — the absence matters as much, because a test that
    only asserts the presence passes against a run that reports drift always.
    """
    import io

    from zenzic.lsp.server import LanguageServer

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / ".zenzic-vsm.json").write_text(
        json.dumps({"index.md": {"url": "/", "status": "REACHABLE"}}), encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607

    def _codes(server: LanguageServer) -> set[str]:
        raw = server.stdout.getvalue().decode("utf-8")  # type: ignore[union-attr]
        out: set[str] = set()
        while True:
            head = raw.find("\r\n\r\n")
            if head == -1:
                break
            length = 0
            for line in raw[:head].split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1])
            message = json.loads(raw[head + 4 : head + 4 + length])
            raw = raw[head + 4 + length :]
            if message.get("method") == "textDocument/publishDiagnostics":
                out.update(d["code"] for d in message["params"]["diagnostics"])
        return out

    server = LanguageServer()
    server.stdout = io.BytesIO()
    server.repo_root = tmp_path
    server._sync_workspace_and_publish()
    assert "Z115" not in _codes(server), "the manifest is current and the session says it drifted"

    added = docs / "new.md"
    added.write_text("# Just added\n", encoding="utf-8")
    uri = added.resolve().as_uri()
    server.documents.documents[uri] = "# Just added\n"
    if server.overlay is not None:
        server.overlay.update(uri, "# Just added\n")

    server.stdout = io.BytesIO()
    server._sync_workspace_and_publish({uri})

    assert "Z115" in _codes(server), (
        "the author added a page and the session did not say the manifest is now "
        "behind it -- the link they are about to write is the one CI will call broken"
    )
