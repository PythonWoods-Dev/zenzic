# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A configuration file that will not parse must not blank the editor.

`test_lsp_protocol_robustness.py` has asserted this since it was written, under
a class named `TestAConfigErrorDoesNotBlankTheWorkspace` — and it asserted it
against `IncrementalAnalysisEngine`, handed a default `ZenzicConfig()`. The
config error therefore never reached the code that blanks the workspace.

Measured 2026-09-21 on the real server: with a malformed `pyproject.toml`,
`LanguageServer._sync_workspace_and_publish()` raises `ZenzicConfigError` out of
`ZenzicConfig.load()` and publishes **zero** diagnostics. The file under it
holds an `AKIA` credential — a security-tier finding — and the author sees
nothing at all.

This is the second instance of one shape, found by auditing the first. The
first was a declared engine whose adapter could not be built
(`test_a_declared_engine_needs_its_config.py`); this is the configuration that
could not be read. Both raised upstream of the analysis engine, both went
unseen because the test for them built the engine directly, and both leave an
editor that looks like a clean document.

The CLI stops, correctly, and says why. The editor cannot: going dark is the
one outcome `_resolve_docs_root` names as worse than widening. It keeps the
defaults, keeps analysing, and says so as `Z110` on the file that will not
parse.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

from zenzic.lsp.server import LanguageServer


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."

_BROKEN = {
    "pyproject.toml": '[project\nname = "x"\n',
    ".zenzic.toml": 'docs_dir = "docs"\nfail_under = \n',
}


def _project(tmp_path: Path, filename: str) -> Path:
    (tmp_path / filename).write_text(_BROKEN[filename], encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        f'# P\n\n{_PROSE}\n\n    aws_key = "{_SECRET}"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _published(project: Path) -> dict[str, set[str]]:
    """Codes per file name, from the JSON-RPC the server actually wrote."""
    server = LanguageServer()
    server.stdout = io.BytesIO()
    server.repo_root = project
    server._sync_workspace_and_publish()

    raw = server.stdout.getvalue().decode("utf-8")
    out: dict[str, set[str]] = {}
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
            name = message["params"]["uri"].rsplit("/", 1)[-1]
            out.setdefault(name, set()).update(d["code"] for d in message["params"]["diagnostics"])
    return out


@pytest.mark.parametrize("filename", sorted(_BROKEN))
def test_the_credential_is_still_reported(tmp_path: Path, filename: str) -> None:
    """The half that matters most: a security finding must survive it.

    Asserted on the security tier rather than on any diagnostic, because an
    editor that keeps reporting prose rules and drops credentials has blanked
    the part that cannot be blanked.
    """
    published = _published(_project(tmp_path, filename))

    page = published.get("page.md", set())
    assert any(code.startswith("Z2") for code in page), (
        f"the credential went unreported while {filename} was unparseable; "
        f"page.md carried {sorted(page)} and the session published {sorted(published)}"
    )


@pytest.mark.parametrize("filename", sorted(_BROKEN))
def test_the_broken_file_says_so(tmp_path: Path, filename: str) -> None:
    """Degrading silently is the defect one step removed.

    The session is running on built-in defaults, which is not the configuration
    the author wrote and not the one CI will use. `Z110` on the file that will
    not parse is how the editor says that.
    """
    published = _published(_project(tmp_path, filename))

    assert filename in published, (
        f"nothing was published against {filename}; got {sorted(published)}"
    )
    assert "Z110" in published[filename], (
        f"the editor analysed with defaults and did not say so; "
        f"{filename} carried {sorted(published[filename])}"
    )


def test_a_config_that_parses_is_not_this_error(tmp_path: Path) -> None:
    """The other half of the separation, and the positive control's mirror."""
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(f"# P\n\n{_PROSE}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607

    published = _published(tmp_path)

    assert "Z110" not in published.get(".zenzic.toml", set()), (
        "reported a syntax error against a file that parses"
    )
