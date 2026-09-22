# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A declared `zensical`/`mkdocs` with no configuration file, on every surface.

The sibling of `test_a_declared_prebuilt_needs_its_manifest.py`, and it was
missing for the same reason the defect was: the two families fail in different
places.

`prebuilt` and `vsm` are *manifest-driven* — their adapter builds happily
without `.zenzic-vsm.json`, so the missing artefact is caught by an explicit,
shared check (`manifest_missing_error`) that returns rather than raises,
precisely so "the language server calls this too and must turn it into a
diagnostic".

`mkdocs` and `zensical` are *config-driven*. `zensical` raises from `from_repo`;
`mkdocs` used to substitute `StandaloneAdapter` and announce it on stderr only,
which is the same "notice no CI consumer reads" the `prebuilt` work was written
to close. Since 2026-09-21 the factory raises for **any** declared engine whose
configuration is absent, so the three families answer alike.

The CLI wants that raise and exits 1. The editor calls the same factory through
`resolve_container_vocabulary`, upstream of the engine, and inherited a failure
it has no channel for: measured 2026-09-21 on a repository declaring
`engine = "zensical"` with no `zensical.toml`, the server answered `initialize`
and then published **zero** diagnostics for a file the CLI flags, its only trace
one `ZLS Error` line on stderr, where no author looks.

That is the going-dark `_resolve_docs_root` names as worse than widening, and
the silence `Z111` closed for a missing `docs_dir` and again for a missing
manifest. The editor keeps analysing with `standalone` and says so.

The prebuilt test asserts the editor case against `IncrementalAnalysisEngine`
directly. That is why it did not see this: the raise happens in the server,
before the engine is ever constructed. These drive the server.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zenzic.lsp.server import LanguageServer


_ENGINES = {
    "zensical": "zensical.toml",
    "mkdocs": "mkdocs.yml",
}


def _project(tmp_path: Path, engine: str) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.md").write_text(
        "# Home\n\n" + " ".join(["word"] * 60) + "\n\nSee [nowhere](missing.md).\n",
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.toml").write_text(
        f'docs_dir = "docs"\n\n[build_context]\nengine = "{engine}"\n', encoding="utf-8"
    )
    assert not (tmp_path / _ENGINES[engine]).exists()
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", *args],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )


def _published(server: LanguageServer) -> dict[str, set[str]]:
    """Codes per URI, parsed from the JSON-RPC the server actually wrote."""
    raw = server.stdout.getvalue().decode("utf-8")  # type: ignore[union-attr]
    out: dict[str, set[str]] = {}
    while True:
        head = raw.find("\r\n\r\n")
        if head == -1:
            break
        length = 0
        for line in raw[:head].split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1])
        body = raw[head + 4 : head + 4 + length]
        raw = raw[head + 4 + length :]
        msg = json.loads(body)
        if msg.get("method") != "textDocument/publishDiagnostics":
            continue
        params = msg["params"]
        out.setdefault(params["uri"], set()).update(d["code"] for d in params["diagnostics"])
    return out


def _sync(project: Path) -> dict[str, set[str]]:
    server = LanguageServer()
    server.stdout = io.BytesIO()
    server.repo_root = project
    server._sync_workspace_and_publish()
    return _published(server)


@pytest.mark.parametrize("engine", sorted(_ENGINES))
def test_the_cli_refuses(tmp_path: Path, engine: str) -> None:
    """The half that already held for `zensical`: the CLI has somewhere to fail.

    Asserting on `Z111` rather than on exit 1: the fixture contains a broken
    link, so exit 1 is also what a run that substituted the engine and analysed
    the whole tree returns. That green would have said nothing.
    """
    out = _run(_project(tmp_path, engine), "check", "all")

    combined = out.stdout + out.stderr
    assert out.returncode == 1, f"exit {out.returncode}\n{combined}"
    assert "Z101" not in combined, (
        "the run analysed the sources with an engine the user did not declare"
    )
    assert _ENGINES[engine] in combined, "the message does not name the file to create"


@pytest.mark.parametrize("engine", sorted(_ENGINES))
def test_the_editor_says_it_and_keeps_working(tmp_path: Path, engine: str) -> None:
    """The language server has no channel to fail through, so it must not try.

    Driven through the server, not the engine. The manifest test asserts its
    editor case against `IncrementalAnalysisEngine` directly, which is why it
    could not have seen this: the exception was raised while the rule engine
    was being built, before any analysis engine existed.

    Asserting on what was published rather than on the site map, because the
    configuration diagnostic is attached to `.zenzic.toml`, which is not a
    route -- a test reading routes would go green on a server that never said
    anything.
    """
    project = _project(tmp_path, engine)
    published = _sync(project)

    config_uri = (project / ".zenzic.toml").resolve().as_uri()
    assert config_uri in published, (
        f"nothing was published against the configuration file; got {sorted(published)}"
    )
    assert "Z111" in published[config_uri], (
        f"the editor stayed silent about its own configuration; "
        f"codes were {sorted(published[config_uri])}"
    )


@pytest.mark.parametrize("engine", sorted(_ENGINES))
def test_the_editor_still_reports_the_ordinary_findings(tmp_path: Path, engine: str) -> None:
    """Degrading is only worth doing if the author gets their diagnostics.

    A session that reports the configuration error and nothing else is the same
    blank screen with one extra line on it. Before the fix this was zero
    diagnostics for `zensical`, measured.
    """
    project = _project(tmp_path, engine)
    published = _sync(project)

    doc_uri = (project / "docs" / "index.md").resolve().as_uri()
    assert doc_uri in published, (
        f"the document produced no diagnostics at all; got {sorted(published)}"
    )
    assert "Z101" in published[doc_uri], (
        f"the broken link went unreported; codes were {sorted(published[doc_uri])}"
    )


def test_a_config_that_exists_is_not_this_error(tmp_path: Path) -> None:
    """The other half of the separation, as the manifest test states it."""
    project = _project(tmp_path, "zensical")
    (project / "zensical.toml").write_text('[site]\nname = "t"\n', encoding="utf-8")

    published = _sync(project)

    config_uri = (project / ".zenzic.toml").resolve().as_uri()
    assert "Z111" not in published.get(config_uri, set()), (
        "reported a configuration error against a configuration that is present"
    )
