# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Four ways the language server broke its own stated contracts.

All four were found in one pass by a read-only lens and confirmed by driving the
real server. They share a shape with defects already fixed here: a rule stated
once and implemented at one of several sites.

**A response is not a malformed request.** ``handle_message`` treated "no
``method`` key" as an invalid request and replied ``-32600`` — so the client's
perfectly ordinary reply to the server's own ``client/registerCapability``
request drew an error frame, on an id the client had already retired, on every
single session. The test was a denylist: *not a request I recognise* rather than
*is this a response*.

**A config error blanked every diagnostic.** A syntax error in ``pyproject.toml``
— a file this project neither owns nor writes — made the engine return a result
map containing only the config file's own finding, replacing everything else.
The server publishes what it is handed, so an open document holding a live
credential reported nothing. The module's own comment says a buffer the server
refuses to look at would be a suppression mechanism; this refused all of them at
once.

**A request must be answered — at one handler out of four.** The guarantee was
implemented for ``codeAction`` and stated there as a rule. ``hover``,
``willSaveWaitUntil`` and ``willRenameFiles`` were called bare, and an
unrecognised method got no ``-32601``. ``hover`` returns without responding
whenever the client sent no ``rootUri`` — a single-file editor window — leaving
the request pending forever.

**A malformed range desyncs the buffer silently.** The missing-``text`` case was
fixed with ``.get``; ``range["start"]`` and ``range["end"]`` stayed bare
subscripts, so a change object carrying an empty range raised, was swallowed by
the loop, and left the buffer at its previous value while the editor moved on.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from zenzic.lsp.documents import DocumentManager
from zenzic.lsp.server import LanguageServer


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _server() -> tuple[LanguageServer, io.BytesIO]:
    out = io.BytesIO()
    return LanguageServer(stdin=io.BytesIO(), stdout=out), out


def _frames(out: io.BytesIO) -> list[dict]:
    """Parse every JSON-RPC frame written to the stream."""
    raw = out.getvalue().decode("utf-8", errors="replace")
    messages = []
    while "\r\n\r\n" in raw:
        header, _, rest = raw.partition("\r\n\r\n")
        length = int(next(h.split(":")[1] for h in header.splitlines() if "Content-Length" in h))
        messages.append(json.loads(rest[:length]))
        raw = rest[length:]
    return messages


class TestAResponseIsNotAMalformedRequest:
    def test_a_client_response_draws_no_error_frame(self) -> None:
        srv, out = _server()
        srv.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        out.truncate(0)
        out.seek(0)
        srv.handle_message({"jsonrpc": "2.0", "id": "watch-files", "result": None})
        assert _frames(out) == [], (
            "the server replied to the client's response; a Response object must never be answered"
        )

    def test_an_error_response_from_the_client_is_also_ignored(self) -> None:
        srv, out = _server()
        out.truncate(0)
        out.seek(0)
        srv.handle_message(
            {"jsonrpc": "2.0", "id": "watch-files", "error": {"code": -32601, "message": "no"}}
        )
        assert _frames(out) == []

    def test_a_genuinely_malformed_request_still_errors(self) -> None:
        """Control: dropping responses must not drop real protocol violations."""
        srv, out = _server()
        out.truncate(0)
        out.seek(0)
        srv.handle_message({"jsonrpc": "2.0", "id": 5, "params": {}})
        codes = [f.get("error", {}).get("code") for f in _frames(out)]
        assert -32600 in codes


class TestEveryRequestIsAnswered:
    @pytest.mark.parametrize(
        ("method", "params"),
        [
            (
                "textDocument/hover",
                {
                    "textDocument": {"uri": "file:///x/p.md"},
                    "position": {"line": 0, "character": 0},
                },
            ),
            ("textDocument/willSaveWaitUntil", {"textDocument": {"uri": "file:///x/p.md"}}),
            ("workspace/willRenameFiles", {"files": []}),
            (
                "textDocument/codeAction",
                {"textDocument": {"uri": "file:///x/p.md"}, "context": {"diagnostics": []}},
            ),
        ],
    )
    def test_a_request_gets_a_response_even_with_no_workspace(
        self, method: str, params: dict
    ) -> None:
        """No `rootUri` is a real client state — a single-file editor window."""
        srv, out = _server()
        srv.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        out.truncate(0)
        out.seek(0)
        srv.handle_message({"jsonrpc": "2.0", "id": 77, "method": method, "params": params})
        assert any(f.get("id") == 77 for f in _frames(out)), (
            f"{method} left request id 77 pending forever"
        )

    def test_a_malformed_position_still_gets_a_response(self) -> None:
        srv, out = _server()
        srv.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        out.truncate(0)
        out.seek(0)
        srv.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 78,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": "file:///x/p.md"},
                    "position": {"line": "0", "character": 1},
                },
            }
        )
        assert any(f.get("id") == 78 for f in _frames(out))

    def test_an_unknown_method_gets_method_not_found(self) -> None:
        srv, out = _server()
        out.truncate(0)
        out.seek(0)
        srv.handle_message({"jsonrpc": "2.0", "id": 9, "method": "textDocument/nonsense"})
        codes = [f.get("error", {}).get("code") for f in _frames(out) if f.get("id") == 9]
        assert -32601 in codes

    def test_a_notification_with_an_unknown_method_is_silent(self) -> None:
        """Control: a notification carries no id and must never be answered."""
        srv, out = _server()
        out.truncate(0)
        out.seek(0)
        srv.handle_message({"jsonrpc": "2.0", "method": "$/someNotification"})
        assert _frames(out) == []


class TestAConfigErrorDoesNotBlankTheWorkspace:
    def test_a_credential_still_reports_while_the_config_is_broken(self, tmp_path: Path) -> None:
        from zenzic.core.adapters import get_adapter
        from zenzic.core.incremental import IncrementalAnalysisEngine
        from zenzic.core.scanner import _build_rule_engine
        from zenzic.models.config import ZenzicConfig
        from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap

        (tmp_path / "pyproject.toml").write_text('[project\nname = "x"\n', encoding="utf-8")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "page.md").write_text(
            f'# P\n\n{_PROSE}\n\n    aws_key = "{_SECRET}"\n', encoding="utf-8"
        )

        cfg = ZenzicConfig()
        engine = IncrementalAnalysisEngine(
            cfg,
            _build_rule_engine(cfg),
            get_adapter(cfg.build_context, docs, tmp_path),
            docs,
            tmp_path,
        )
        vsm = VirtualSiteMap()
        results = engine.process_changes(vsm, VirtualBufferOverlay(vsm), None)

        by_name = {
            uri.rsplit("/", 1)[-1]: sorted({d.code for d in diags})
            for uri, diags in results.items()
        }
        assert "Z110" in by_name.get("pyproject.toml", []), (
            "the config error must still be reported"
        )
        assert any("Z201" in codes for codes in by_name.values()), (
            f"a broken, unrelated config file silenced the whole security tier: {by_name}"
        )


class TestAMalformedRangeDoesNotSilentlyDesync:
    @pytest.mark.parametrize(
        "change",
        [
            {"range": {}, "text": "X"},
            {"range": {"start": {"line": 0, "character": 0}}, "text": "X"},
            {"range": {"end": {"line": 0, "character": 0}}, "text": "X"},
            {"range": {"start": {}, "end": {}}, "text": "X"},
        ],
    )
    def test_the_buffer_never_silently_keeps_its_old_value(self, change: dict) -> None:
        dm = DocumentManager()
        dm.did_open({"textDocument": {"uri": "u", "text": "hello\n"}})
        dm.did_change({"textDocument": {"uri": "u"}, "contentChanges": [change]})
        # Order matters: check absence first. Reading the key would raise
        # exactly when the fix is working.
        assert dm.documents.get("u") != "hello\n", (
            "a malformed change left the buffer at its pre-change value with no signal; "
            "every later incremental patch then applies to a wrong base"
        )

    def test_a_well_formed_incremental_change_still_applies(self) -> None:
        """Control: the defensive path must not swallow legitimate edits."""
        dm = DocumentManager()
        dm.did_open({"textDocument": {"uri": "u", "text": "hello\n"}})
        dm.did_change(
            {
                "textDocument": {"uri": "u"},
                "contentChanges": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 5},
                        },
                        "text": "goodbye",
                    }
                ],
            }
        )
        assert dm.documents["u"] == "goodbye\n"
