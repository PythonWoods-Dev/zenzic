# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The CLI and the LSP must report the same security findings for the same file.

Credential and forbidden-term scanning was implemented twice: once in
``scanner.py``'s ``harvest()`` for the full-corpus CLI scan, and once in
``incremental.py``'s ``_analyze_file`` for the buffer-aware LSP path, which never
calls ``harvest()``. Two implementations of one security rule drifted twice:

* ``7bd8fa4`` — ``_analyze_file`` scanned for credentials but never called
  ``scan_line_for_forbidden_terms``, so a configured forbidden term produced a
  finding in CI and **no editor diagnostic at all**.
* ``bfbb676`` — the span-overlap fix (a forbidden term sharing a line with a
  credential must still report) was applied to ``harvest()`` only. The LSP kept
  the old line-granularity skip, so the two paths gave different answers for the
  same line, in the security tier.

Both paths now call one shared primitive, ``scan_security_findings``. These tests
exist so a third divergence fails here rather than shipping: they drive the two
real entry points — ``ReferenceScanner.harvest()`` and the language server's
``process_changes()`` — and compare what each reports.

``zenzic-mcp`` consumes the same ``IncrementalAnalysisEngine``, so it inherits
whatever the LSP path does; keeping the two aligned keeps three consumers aligned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.scanner import ReferenceScanner
from zenzic.lsp.server import LanguageServer
from zenzic.models.config import ZenzicConfig


_SECRET = "AKIAIOSFODNN7EXAMPLE"
_TERM = "ProjectOmniInternal"
_PROSE = (
    "This page carries a comfortable amount of prose so the minimum word-count "
    "check stays quiet and only the finding under discussion is reported here."
)

#: ``harvest()`` labels a credential by detector name and a forbidden term by
#: category; the LSP reports Z-codes. Map both onto codes so they are comparable.
_SECRET_TYPE_TO_CODE = {"FORBIDDEN_TERM": "Z204"}


def _cli_codes(text: str, page: Path, config: ZenzicConfig) -> set[str]:
    """Security codes the CLI path reports, via the real harvest() generator."""
    scanner = ReferenceScanner(page, config)
    return {
        _SECRET_TYPE_TO_CODE.get(data.secret_type, "Z201")
        for _lineno, event_type, data in scanner.harvest(text)
        if event_type == "SECRET"
    }


def _lsp_codes(tmp_path: Path, body: str) -> set[str]:
    """Security codes the LSP path reports, via a real server + process_changes."""
    (tmp_path / ".zenzic.toml").write_text(
        f'docs_dir = "docs"\nforbidden_patterns = ["{_TERM}"]\n', encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    page = docs / "index.md"
    page.write_text(f"# Home\n\n{_PROSE}\n\n{body}\n", encoding="utf-8")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()

    uri = page.resolve().as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": uri, "text": page.read_text(encoding="utf-8")}},
        }
    )
    assert server.engine is not None and server.vsm is not None and server.overlay is not None
    results = server.engine.process_changes(server.vsm, server.overlay, {uri})
    return {d.code for d in results.get(uri, []) if d.code in {"Z201", "Z204"}}


def _both(tmp_path: Path, body: str) -> tuple[set[str], set[str]]:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    page = docs / "index.md"
    text = f"# Home\n\n{_PROSE}\n\n{body}\n"
    page.write_text(text, encoding="utf-8")
    config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=[_TERM])
    return _cli_codes(text, page, config), _lsp_codes(tmp_path, body)


@pytest.mark.parametrize(
    ("label", "body"),
    [
        # The bfbb676 divergence: independent spans sharing one line.
        ("term after credential, same line", f'aws_key = "{_SECRET}"  # {_TERM} rollout'),
        ("term before credential, same line", f'{_TERM} uses aws_key = "{_SECRET}"'),
        # The 7bd8fa4 divergence: a forbidden term with no credential at all.
        ("forbidden term alone", f"The {_TERM} rollout begins next quarter."),
        # Ordinary cases, which must also agree.
        ("credential alone", f'aws_key = "{_SECRET}"'),
        ("both on separate lines", f'aws_key = "{_SECRET}"\n\nThe {_TERM} rollout begins.'),
        ("neither", "Just some ordinary documentation prose."),
    ],
)
def test_cli_and_lsp_report_identical_security_codes(tmp_path: Path, label: str, body: str) -> None:
    cli, lsp = _both(tmp_path, body)
    assert cli == lsp, (
        f"CLI/LSP security divergence for {label!r}: "
        f"CLI reported {sorted(cli) or 'nothing'}, LSP reported {sorted(lsp) or 'nothing'}. "
        "Both paths must route through scan_security_findings."
    )


class TestTheSpecificRegressions:
    """Named so a future failure points straight at the history above."""

    def test_span_overlap_fix_reached_the_lsp(self, tmp_path: Path) -> None:
        """bfbb676 applied to harvest() only; the LSP kept dropping the Z204."""
        cli, lsp = _both(tmp_path, f'aws_key = "{_SECRET}"  # {_TERM} rollout')
        assert "Z204" in cli and "Z204" in lsp
        assert "Z201" in cli and "Z201" in lsp

    def test_forbidden_terms_are_detected_on_both_paths(self, tmp_path: Path) -> None:
        """7bd8fa4: the LSP path once had no forbidden-term scan at all."""
        cli, lsp = _both(tmp_path, f"The {_TERM} rollout begins next quarter.")
        assert cli == {"Z204"} and lsp == {"Z204"}
