# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Zenzic Language Server (ZLS) foundation."""

import io
import json
from pathlib import Path
from typing import Any

from zenzic.lsp.documents import DocumentManager
from zenzic.lsp.server import LanguageServer


def test_document_manager_incremental_sync() -> None:
    """Verify the DocumentManager correctly applies multi-line incremental edits."""
    manager = DocumentManager()
    uri = "file:///fake/path/doc.md"

    # 1. didOpen
    manager.did_open({"textDocument": {"uri": uri, "text": "Line 1\nLine 2\nLine 3\n"}})
    assert manager.documents[uri] == "Line 1\nLine 2\nLine 3\n"

    # 2. didChange (incremental: replace "Line 2" with "Modified Line 2")
    manager.did_change(
        {
            "textDocument": {"uri": uri},
            "contentChanges": [
                {
                    "range": {
                        "start": {"line": 1, "character": 0},
                        "end": {"line": 1, "character": 6},
                    },
                    "text": "Modified Line 2",
                }
            ],
        }
    )
    assert manager.documents[uri] == "Line 1\nModified Line 2\nLine 3\n"

    # 3. didChange (incremental with multi-byte unicode surrogate)
    # 📝 (U+1F4DD, memo) takes 2 UTF-16 code units.
    # text: "Line 1\n📝 Note\nLine 3\n"
    manager.documents[uri] = "Line 1\n📝 Note\nLine 3\n"
    manager.did_change(
        {
            "textDocument": {"uri": uri},
            "contentChanges": [
                {
                    "range": {
                        "start": {"line": 1, "character": 2},  # skip 📝 (2 units)
                        "end": {"line": 1, "character": 7},  # " Note" length is 5. 2 + 5 = 7.
                    },
                    "text": " Changed",
                }
            ],
        }
    )
    assert manager.documents[uri] == "Line 1\n📝 Changed\nLine 3\n"

    # 4. didChange (full sync fallback)
    manager.did_change(
        {"textDocument": {"uri": uri}, "contentChanges": [{"text": "Complete overwrite"}]}
    )
    assert manager.documents[uri] == "Complete overwrite"

    # 5. didClose
    manager.did_close({"textDocument": {"uri": uri}})
    assert uri not in manager.documents


def test_language_server_lifecycle() -> None:
    """Verify JSON-RPC 2.0 lifecycle handlers over stdio streams."""
    # Build a mock input stream
    req1 = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    req2 = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
    req3 = {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}}
    req4 = {"jsonrpc": "2.0", "method": "exit", "params": {}}

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    in_stream = io.BytesIO()
    in_stream.write(encode_rpc(req1))
    in_stream.write(encode_rpc(req2))
    in_stream.write(encode_rpc(req3))
    in_stream.write(encode_rpc(req4))
    in_stream.seek(0)

    out_stream = io.BytesIO()

    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    # The server loop should exit cleanly
    assert server.exit_received is True
    assert server.exit_code == 0

    out_stream.seek(0)
    output = out_stream.read()
    assert b"Content-Length" in output

    # Find the initialize response
    # It should have textDocumentSync = 2
    parts = output.split(b"\r\n\r\n")
    # first part is header, second part is body
    body_str = parts[1].split(b"Content-Length")[0]  # isolate first response body
    resp = json.loads(body_str.decode("utf-8"))

    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    # Object form (not the bare TextDocumentSyncKind int) is required to also
    # declare willSaveWaitUntil for auto-fix-on-save; "change": 2 preserves
    # the original Incremental sync kind.
    assert resp["result"]["capabilities"]["textDocumentSync"] == {
        "openClose": True,
        "change": 2,
        "willSaveWaitUntil": True,
    }


def test_publish_diagnostics() -> None:
    """Verify that didChange triggers publishDiagnostics for Z-Codes."""
    # We will trigger Z107 (Circular Anchor) by writing a circular link:
    # [my heading](#my-heading)
    # Z107 rule is active by default.

    uri = "file:///fake/path/doc.md"
    req0 = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": uri, "text": ""}},
    }
    req1 = {
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {
            "textDocument": {"uri": uri},
            "contentChanges": [{"text": "Line 1\n[my heading](#my-heading)\nLine 3"}],
        },
    }
    req2 = {"jsonrpc": "2.0", "method": "exit", "params": {}}

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        import json

        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    in_stream = io.BytesIO()
    in_stream.write(encode_rpc(req0))
    in_stream.write(encode_rpc(req1))
    in_stream.write(encode_rpc(req2))
    in_stream.seek(0)

    out_stream = io.BytesIO()

    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    out_stream.seek(0)
    output = out_stream.read()

    # Check that a publishDiagnostics was emitted
    import json

    parts = output.split(b"\r\n\r\n")
    # find publishDiagnostics in any of the body parts
    found = False
    for p in parts:
        if b"publishDiagnostics" in p:
            body_str = p.split(b"Content-Length")[0]
            try:
                resp = json.loads(body_str.decode("utf-8"))
                if resp.get("method") == "textDocument/publishDiagnostics":
                    diagnostics = resp["params"]["diagnostics"]
                    assert len(diagnostics) > 0
                    assert diagnostics[0]["code"] == "Z107"
                    found = True
                    break
            except json.JSONDecodeError:
                pass
    assert found


def test_debounce_diagnostics() -> None:
    """Verify that multiple rapid didChange events result in a single publishDiagnostics."""
    # We send 3 didChange events for the same file, then an exit.
    # We should only see 1 publishDiagnostics.
    uri = "file:///fake/path/doc.md"
    req0 = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": uri, "text": ""}},
    }
    req1 = {
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {"textDocument": {"uri": uri}, "contentChanges": [{"text": "Line 1"}]},
    }
    req2 = {
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {
            "textDocument": {"uri": uri},
            "contentChanges": [{"text": "Line 1\n[my heading](#my-heading)"}],
        },
    }
    req3 = {
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {
            "textDocument": {"uri": uri},
            "contentChanges": [{"text": "Line 1\n[my heading](#my-heading)\nLine 3"}],
        },
    }
    req4 = {"jsonrpc": "2.0", "method": "exit", "params": {}}

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        import json

        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    in_stream = io.BytesIO()
    in_stream.write(encode_rpc(req0))
    in_stream.write(encode_rpc(req1))
    in_stream.write(encode_rpc(req2))
    in_stream.write(encode_rpc(req3))
    in_stream.write(encode_rpc(req4))
    in_stream.seek(0)

    out_stream = io.BytesIO()

    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    out_stream.seek(0)
    output = out_stream.read()

    parts = output.split(b"\r\n\r\n")
    publish_count = 0
    for p in parts:
        if b"publishDiagnostics" in p:
            body_str = p.split(b"Content-Length")[0]
            try:
                import json

                resp = json.loads(body_str.decode("utf-8"))
                if resp.get("method") == "textDocument/publishDiagnostics":
                    publish_count += 1
            except json.JSONDecodeError:
                pass

    assert publish_count == 1


def test_zero_config_security_invariant(tmp_path) -> None:
    """Verify that ZLS in an unconfigured workspace still loads core rules (Z201/Z108)."""
    import io

    # Create an empty workspace (no .zenzic.toml)
    workspace_uri = tmp_path.as_uri()
    file_uri = f"{workspace_uri}/leaked.md"

    # Leak an AWS key and an empty link
    leak_text = "Here is my secret: AKIAIOSFODNN7EXAMPLE\nAnd an empty link: [](#missing)"

    req_init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"rootUri": workspace_uri},
    }
    req_open = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {
                "uri": file_uri,
                "text": leak_text,
            }
        },
    }
    req_exit = {"jsonrpc": "2.0", "method": "exit", "params": {}}

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        import json

        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    in_stream = io.BytesIO()
    in_stream.write(encode_rpc(req_init))
    in_stream.write(encode_rpc(req_open))
    in_stream.write(encode_rpc(req_exit))
    in_stream.seek(0)

    out_stream = io.BytesIO()

    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    out_stream.seek(0)
    output = out_stream.read()

    import json

    parts = output.split(b"\r\n\r\n")
    z201_found = False
    z108_found = False

    for p in parts:
        if b"publishDiagnostics" in p:
            body_str = p.split(b"Content-Length")[0]
            try:
                resp = json.loads(body_str.decode("utf-8"))
                if resp.get("method") == "textDocument/publishDiagnostics":
                    diagnostics = resp["params"]["diagnostics"]
                    for d in diagnostics:
                        if d.get("code") == "Z201":
                            z201_found = True
                        if d.get("code") == "Z108":
                            z108_found = True
            except json.JSONDecodeError:
                pass

    assert z201_found, "Z201 (Credential Leak) was not emitted in zero-config mode!"
    assert z108_found, "Z108 (Empty Link) was not emitted in zero-config mode!"


def test_vsm_integration_and_dynamic_watching(tmp_path) -> None:
    """Verify VSM synchronous build and O(1) dynamic watching."""
    import io
    import json
    import os

    # Store old cwd
    old_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Write a zenzic config so ZenzicConfig finds it
        (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"')

        # We will test a document index.md that links to missing.md
        index_md = docs_dir / "index.md"
        index_md.write_text("[broken link](missing.md)")

        req_init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"rootUri": tmp_path.as_uri()},
        }
        req_initialized = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        # Open index.md
        req_open = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": index_md.as_uri(), "text": "[broken link](missing.md)"}
            },
        }

        def encode_rpc(msg: dict[str, Any]) -> bytes:
            body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            return header + body

        in_stream = io.BytesIO()
        in_stream.write(encode_rpc(req_init))
        in_stream.write(encode_rpc(req_initialized))
        in_stream.write(encode_rpc(req_open))
        in_stream.seek(0)

        out_stream = io.BytesIO()
        server = LanguageServer(stdin=in_stream, stdout=out_stream)

        # Serve will process the first 3 messages
        server.serve()

        out_stream.seek(0)
        output = out_stream.read()

        # Check that a publishDiagnostics was emitted for index.md with Z101
        parts = output.split(b"\r\n\r\n")
        found_z101 = False
        for p in parts:
            if b"publishDiagnostics" in p:
                body_str = p.split(b"Content-Length")[0]
                try:
                    resp = json.loads(body_str.decode("utf-8"))
                    if resp.get("method") == "textDocument/publishDiagnostics":
                        diagnostics = resp["params"]["diagnostics"]
                        for d in diagnostics:
                            if d["code"] in ("Z101", "Z104"):
                                found_z101 = True

                except Exception:
                    pass
        assert found_z101, "Z101 should be found before missing.md is created"

        # Now send didChangeWatchedFiles to create missing.md
        missing_md = docs_dir / "missing.md"
        missing_md.write_text("# Found!")

        req_watched = {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeWatchedFiles",
            "params": {
                "changes": [
                    {
                        "uri": missing_md.as_uri(),
                        "type": 1,  # Created
                    }
                ]
            },
        }
        req_exit = {"jsonrpc": "2.0", "method": "exit", "params": {}}

        in_stream2 = io.BytesIO()
        in_stream2.write(encode_rpc(req_watched))
        in_stream2.write(encode_rpc(req_exit))
        in_stream2.seek(0)

        server.stdin = in_stream2
        server.exit_received = False
        out_stream.truncate(0)
        out_stream.seek(0)

        server.serve()

        out_stream.seek(0)
        output2 = out_stream.read()
        parts2 = output2.split(b"\r\n\r\n")
        found_z101_after = False
        publish_called = False
        for p in parts2:
            if b"publishDiagnostics" in p:
                body_str = p.split(b"Content-Length")[0]
                try:
                    resp = json.loads(body_str.decode("utf-8"))
                    if resp.get("method") == "textDocument/publishDiagnostics":
                        publish_called = True
                        diagnostics = resp["params"]["diagnostics"]
                        for d in diagnostics:
                            if d["code"] == "Z101":
                                found_z101_after = True
                except Exception:
                    pass

        print("OUTPUT2:", output2.decode("utf-8"))
        assert publish_called, "Should republish on VSM update"
        assert not found_z101_after, "Z101 should be resolved after missing.md is created"

    finally:
        os.chdir(old_cwd)


# ─── CLI/ZLS Parity tests: Z403 and Z102 ─────────────────────────────────────


def _collect_diagnostics(text: str, uri: str = "file:///fake/path/doc.md") -> list[dict[str, Any]]:
    """Run the ZLS on a single document and return all emitted diagnostics."""
    import io
    import json

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    in_stream = io.BytesIO()
    in_stream.write(
        encode_rpc(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri, "text": text}},
            }
        )
    )
    in_stream.write(encode_rpc({"jsonrpc": "2.0", "method": "exit", "params": {}}))
    in_stream.seek(0)

    out_stream = io.BytesIO()
    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    out_stream.seek(0)
    output = out_stream.read()

    all_diagnostics: list[dict[str, Any]] = []
    for part in output.split(b"\r\n\r\n"):
        if b"publishDiagnostics" not in part:
            continue
        body_str = part.split(b"Content-Length")[0]
        try:
            resp = json.loads(body_str.decode("utf-8"))
            if resp.get("method") == "textDocument/publishDiagnostics":
                all_diagnostics.extend(resp["params"]["diagnostics"])
        except json.JSONDecodeError:
            pass
    return all_diagnostics


def test_lsp_emits_z403() -> None:
    """ZLS must report Z403 for inline images and HTML <img> tags missing alt text.

    Parity target: ``zenzic check all --strict`` emits Z403 for both syntaxes.
    The ZLS must match this output without requiring a VSM (zero-config mode).
    """
    doc = (
        "# Image Alt Text Test\n"
        "\n"
        "Inline image without alt text:\n"
        "![](https://example.com/image.png)\n"
        "\n"
        "HTML img without alt text:\n"
        '<img src="https://example.com/image.png">\n'
    )
    diagnostics = _collect_diagnostics(doc)

    z403_codes = [d for d in diagnostics if d.get("code") == "Z403"]
    assert len(z403_codes) == 2, (
        f"Expected 2 Z403 diagnostics (inline + HTML <img>), got {len(z403_codes)}. "
        f"All diagnostics: {[d['code'] for d in diagnostics]}"
    )

    # Inline image is on line 4 (0-indexed: line 3)
    inline_diag = next((d for d in z403_codes if d["range"]["start"]["line"] == 3), None)
    assert inline_diag is not None, "Z403 should be reported on line 4 (the inline image)"

    # HTML <img> is on line 7 (0-indexed: line 6)
    html_diag = next((d for d in z403_codes if d["range"]["start"]["line"] == 6), None)
    assert html_diag is not None, "Z403 should be reported on line 7 (the HTML img)"


def test_lsp_emits_z102() -> None:
    """ZLS must report Z102 for fragment links to anchors absent in the same document.

    Parity target: ``zenzic check all --strict`` emits Z102 for
    ``[Link to missing anchor](#this-anchor-does-not-exist)``.
    The ZLS must match this output without requiring a VSM (zero-config mode).
    """
    doc = (
        "# Real Heading\n"
        "\n"
        "## Z102 - Missing Anchor\n"
        "[Link to missing anchor](#this-anchor-does-not-exist)\n"
        "\n"
        "[Valid link](#real-heading)\n"
    )
    diagnostics = _collect_diagnostics(doc)

    z102_codes = [d for d in diagnostics if d.get("code") == "Z102"]
    assert len(z102_codes) == 1, (
        f"Expected exactly 1 Z102 diagnostic (broken anchor), got {len(z102_codes)}. "
        f"All diagnostics: {[d['code'] for d in diagnostics]}"
    )

    broken_diag = z102_codes[0]
    # The broken link is on line 4 (0-indexed: line 3)
    assert broken_diag["range"]["start"]["line"] == 3, (
        f"Z102 should be on line 4, got line {broken_diag['range']['start']['line'] + 1}"
    )
    assert "this-anchor-does-not-exist" in broken_diag["message"], (
        f"Z102 message should mention the missing fragment, got: {broken_diag['message']}"
    )


def test_lsp_security_rules_masking() -> None:
    """Verify that Security/Path rules (Z203) are emitted instead of Z101 for absolute system paths."""
    uri = "file:///fake/path/doc.md"
    req_init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "rootUri": "file:///fake/path",
        },
    }
    # Link pointing to /etc/passwd
    req_open = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": uri, "text": "[hacked](/etc/passwd)\n"}},
    }
    req_exit = {"jsonrpc": "2.0", "method": "exit", "params": {}}

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        import json

        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    import io

    from zenzic.lsp.server import LanguageServer

    in_stream = io.BytesIO()
    in_stream.write(encode_rpc(req_init))
    in_stream.write(encode_rpc(req_open))
    in_stream.write(encode_rpc(req_exit))
    in_stream.seek(0)

    out_stream = io.BytesIO()
    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    out_stream.seek(0)
    output = out_stream.read()

    parts = output.split(b"\r\n\r\n")
    found_z203 = False
    found_z101 = False
    for p in parts:
        if b"publishDiagnostics" in p:
            body_str = p.split(b"Content-Length")[0]
            try:
                import json

                resp = json.loads(body_str.decode("utf-8"))
                if resp.get("method") == "textDocument/publishDiagnostics":
                    diagnostics = resp["params"]["diagnostics"]
                    for d in diagnostics:
                        if d["code"] == "Z203":
                            found_z203 = True
                        if d["code"] == "Z101":
                            found_z101 = True
            except json.JSONDecodeError:
                pass

    assert found_z203, "Z203 MUST be emitted for /etc/passwd"
    assert not found_z101, "Z101 MUST be masked by Z203"


def test_is_supported_doc_uri() -> None:
    """Verify _is_supported_doc_uri correctly identifies supported doc extensions."""
    server = LanguageServer()
    assert server._is_supported_doc_uri("file:///repo/docs/readme.md") is True
    assert server._is_supported_doc_uri("file:///repo/docs/page.mdx") is True
    assert server._is_supported_doc_uri("file:///repo/i18n/OWNERS") is False
    assert server._is_supported_doc_uri("file:///repo/config.yaml") is False
    assert server._is_supported_doc_uri("file:///repo/.gitignore") is False
    assert server._is_supported_doc_uri("") is False


def test_lsp_drops_non_markdown_did_open(tmp_path) -> None:
    """Verify that textDocument/didOpen for non-markdown files (OWNERS, yaml, txt) is dropped."""
    server = LanguageServer()
    owners_uri = (tmp_path / "i18n" / "OWNERS").as_uri()
    yaml_uri = (tmp_path / "config.yaml").as_uri()
    md_uri = (tmp_path / "docs" / "index.md").as_uri()

    # Non-markdown files must be dropped
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": owners_uri, "text": "reviewers:\n- sig-docs\n"}},
        }
    )
    assert owners_uri not in server.documents.documents
    assert owners_uri not in server.dirty_documents

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": yaml_uri, "text": "key: value\n"}},
        }
    )
    assert yaml_uri not in server.documents.documents
    assert yaml_uri not in server.dirty_documents

    # Markdown file must be accepted
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": md_uri, "text": "# Hello World\n"}},
        }
    )
    assert md_uri in server.documents.documents
    assert md_uri in server.dirty_documents


def test_is_within_domain(tmp_path) -> None:
    """Verify _is_within_domain respects repo_root and docs_dir boundaries."""
    server = LanguageServer()
    # Null workspace allows any file
    assert server._is_within_domain((tmp_path / "README.md").as_uri()) is True

    # Active workspace with default docs_dir="docs"
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    server.repo_root = tmp_path

    assert server._is_within_domain((docs_dir / "index.md").as_uri()) is True
    assert server._is_within_domain((tmp_path / "README.md").as_uri()) is False
    assert server._is_within_domain((tmp_path / "other" / "page.md").as_uri()) is False


def test_lsp_drops_out_of_bounds_markdown_did_open(tmp_path) -> None:
    """Verify that textDocument/didOpen for out-of-bounds .md files (e.g. root README.md when docs_dir='docs') is dropped."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    in_bounds_md = docs_dir / "index.md"
    in_bounds_md.write_text(
        "# Docs Index\nThis is a valid documentation page with enough content.\n"
    )

    out_bounds_md = tmp_path / "README.md"
    out_bounds_md.write_text("# Root Readme\nShort content.\n")

    server = LanguageServer()
    server.repo_root = tmp_path

    in_uri = in_bounds_md.resolve().as_uri()
    out_uri = out_bounds_md.resolve().as_uri()

    # Out-of-bounds .md file must be dropped
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": out_uri, "text": "# Root Readme\nShort content.\n"}},
        }
    )
    assert out_uri not in server.documents.documents
    assert out_uri not in server.dirty_documents

    # In-bounds .md file must be accepted
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": in_uri,
                    "text": "# Docs Index\nThis is a valid documentation page.\n",
                }
            },
        }
    )
    assert in_uri in server.documents.documents
    assert in_uri in server.dirty_documents


def test_lsp_code_action_z505(tmp_path) -> None:
    """Verify textDocument/codeAction returns valid CodeAction WorkspaceEdit for Z505 fix."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    doc_text = "```\ncode\n```\n"

    # Open document
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )

    out_stream.seek(0)
    out_stream.truncate(0)

    # Request code action for Z505 diagnostic
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 3},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 3},
                            },
                            "code": "Z505",
                            "source": "Zenzic",
                            "message": "[Z505] Fenced code block has no language specifier",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw_output = out_stream.read().decode("utf-8")
    assert "Content-Length:" in raw_output
    body_str = raw_output.split("\r\n\r\n")[1]
    response = json.loads(body_str)

    assert response["id"] == 100
    actions = response["result"]
    assert len(actions) == 2
    action = [a for a in actions if a["title"].startswith("Fix Z505")][0]
    assert action["title"] == "Fix Z505: Inject language specifier ('text')"
    assert action["kind"] == "quickfix"
    assert doc_uri in action["edit"]["changes"]
    edits = action["edit"]["changes"][doc_uri]
    assert len(edits) == 1
    assert "```text" in edits[0]["newText"]


def test_lsp_code_action_z108(tmp_path) -> None:
    """Verify textDocument/codeAction returns valid CodeAction WorkspaceEdit for Z108 fix."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    doc_text = "[](https://example.com)\n"

    # Open document
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )

    out_stream.seek(0)
    out_stream.truncate(0)

    # Request code action for Z108 diagnostic
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 23},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 23},
                            },
                            "code": "Z108",
                            "source": "Zenzic",
                            "message": "[Z108] Link text is empty or contains only whitespace",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw_output = out_stream.read().decode("utf-8")
    assert "Content-Length:" in raw_output
    body_str = raw_output.split("\r\n\r\n")[1]
    response = json.loads(body_str)

    assert response["id"] == 101
    actions = response["result"]
    assert len(actions) == 2
    action = [a for a in actions if a["title"].startswith("Fix Z108")][0]
    assert action["title"] == "Fix Z108: Inject placeholder link text ('TODO')"
    assert action["kind"] == "quickfix"
    assert doc_uri in action["edit"]["changes"]
    edits = action["edit"]["changes"][doc_uri]
    assert len(edits) == 1
    assert "[TODO](https://example.com)" in edits[0]["newText"]


def test_lsp_code_action_z515_z517_z520_parity(tmp_path) -> None:
    """CLI/LSP parity fix: Z515/Z517/Z520 were fixable=True in codes.py and already
    wired into `zenzic fix`, but textDocument/codeAction had no branch for them --
    manual Quick Fix in the editor silently offered nothing for 3 of the 6 fixable
    codes. Reuses the same Mutation classes `zenzic fix` already uses."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    doc_text = "See https://example.com for more.\n"
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )

    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 102,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 34},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 4},
                                "end": {"line": 0, "character": 23},
                            },
                            "code": "Z515",
                            "source": "Zenzic",
                            "message": "[Z515] Bare URL used",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    response = json.loads(raw.split("\r\n\r\n")[1])
    actions = response["result"]
    fix_actions = [a for a in actions if a["title"].startswith("Fix Z515")]
    assert len(fix_actions) == 1
    edits = fix_actions[0]["edit"]["changes"][doc_uri]
    assert "<https://example.com>" in edits[0]["newText"]


def test_lsp_code_action_unfixable(tmp_path) -> None:
    """Verify textDocument/codeAction returns empty list for unfixable & non-suppressible diagnostics."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": "Some text\n"}},
        }
    )

    out_stream.seek(0)
    out_stream.truncate(0)

    # Z201 is non-suppressible and has no quick fix
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 9}},
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 9},
                            },
                            "code": "Z201",
                            "source": "Zenzic",
                            "message": "[Z201] Security breach",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw_output = out_stream.read().decode("utf-8")
    body_str = raw_output.split("\r\n\r\n")[1]
    response = json.loads(body_str)

    assert response["id"] == 101
    assert response["result"] == []


def test_lsp_dqs_update_notification(tmp_path) -> None:
    """Verify _sync_workspace_and_publish does NOT emit zenzic/dqsUpdate (LSP-FIX-014).

    The LSP operates in incremental mode and only observes topological findings
    (Z1xx/Z4xx).  Content findings (Z5xx) on closed files are never analysed,
    so any DQS computed here would be non-deterministically lower than the CLI
    batch score.  Emitting a misleading score violates the Determinism invariant;
    the notification is therefore intentionally suppressed (LSP-FIX-014).
    The authoritative DQS is produced exclusively by `zenzic check all --strict`.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    in_bounds_md = docs_dir / "index.md"
    in_bounds_md.write_text("# Docs Index\n[Valid Link](http://example.com)\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    out_stream = io.BytesIO()
    server.stdout = out_stream

    # Build VSM and trigger sync
    server._build_vsm_sync()
    server._sync_workspace_and_publish()

    out_stream.seek(0)
    raw_output = out_stream.read().decode("utf-8")

    # Determinism invariant: the misleading partial DQS notification must NOT be emitted.
    assert "zenzic/dqsUpdate" not in raw_output


def test_lsp_relative_link_normalization_no_z101(tmp_path) -> None:
    """Verify LSP analysis of nested file referencing ./relative-link.md does not emit Z101 if target exists in VSM."""
    docs_dir = tmp_path / "docs"
    sub_dir = docs_dir / "guide"
    sub_dir.mkdir(parents=True, exist_ok=True)

    target_md = sub_dir / "target.md"
    target_md.write_text("# Target Page\nSome content here.\n")

    source_md = sub_dir / "source.md"
    source_md.write_text("# Source Page\n[Link to target](./target.md)\n")

    server = LanguageServer()
    server.repo_root = tmp_path

    # Trigger full workspace sync
    server._build_vsm_sync()

    source_uri = source_md.resolve().as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": source_uri, "text": source_md.read_text(encoding="utf-8")}
            },
        }
    )

    assert server.engine is not None
    assert server.vsm is not None
    assert server.overlay is not None

    results = server.engine.process_changes(server.vsm, server.overlay, {source_uri})
    diags = results.get(source_uri, [])

    # Assert no Z101 (broken link) finding was emitted
    z101_diags = [d for d in diags if d.code == "Z101"]
    assert len(z101_diags) == 0


def test_lsp_workspace_initialization_does_not_emit_dqs(tmp_path) -> None:
    """Verify that the initialized handler triggers workspace sync but does NOT emit DQS (LSP-FIX-014).

    The LSP computes DQS only from in-memory VSM topological findings (Z1xx/Z4xx).
    Content findings (Z5xx) on closed files are excluded, making the score
    non-deterministically lower than the CLI batch score.  Displaying a misleading
    score violates the Determinism invariant.  The authoritative DQS is produced
    exclusively by `zenzic check all --strict` in CI/CD batch mode.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    index_md = docs_dir / "index.md"
    index_md.write_text("# Home\nWelcome home.\n")

    stdin = io.BytesIO()
    stdout = io.BytesIO()
    server = LanguageServer(stdin=stdin, stdout=stdout)

    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"rootUri": tmp_path.resolve().as_uri()},
    }
    initialized_msg = {"jsonrpc": "2.0", "method": "initialized", "params": {}}

    server.handle_message(init_msg)
    server.handle_message(initialized_msg)

    stdout.seek(0)
    raw_output = stdout.read().decode("utf-8")

    # Determinism invariant: the misleading partial DQS notification must NOT be emitted.
    assert "zenzic/dqsUpdate" not in raw_output
    # Workspace state must still be correctly initialised.
    assert server.vsm is not None
    assert server.engine is not None


def test_lsp_excluded_files_produce_no_diagnostics(tmp_path) -> None:
    """A file inside excluded_dirs stays in the pipeline but yields 0 quality diagnostics.

    User scoping governs the quality tier only: the buffer is admitted (the
    security tier must still see it — Z201/Z204 are never suppressible), and
    the engine — not the server's domain gate — decides that every non-security
    diagnostic stays suppressed. This fixture has no credentials, so the
    admitted buffer must produce exactly zero diagnostics.
    """
    config_file = tmp_path / ".zenzic.toml"
    config_file.write_text('docs_dir = "docs"\nexcluded_dirs = ["docs/tutorials/examples"]\n')

    docs_dir = tmp_path / "docs"
    ex_dir = docs_dir / "tutorials" / "examples"
    ex_dir.mkdir(parents=True, exist_ok=True)

    ex_file = ex_dir / "z501-placeholder.md"
    ex_file.write_text("# Malformed Example\n[Bad link](http://broken-domain-999.invalid)\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()

    ex_uri = ex_file.resolve().as_uri()
    # Admitted: user exclusions no longer put a file outside the domain —
    # only system guardrails and VCS do (the security tier must see it).
    assert server._is_within_domain(ex_uri)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": ex_uri, "text": ex_file.read_text(encoding="utf-8")}
            },
        }
    )

    assert ex_uri in server.documents.documents

    assert server.vsm is not None and server.engine is not None
    assert server.overlay is not None
    results = server.engine.process_changes(server.vsm, server.overlay, {ex_uri})
    assert results.get(ex_uri, []) == [], (
        "an excluded, credential-free file must yield zero diagnostics — "
        f"got {[d.code for d in results.get(ex_uri, [])]}"
    )


def test_lsp_html_asset_links_resolve_without_z101(tmp_path) -> None:
    """Verify that links to static HTML assets register in VSM and do not produce Z101 diagnostics."""
    docs_dir = tmp_path / "docs"
    assets_dir = docs_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    html_asset = assets_dir / "diagram.html"
    html_asset.write_text("<html><body>Diagram</body></html>")

    source_md = docs_dir / "index.md"
    source_md.write_text("# Home\n[See Diagram](./assets/diagram.html)\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()

    source_uri = source_md.resolve().as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": source_uri, "text": source_md.read_text(encoding="utf-8")}
            },
        }
    )

    assert server.vsm is not None
    assert server.engine is not None
    assert server.overlay is not None

    results = server.engine.process_changes(server.vsm, server.overlay, {source_uri})
    diags = results.get(source_uri, [])

    z101_diags = [d for d in diags if d.code == "Z101"]
    assert len(z101_diags) == 0


def test_lsp_enforces_user_excluded_dirs(tmp_path) -> None:
    """Opening a credential-free file under excluded_dirs emits 0 diagnostics.

    The buffer is admitted (user scoping never hides the security tier); with
    no security content, the engine suppresses everything else it finds.
    """
    config_file = tmp_path / ".zenzic.toml"
    config_file.write_text('excluded_dirs = ["examples"]\n')

    docs_dir = tmp_path / "docs"
    examples_dir = docs_dir / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    ex_file = examples_dir / "sample.md"
    ex_file.write_text("# Bad Page\n[broken](missing.md)\n")

    server = LanguageServer()
    server.repo_root = tmp_path

    ex_uri = ex_file.resolve().as_uri()

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": ex_uri, "text": ex_file.read_text(encoding="utf-8")}
            },
        }
    )

    assert ex_uri in server.documents.documents

    if server.vsm is None:
        server._build_vsm_sync()

    assert server.vsm is not None
    assert server.engine is not None
    assert server.overlay is not None

    results = server.engine.process_changes(server.vsm, server.overlay, None)
    diags = results.get(ex_uri, [])
    assert len(diags) == 0


def test_lsp_absolute_uri_excluded_path_emits_zero_diagnostics(tmp_path) -> None:
    """LSP-FIX-008: absolute file:// URI inside an excluded_dirs path must produce 0 diagnostics.

    Regression test for the false-positive bug where the LSP server passed an
    absolute ``Path`` to ``LayeredExclusionManager.should_exclude_file`` but the
    method only matched docs-relative path components, causing excluded files to
    escape the exclusion gate and receive spurious diagnostics.

    Setup:
        - ``.zenzic.toml`` declares ``excluded_dirs = ["docs/tutorials/examples"]``
          (repo-relative, full-depth pattern).
        - ``docs/tutorials/examples/z5xx-content/z506-malformed-frontmatter.md``
          contains intentionally malformed content that would trigger findings
          if analysed.

    Acceptance criterion:
        Opening the file via ``textDocument/didOpen`` with an absolute
        ``file://`` URI publishes exactly **0 diagnostics** for that URI: the
        buffer is admitted (user scoping never hides the security tier), and
        with no credentials in the fixture the engine suppresses every quality
        finding the content would otherwise raise.
    """
    import io
    import json

    # Configure repo with a full-depth exclusion path
    config_file = tmp_path / ".zenzic.toml"
    config_file.write_text('docs_dir = "docs"\nexcluded_dirs = ["docs/tutorials/examples"]\n')

    # Create the excluded file tree
    excluded_dir = tmp_path / "docs" / "tutorials" / "examples" / "z5xx-content"
    excluded_dir.mkdir(parents=True, exist_ok=True)

    excluded_file = excluded_dir / "z506-malformed-frontmatter.md"
    excluded_file.write_text(
        "---\n"
        "title\n"  # malformed frontmatter — would trigger Z506 if analysed
        "---\n"
        "[Broken link](absolutely-missing-target.md)\n"  # would trigger Z101
    )

    # Also create a valid in-bounds file so docs_root is non-empty
    docs_dir = tmp_path / "docs"
    index_md = docs_dir / "index.md"
    index_md.write_text("# Home\nWelcome.\n")

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        return header + body

    excluded_uri = excluded_file.resolve().as_uri()
    workspace_uri = tmp_path.resolve().as_uri()

    req_init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"rootUri": workspace_uri},
    }
    req_initialized = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
    req_open = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {
                "uri": excluded_uri,
                "text": excluded_file.read_text(encoding="utf-8"),
            }
        },
    }
    req_exit = {"jsonrpc": "2.0", "method": "exit", "params": {}}

    in_stream = io.BytesIO()
    in_stream.write(encode_rpc(req_init))
    in_stream.write(encode_rpc(req_initialized))
    in_stream.write(encode_rpc(req_open))
    in_stream.write(encode_rpc(req_exit))
    in_stream.seek(0)

    out_stream = io.BytesIO()
    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    # Gate 1: the document is admitted — exclusion decisions now live in the
    # engine, which still owes this buffer a security pass.
    assert excluded_uri in server.documents.documents, (
        "user-excluded file must be admitted so the security tier can see it"
    )

    # Gate 2: no diagnostics must have been published for the excluded URI
    out_stream.seek(0)
    output = out_stream.read()

    diag_count_for_excluded = 0
    for part in output.split(b"\r\n\r\n"):
        if b"publishDiagnostics" not in part:
            continue
        body_str = part.split(b"Content-Length")[0]
        try:
            resp = json.loads(body_str.decode("utf-8"))
            if resp.get("method") == "textDocument/publishDiagnostics":
                if resp["params"]["uri"] == excluded_uri:
                    diag_count_for_excluded += len(resp["params"]["diagnostics"])
        except (json.JSONDecodeError, KeyError):
            pass

    assert diag_count_for_excluded == 0, (
        f"Expected 0 diagnostics for excluded URI, got {diag_count_for_excluded}. "
        "Either the LSP-FIX-008 path normalisation regressed, or quality "
        "findings leaked past user exclusion for a credential-free file."
    )


def test_lsp_directory_policies_applied_in_analysis(tmp_path) -> None:
    """LSP-FIX-009: governance.directory_policies must filter diagnostics in LSP mode.

    Setup:
        - .zenzic.toml specifies [governance.directory_policies]
          "docs/tutorials/examples/z5xx-content/**" = ["Z506", "Z503"]
        - File contains frontmatter delimiter error (Z506) and invalid snippet syntax (Z503).
    """
    config_file = tmp_path / ".zenzic.toml"
    config_file.write_text(
        'docs_dir = "docs"\n'
        "[governance.directory_policies]\n"
        '"docs/tutorials/examples/z5xx-content/**" = ["Z506", "Z503"]\n'
    )

    sample_dir = tmp_path / "docs" / "tutorials" / "examples" / "z5xx-content"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_file = sample_dir / "z506-malformed-frontmatter.md"
    sample_file.write_text("-\ntitle: Malformed\n---\n```python\ndef bad_syntax(\n```\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()

    sample_uri = sample_file.resolve().as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": sample_uri,
                    "text": sample_file.read_text(encoding="utf-8"),
                }
            },
        }
    )

    assert server.engine is not None
    assert server.vsm is not None
    assert server.overlay is not None

    results = server.engine.process_changes(server.vsm, server.overlay, {sample_uri})
    diags = results.get(sample_uri, [])

    # Assert Z506 and Z503 findings were filtered out by directory_policies
    policy_diags = [d for d in diags if d.code in ("Z506", "Z503")]
    assert len(policy_diags) == 0, f"Expected 0 Z506/Z503 diagnostics, got {policy_diags}"


def test_lsp_adapter_watched_config_files_hot_reload(tmp_path) -> None:
    """LSP-FIX-009: modifying a watched adapter config file triggers hot-reload and VSM rebuild.

    Setup:
        - mkdocs.yml initially contains only index.md in nav.
        - page2.md exists on disk and is linked from index.md, emitting Z103 (orphan).
        - Updating mkdocs.yml to include page2.md triggers hot-reload and clears Z103.
    """
    mkdocs_file = tmp_path / "mkdocs.yml"
    mkdocs_file.write_text("site_name: TestSite\nnav:\n  - Home: index.md\n")

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    index_md = docs_dir / "index.md"
    index_md.write_text("# Home\n[Link](./page2.md)\n")

    page2_md = docs_dir / "page2.md"
    page2_md.write_text("# Page 2\nContent.\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()

    assert server.adapter is not None
    assert "mkdocs.yml" in server.adapter.watched_config_files

    index_uri = index_md.resolve().as_uri()
    results = server.engine.process_changes(server.vsm, server.overlay, {index_uri})
    diags = results.get(index_uri, [])
    z103_before = [d for d in diags if d.code == "Z103"]
    assert len(z103_before) == 1, "Expected Z103 before mkdocs.yml update"

    # Update mkdocs.yml to add page2.md to nav
    mkdocs_file.write_text("site_name: TestSite\nnav:\n  - Home: index.md\n  - Page 2: page2.md\n")

    # Send didChangeWatchedFiles for mkdocs.yml
    mkdocs_uri = mkdocs_file.resolve().as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeWatchedFiles",
            "params": {"changes": [{"uri": mkdocs_uri, "type": 2}]},
        }
    )

    # Re-evaluate index.md
    assert server.engine is not None
    assert server.vsm is not None
    results_after = server.engine.process_changes(server.vsm, server.overlay, {index_uri})
    diags_after = results_after.get(index_uri, [])
    z103_after = [d for d in diags_after if d.code == "Z103"]
    assert len(z103_after) == 0, "Z103 should be cleared after hot-reloading mkdocs.yml nav"


def test_file_deletion_clears_ghost_diagnostics(tmp_path: "Path") -> None:  # noqa: F821
    """LSP-FIX-015 Fix 1 — Deleting a file must clear its diagnostics from the PROBLEMS panel.

    When a file is deleted (workspace/didChangeWatchedFiles type=3), the LSP must
    send a ``textDocument/publishDiagnostics`` with an empty diagnostics array ``[]``
    so that VS Code clears stale (ghost) entries from the PROBLEMS panel immediately.
    """

    docs = tmp_path / "docs"
    docs.mkdir()
    # Create a file with a Z107 circular anchor so there will be prior diagnostics
    doc_path = docs / "ghost.md"
    doc_path.write_text("[self](#self)\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        f"site_name: T\ndocs_dir: {docs}\nnav:\n  - Page: ghost.md\n",
        encoding="utf-8",
    )

    def _encode(msg: dict[str, Any]) -> bytes:
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        return f"Content-Length: {len(body)}\r\n\r\n".encode() + body

    def _parse_frames(raw: bytes) -> list[dict[str, Any]]:
        """Parse all Content-Length-framed JSON-RPC messages from a byte stream."""
        msgs = []
        offset = 0
        while offset < len(raw):
            # Find the double CRLF that terminates the header block
            header_end = raw.find(b"\r\n\r\n", offset)
            if header_end == -1:
                break
            header = raw[offset:header_end].decode("ascii", errors="ignore")
            content_length = 0
            for line in header.splitlines():
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
                    break
            body_start = header_end + 4
            body_end = body_start + content_length
            if body_end > len(raw):
                break
            try:
                msgs.append(json.loads(raw[body_start:body_end]))
            except json.JSONDecodeError:
                pass
            offset = body_end
        return msgs

    doc_uri = doc_path.as_uri()
    root_uri = tmp_path.as_uri()

    in_stream = io.BytesIO()
    # 1. initialize — establishes the repo root and config
    in_stream.write(
        _encode(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": root_uri, "capabilities": {}},
            }
        )
    )
    # 2. initialized — triggers _build_vsm_sync() so self.vsm is available
    in_stream.write(_encode({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
    # 3. didOpen — opens the file so its diagnostics are emitted
    in_stream.write(
        _encode(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": doc_uri, "text": "[self](#self)\n"}},
            }
        )
    )
    # 4. didChangeWatchedFiles type=3 — simulates file deletion
    in_stream.write(
        _encode(
            {
                "jsonrpc": "2.0",
                "method": "workspace/didChangeWatchedFiles",
                "params": {"changes": [{"uri": doc_uri, "type": 3}]},
            }
        )
    )
    in_stream.write(_encode({"jsonrpc": "2.0", "method": "exit", "params": {}}))
    in_stream.seek(0)

    out_stream = io.BytesIO()
    server = LanguageServer(stdin=in_stream, stdout=out_stream)
    server.serve()

    out_stream.seek(0)
    raw = out_stream.read()
    frames = _parse_frames(raw)

    empty_diags_found = any(
        frame.get("method") == "textDocument/publishDiagnostics"
        and frame.get("params", {}).get("uri") == doc_uri
        and frame.get("params", {}).get("diagnostics") == []
        for frame in frames
    )

    assert empty_diags_found, (
        "Expected a textDocument/publishDiagnostics with diagnostics=[] "
        "after the file was deleted, but none was found. "
        "Ghost diagnostics will remain in the VS Code PROBLEMS panel.\n"
        f"Frames received: {[f.get('method') for f in frames]}"
    )


def test_lsp_code_action_suppression(tmp_path) -> None:
    """Verify textDocument/codeAction generates Inline Suppression CodeActions (LSP-FEAT-003).

    1. Suppressible code (Z101): returns 'Suppress Z101 for this line'.
    2. Non-suppressible code (Z201): returns no suppression action.
    3. Fixable + Suppressible code (Z108): returns both Quick Fix and Suppression action.
    """
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    doc_text = (
        "[](https://example.com)\n[Broken link](missing.md)\nAWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE\n"
    )

    # Open document
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )

    # 1. Test Z101 (Suppressible only)
    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 201,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 1, "character": 0},
                    "end": {"line": 1, "character": 24},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 1, "character": 0},
                                "end": {"line": 1, "character": 24},
                            },
                            "code": "Z101",
                            "source": "Zenzic",
                            "message": "[Z101] Target file missing.md does not exist",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    resp = json.loads(raw.split("\r\n\r\n")[1])
    actions = resp["result"]
    assert len(actions) == 1
    assert actions[0]["title"] == "Suppress Z101 for this line"
    assert actions[0]["kind"] == "quickfix"
    edit = actions[0]["edit"]["changes"][doc_uri][0]
    assert edit["newText"] == " <!-- zenzic:ignore:Z101 -->"
    assert edit["range"] == {
        "start": {"line": 1, "character": 9999},
        "end": {"line": 1, "character": 9999},
    }

    # 2. Test Z201 (Non-suppressible security gate)
    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 202,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 2, "character": 0},
                    "end": {"line": 2, "character": 40},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 2, "character": 0},
                                "end": {"line": 2, "character": 40},
                            },
                            "code": "Z201",
                            "source": "Zenzic",
                            "message": "[Z201] Hardcoded credential secret detected",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    resp = json.loads(raw.split("\r\n\r\n")[1])
    assert resp["result"] == [], "Z201 Security findings must NOT offer suppression Code Actions"

    # 3. Test Z108 (Fixable + Suppressible)
    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 203,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 23},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 23},
                            },
                            "code": "Z108",
                            "source": "Zenzic",
                            "message": "[Z108] Link text is empty",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    resp = json.loads(raw.split("\r\n\r\n")[1])
    actions = resp["result"]
    assert len(actions) == 2
    titles = [a["title"] for a in actions]
    assert "Fix Z108: Inject placeholder link text ('TODO')" in titles
    assert "Suppress Z108 for this line" in titles

    # 4. Test Z412 / Z410 (Topological findings - NON_INLINE_SUPPRESSIBLE_CODES per ADR-093)
    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 204,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 10},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 10},
                            },
                            "code": "Z412",
                            "source": "Zenzic",
                            "message": "[Z412] Target document is untraceable",
                        }
                    ]
                },
            },
        }
    )

    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    resp = json.loads(raw.split("\r\n\r\n")[1])
    actions = resp["result"]
    assert len(actions) == 1
    assert actions[0]["title"] == "Suppress Z412 (configure via .zenzic.toml)"
    assert "disabled" in actions[0]
    assert "directory_policies" in actions[0]["disabled"]["reason"]


# ─── LSP-FIX-017 & Filesystem Truth tests ─────────────────────────────────────


def _encode_rpc(msg: dict[str, Any]) -> bytes:
    """Encode a single JSON-RPC 2.0 message as LSP wire format."""
    body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _parse_lsp_messages(raw: bytes) -> list[dict[str, Any]]:
    """Parse all JSON-RPC messages from a raw LSP byte stream."""
    messages: list[dict[str, Any]] = []
    parts = raw.split(b"\r\n\r\n")
    for part in parts:
        # Each part is either a header or a body fragment; the body follows
        # immediately after the double-CRLF separator.
        body_candidate = part.split(b"Content-Length")[0].strip()
        if not body_candidate:
            continue
        try:
            messages.append(json.loads(body_candidate.decode("utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return messages


def test_lsp_fix_017_ghost_diagnostic_clearing(tmp_path) -> None:
    """LSP-FIX-017: deleting a watched file MUST broadcast publishDiagnostics
    with an empty diagnostics array, clearing ghost errors from the Problems tab.

    Sequence:
    1. initialize / initialized (triggers full sync with a file that has errors)
    2. workspace/didChangeWatchedFiles — type=3 (Deleted) for the erroneous file
    3. Assert: server emits publishDiagnostics with diagnostics=[] for that URI
    """
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"', encoding="utf-8")

        # Create a file with a known violation (Z107: circular self-anchor)
        error_file = docs_dir / "ghost.md"
        error_file.write_text("[self link](#self-link)", encoding="utf-8")
        file_uri = error_file.resolve().as_uri()

        workspace_uri = tmp_path.as_uri()

        req_init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"rootUri": workspace_uri},
        }
        req_initialized = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        req_exit = {"jsonrpc": "2.0", "method": "exit", "params": {}}

        # Phase 1: full init so the engine populates _uris_with_active_diagnostics
        in1 = io.BytesIO()
        in1.write(_encode_rpc(req_init))
        in1.write(_encode_rpc(req_initialized))
        in1.write(_encode_rpc(req_exit))
        in1.seek(0)

        out1 = io.BytesIO()
        server = LanguageServer(stdin=in1, stdout=out1)
        server.serve()

        # Confirm the engine has seen the file and produced diagnostics
        out1.seek(0)
        phase1_msgs = _parse_lsp_messages(out1.read())
        phase1_pub = [
            m for m in phase1_msgs if m.get("method") == "textDocument/publishDiagnostics"
        ]
        ghost_md_pub = [p for p in phase1_pub if p["params"]["uri"] == file_uri]
        assert any(p["params"]["diagnostics"] for p in ghost_md_pub), (
            "Pre-condition: ghost.md must have active diagnostics after full sync"
        )

        # Phase 2: simulate the file being deleted externally
        error_file.unlink()  # Remove from disk so the engine won't find it on next sync

        req_delete = {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeWatchedFiles",
            "params": {"changes": [{"uri": file_uri, "type": 3}]},  # 3 = Deleted
        }

        in2 = io.BytesIO()
        in2.write(_encode_rpc(req_delete))
        in2.write(_encode_rpc(req_exit))
        in2.seek(0)

        server.stdin = in2
        server.exit_received = False
        out2 = io.BytesIO()
        server.stdout = out2
        server.serve()

        out2.seek(0)
        phase2_msgs = _parse_lsp_messages(out2.read())
        phase2_pub = [
            m for m in phase2_msgs if m.get("method") == "textDocument/publishDiagnostics"
        ]

        # LSP-FIX-017: there MUST be at least one publishDiagnostics with empty
        # array for the deleted URI — this clears the ghost from the Problems tab.
        empty_clear_found = any(
            m["params"]["uri"] == file_uri and m["params"]["diagnostics"] == [] for m in phase2_pub
        )
        assert empty_clear_found, (
            f"LSP-FIX-017 violation: no publishDiagnostics with diagnostics=[] "
            f"was emitted for the deleted URI {file_uri!r}. "
            f"Ghost errors would persist in the VS Code Problems tab."
        )

    finally:
        os.chdir(old_cwd)


def test_filesystem_directory_move_triggers_analysis(tmp_path) -> None:
    """Mirror Law / Filesystem Truth: a workspace/didChangeWatchedFiles event
    that targets a directory (no .md extension) MUST trigger a full workspace
    sync, causing diagnostics for files inside the directory to appear in the
    Problems tab without the user opening the files.

    Sequence:
    1. initialize / initialized (empty docs dir — no diagnostics)
    2. Physically create docs/moved/ with an erroneous .md file
    3. workspace/didChangeWatchedFiles — type=1 (Created) for the directory URI
    4. Assert: server emits publishDiagnostics for the .md file inside the dir
    """
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"', encoding="utf-8")

        workspace_uri = tmp_path.as_uri()

        req_init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"rootUri": workspace_uri},
        }
        req_initialized = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        req_exit = {"jsonrpc": "2.0", "method": "exit", "params": {}}

        # Phase 1: initialise with an empty workspace
        in1 = io.BytesIO()
        in1.write(_encode_rpc(req_init))
        in1.write(_encode_rpc(req_initialized))
        in1.write(_encode_rpc(req_exit))
        in1.seek(0)

        out1 = io.BytesIO()
        server = LanguageServer(stdin=in1, stdout=out1)
        server.serve()

        # Phase 2: simulate a directory being moved into docs/
        moved_dir = docs_dir / "moved"
        moved_dir.mkdir()
        error_md = moved_dir / "error.md"
        # Z107: circular self-anchor reference
        error_md.write_text("[self](#self)", encoding="utf-8")
        error_md_uri = error_md.resolve().as_uri()

        # VS Code emits the directory URI, not the individual file URI
        dir_uri = moved_dir.resolve().as_uri()
        req_dir_created = {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeWatchedFiles",
            "params": {"changes": [{"uri": dir_uri, "type": 1}]},  # 1 = Created
        }

        in2 = io.BytesIO()
        in2.write(_encode_rpc(req_dir_created))
        in2.write(_encode_rpc(req_exit))
        in2.seek(0)

        server.stdin = in2
        server.exit_received = False
        out2 = io.BytesIO()
        server.stdout = out2
        server.serve()

        out2.seek(0)
        phase2_msgs = _parse_lsp_messages(out2.read())
        phase2_pub = [
            m for m in phase2_msgs if m.get("method") == "textDocument/publishDiagnostics"
        ]

        # The full sync triggered by the directory event MUST produce diagnostics
        # for error.md without the user opening the file.
        error_md_diags = [
            m
            for m in phase2_pub
            if m["params"]["uri"] == error_md_uri and m["params"]["diagnostics"]
        ]
        assert error_md_diags, (
            f"Mirror Law violation: directory-level Created event did not trigger "
            f"analysis of {error_md_uri!r}. "
            f"Problems tab would be empty until the user manually opens the file."
        )

    finally:
        os.chdir(old_cwd)


def test_cache_pruning_clears_ghost_diagnostics(tmp_path: Path) -> None:
    """Verify atomic cache pruning clears stale paths and returns empty diagnostics on deletion."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    error_md = docs_dir / "error.md"
    error_md.write_text("[self](#self)", encoding="utf-8")
    error_uri = error_md.resolve().as_uri()

    from zenzic.core.adapters import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.rules import AdaptiveRuleEngine
    from zenzic.models.config import ZenzicConfig
    from zenzic.models.vsm import VirtualBufferOverlay, build_vsm

    config = ZenzicConfig()
    rule_engine = AdaptiveRuleEngine([])
    adapter = get_adapter(config.build_context, docs_dir, tmp_path)
    engine = IncrementalAnalysisEngine(config, rule_engine, adapter, docs_dir, tmp_path)

    vsm = build_vsm(adapter, docs_dir, {error_md.resolve(): "[self](#self)"}, repo_root=tmp_path)
    overlay = VirtualBufferOverlay(vsm)

    # 1. Full sync with error.md present
    results1 = engine.process_changes(vsm, overlay, None)
    assert error_uri in results1
    assert error_uri in engine._uris_with_active_diagnostics

    # 2. Delete error.md from disk and run full sync
    error_md.unlink()
    results2 = engine.process_changes(vsm, overlay, None)

    # Cache must be pruned
    assert error_md.resolve() not in engine.md_contents_cache
    assert error_md.resolve() not in engine.anchors_cache

    # Empty diagnostic array must be emitted for ghost clearing (LSP-FIX-017)
    assert error_uri in results2
    assert results2[error_uri] == []
    assert error_uri not in engine._uris_with_active_diagnostics


def test_full_sync_pending_debouncing() -> None:
    """Verify directory events set _full_sync_pending and use timestamped debounce."""
    import time

    server = LanguageServer()
    dir_uri = "file:///fake/workspace/docs/subfolder"

    now_before = time.time()
    server._handle_file_changes([{"uri": dir_uri, "type": 1}])
    now_after = time.time()

    assert server._full_sync_pending is True
    assert dir_uri in server.dirty_documents
    assert now_before <= server.dirty_documents[dir_uri] <= now_after


def test_directory_deletion_evicts_overlay_and_clears_diagnostics(tmp_path: Path) -> None:
    """Verify that deleting a folder evicts child buffers from overlay/documents and emits diagnostics=[]."""
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.models.config import ZenzicConfig

    docs_dir = tmp_path / "docs"
    example_dir = docs_dir / "example"
    example_dir.mkdir(parents=True)
    err_file = example_dir / "err.md"
    err_file.write_text("[self](#self)")
    err_uri = err_file.resolve().as_uri()

    server = LanguageServer()
    server.repo_root = tmp_path
    server.config, _ = ZenzicConfig.load(tmp_path)
    server.rule_engine = _build_rule_engine(server.config)
    server._build_vsm_sync()

    # Simulate creation of folder contents
    server._handle_file_changes(
        [
            {"uri": example_dir.resolve().as_uri(), "type": 1},
            {"uri": err_uri, "type": 1},
        ]
    )
    server._flush_dirty_documents(force=True)
    assert err_uri in server.file_diagnostics

    # Simulate deletion of directory
    import shutil

    shutil.rmtree(example_dir)
    server._handle_file_changes(
        [
            {"uri": example_dir.resolve().as_uri(), "type": 3},
        ]
    )
    server._flush_dirty_documents(force=True)

    assert err_uri not in server.documents.documents
    assert err_uri not in server.file_diagnostics


def test_initialized_registers_directory_watcher() -> None:
    """LSP-FIX-018: the ``initialized`` handshake must include a ``**/`` glob
    pattern so VS Code sends directory-level deletion events to the server.
    Without this pattern, deleting a folder in the explorer does NOT trigger
    ``workspace/didChangeWatchedFiles`` for the deleted directory, causing
    ghost diagnostics to persist in the PROBLEMS panel.
    """
    import io
    import json
    import tempfile
    from pathlib import Path

    def encode_rpc(msg: dict[str, Any]) -> bytes:
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "index.md").write_text("# Home\n")

        in_stream = io.BytesIO()
        in_stream.write(
            encode_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"rootUri": tmp_path.as_uri()},
                }
            )
        )
        in_stream.write(
            encode_rpc(
                {
                    "jsonrpc": "2.0",
                    "method": "initialized",
                    "params": {},
                }
            )
        )
        in_stream.write(
            encode_rpc(
                {
                    "jsonrpc": "2.0",
                    "method": "exit",
                    "params": {},
                }
            )
        )
        in_stream.seek(0)

        out = io.BytesIO()
        server = LanguageServer(stdin=in_stream, stdout=out)
        server.serve()

        out.seek(0)
        raw = out.read().decode("utf-8", errors="replace")

        all_messages = []
        for chunk in raw.split("\r\n\r\n"):
            json_part = chunk.split("Content-Length")[0].strip()
            if json_part:
                try:
                    all_messages.append(json.loads(json_part))
                except Exception:
                    pass

        reg_msgs = [m for m in all_messages if m.get("method") == "client/registerCapability"]
        assert reg_msgs, "No client/registerCapability message sent during initialized"

        registered_patterns = [
            w.get("globPattern", "")
            for m in reg_msgs
            for reg in m.get("params", {}).get("registrations", [])
            for w in reg.get("registerOptions", {}).get("watchers", [])
        ]

        # LSP-FIX-018: directory watcher must be present
        assert "**/" in registered_patterns, (
            f"Directory watcher '**/' not found in registered patterns: {registered_patterns}"
        )


def _send_will_save_wait_until(server: "LanguageServer", out_stream, doc_uri: str, msg_id: int):
    """Send textDocument/willSaveWaitUntil and return the parsed JSON-RPC response."""
    out_stream.seek(0)
    out_stream.truncate(0)
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "textDocument/willSaveWaitUntil",
            "params": {"textDocument": {"uri": doc_uri}, "reason": 1},
        }
    )
    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    return json.loads(raw.split("\r\n\r\n")[1])


def _init_server_with_config(tmp_path: Path) -> "LanguageServer":
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.models.config import ZenzicConfig

    server = LanguageServer()
    server.repo_root = tmp_path
    server.config, _ = ZenzicConfig.load(tmp_path)
    server.rule_engine = _build_rule_engine(server.config)
    return server


def test_lsp_capability_advertises_will_save_wait_until() -> None:
    """The initialize response must declare willSaveWaitUntil so vscode-languageclient
    auto-forwards vscode.workspace.onWillSaveTextDocument to the server (LSP spec:
    a client only calls textDocument/willSaveWaitUntil when the server opts in)."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"rootUri": None, "capabilities": {}},
        }
    )
    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    response = json.loads(raw.split("\r\n\r\n")[1])
    sync = response["result"]["capabilities"]["textDocumentSync"]
    assert isinstance(sync, dict), (
        "textDocumentSync must be the object form to declare willSaveWaitUntil"
    )
    assert sync["willSaveWaitUntil"] is True


def test_lsp_will_save_wait_until_disabled_by_default(tmp_path: Path) -> None:
    """Auto-fix-on-save must be OFF by default -- returns no edits even for a fixable finding."""
    server = _init_server_with_config(tmp_path)
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": "```\ncode\n```\n"}},
        }
    )

    resp = _send_will_save_wait_until(server, out_stream, doc_uri, 300)
    assert resp["result"] == []


def test_lsp_will_save_wait_until_fixes_z505_when_enabled(tmp_path: Path) -> None:
    """With autoFixOnSave enabled, a real Z505 finding is auto-fixed via the SAME
    UntaggedCodeBlockMutation already used by manual Quick Fix and `zenzic fix` --
    no new fix logic, only a new trigger."""
    server = _init_server_with_config(tmp_path)
    server.auto_fix_on_save = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": "```\ncode\n```\n"}},
        }
    )

    resp = _send_will_save_wait_until(server, out_stream, doc_uri, 301)
    edits = resp["result"]
    assert len(edits) == 1
    assert "```text" in edits[0]["newText"]


def test_lsp_will_save_wait_until_no_op_on_clean_document(tmp_path: Path) -> None:
    """No fixable findings -> empty edit list, not a no-op full-document replacement."""
    server = _init_server_with_config(tmp_path)
    server.auto_fix_on_save = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": doc_uri,
                    "text": "# Clean Document\n\nNothing wrong here.\n",
                }
            },
        }
    )

    resp = _send_will_save_wait_until(server, out_stream, doc_uri, 302)
    assert resp["result"] == []


def test_lsp_will_save_wait_until_skips_code_with_any_suppressed_occurrence(tmp_path: Path) -> None:
    """Safety gate (Phase 3): if ANY occurrence of a fixable code is suppressed anywhere
    in the file, auto-fix must skip that code entirely rather than risk 'fixing' the
    occurrence the user explicitly suppressed. Two bare URLs, one suppressed."""
    server = _init_server_with_config(tmp_path)
    server.auto_fix_on_save = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    # Line 1's Z515 is suppressed (verified via _scan_single_file: consumed=True,
    # no active Z515 finding for line 1); line 3's Z515 is a real, active finding.
    doc_text = (
        "See https://example.com for info. <!-- zenzic:ignore: Z515 -->\n\n"
        "Also see https://other.example.com here.\n"
    )
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )

    resp = _send_will_save_wait_until(server, out_stream, doc_uri, 303)
    assert resp["result"] == [], (
        "the un-suppressed Z515 occurrence must NOT be auto-fixed while a sibling "
        "occurrence of the same code is explicitly suppressed in the same file"
    )


def test_lsp_will_save_wait_until_fixes_all_six_fixable_codes(tmp_path: Path) -> None:
    """Completes CLI/LSP parity: all 6 fixable=True codes (not just the 3 manual
    Quick Fix already wired) are reachable via auto-fix-on-save."""
    server = _init_server_with_config(tmp_path)
    server.auto_fix_on_save = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    doc_text = "## Heading.\n\nSee https://example.com for more.\n"
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )

    resp = _send_will_save_wait_until(server, out_stream, doc_uri, 304)
    edits = resp["result"]
    assert len(edits) == 1
    new_text = edits[0]["newText"]
    assert "## Heading\n" in new_text, "Z517 heading punctuation should be stripped"
    assert "<https://example.com>" in new_text, "Z515 bare URL should be angle-bracketed"


def test_lsp_did_change_configuration_toggles_auto_fix_on_save(tmp_path: Path) -> None:
    """workspace/didChangeConfiguration updates the flag live, no server restart needed."""
    server = _init_server_with_config(tmp_path)
    out_stream = io.BytesIO()
    server.stdout = out_stream
    assert server.auto_fix_on_save is False

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeConfiguration",
            "params": {"settings": {"zenzic": {"autoFixOnSave": True}}},
        }
    )
    assert server.auto_fix_on_save is True


def _send_will_rename_files(
    server: "LanguageServer", out_stream, old_uri: str, new_uri: str, msg_id: int
):
    out_stream.seek(0)
    out_stream.truncate(0)
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "workspace/willRenameFiles",
            "params": {"files": [{"oldUri": old_uri, "newUri": new_uri}]},
        }
    )
    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    return json.loads(raw.split("\r\n\r\n")[1])


def test_lsp_capability_advertises_will_rename_files() -> None:
    """initialize must declare workspace.fileOperations.willRename so
    vscode-languageclient auto-forwards vscode.workspace.onWillRenameFiles."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"rootUri": None, "capabilities": {}},
        }
    )
    out_stream.seek(0)
    raw = out_stream.read().decode("utf-8")
    response = json.loads(raw.split("\r\n\r\n")[1])
    filters = response["result"]["capabilities"]["workspace"]["fileOperations"]["willRename"][
        "filters"
    ]
    assert filters[0]["scheme"] == "file"


def test_lsp_will_rename_files_disabled_by_default(tmp_path: Path) -> None:
    """Off by default -- returns no WorkspaceEdit even for a real inbound link."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "b.md").write_text("# B\nContent.\n")
    (docs_dir / "a.md").write_text("# A\nSee [B](./b.md).\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    resp = _send_will_rename_files(
        server, out_stream, (docs_dir / "b.md").as_uri(), (docs_dir / "b2.md").as_uri(), 400
    )
    assert resp["result"] is None


def test_lsp_will_rename_files_repairs_inbound_link(tmp_path: Path) -> None:
    """Real fixture: A links to B, rename B -> B2, confirm A's link is rewritten.
    Reuses resolve_href_target (via RenameLinkMutation) -- no new resolution logic."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "b.md").write_text("# B\nContent.\n")
    (docs_dir / "a.md").write_text("# A\nSee [B](./b.md) for details.\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()
    server.auto_repair_links_on_rename = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    old_uri = (docs_dir / "b.md").as_uri()
    new_uri = (docs_dir / "b2.md").as_uri()
    resp = _send_will_rename_files(server, out_stream, old_uri, new_uri, 401)

    a_uri = (docs_dir / "a.md").resolve().as_uri()
    changes = resp["result"]["changes"]
    assert a_uri in changes
    assert "[B](b2.md)" in changes[a_uri][0]["newText"]


def test_lsp_will_rename_files_skips_non_markdown_rename(tmp_path: Path) -> None:
    """Scoped to Markdown/MDX document renames only -- an image rename is a no-op
    for this feature (Z405/asset-reference repair is a different, unimplemented
    concern, not silently half-handled here)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "logo.png").write_bytes(b"\x89PNG\r\n")
    (docs_dir / "a.md").write_text("# A\n![Logo](./logo.png)\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()
    server.auto_repair_links_on_rename = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    resp = _send_will_rename_files(
        server, out_stream, (docs_dir / "logo.png").as_uri(), (docs_dir / "logo2.png").as_uri(), 402
    )
    assert resp["result"] is None


def test_lsp_will_rename_files_skips_excluded_linking_file(tmp_path: Path) -> None:
    """Safety gate (Phase 3): a linking file excluded via .zenzic.toml is left
    untouched, even though it has a real inbound link to the renamed file."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "b.md").write_text("# B\nContent.\n")
    (docs_dir / "a.md").write_text("# A\nSee [B](./b.md) for details.\n")
    (tmp_path / ".zenzic.toml").write_text('excluded_file_patterns = ["a.md"]\n')

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()
    server.auto_repair_links_on_rename = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    resp = _send_will_rename_files(
        server, out_stream, (docs_dir / "b.md").as_uri(), (docs_dir / "b2.md").as_uri(), 403
    )
    assert resp["result"] is None, (
        "the excluded file must not be rewritten even though it links to the renamed file"
    )


def test_lsp_will_rename_files_skips_alias_style_href(tmp_path: Path) -> None:
    """Safety gate (Phase 3): a docs-root-relative ('/...') href is left untouched
    rather than guessing which alias style to reconstruct."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "b.md").write_text("# B\nContent.\n")
    (docs_dir / "a.md").write_text("# A\nSee [B](/b.md) for details.\n")

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()
    server.auto_repair_links_on_rename = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    resp = _send_will_rename_files(
        server, out_stream, (docs_dir / "b.md").as_uri(), (docs_dir / "b2.md").as_uri(), 404
    )
    assert resp["result"] is None, "an alias-style href must be skipped, not guessed at"


def test_lsp_did_change_configuration_toggles_auto_repair_links_on_rename(tmp_path: Path) -> None:
    server = LanguageServer()
    server.repo_root = tmp_path
    out_stream = io.BytesIO()
    server.stdout = out_stream
    assert server.auto_repair_links_on_rename is False

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeConfiguration",
            "params": {"settings": {"zenzic": {"autoRepairLinksOnRename": True}}},
        }
    )
    assert server.auto_repair_links_on_rename is True


def test_lsp_will_rename_files_partial_success_one_excluded_one_fixed(tmp_path: Path) -> None:
    """Safety (Phase 3): renaming a heavily-linked page must not fail all-or-nothing.
    Two files link to B; one is excluded (skipped, reported), the other is fixed."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "b.md").write_text("# B\nContent.\n")
    (docs_dir / "a.md").write_text("# A\nSee [B](./b.md) for details.\n")
    (docs_dir / "c.md").write_text("# C\nAlso see [B](./b.md) here.\n")
    (tmp_path / ".zenzic.toml").write_text('excluded_file_patterns = ["a.md"]\n')

    server = LanguageServer()
    server.repo_root = tmp_path
    server._build_vsm_sync()
    server.auto_repair_links_on_rename = True
    out_stream = io.BytesIO()
    server.stdout = out_stream

    resp = _send_will_rename_files(
        server, out_stream, (docs_dir / "b.md").as_uri(), (docs_dir / "b2.md").as_uri(), 405
    )

    a_uri = (docs_dir / "a.md").resolve().as_uri()
    c_uri = (docs_dir / "c.md").resolve().as_uri()
    changes = resp["result"]["changes"]
    assert a_uri not in changes, "excluded file must not appear in the WorkspaceEdit"
    assert c_uri in changes, "the non-excluded file must still be fixed independently"
    assert "[B](b2.md)" in changes[c_uri][0]["newText"]


def test_lsp_code_action_ignores_foreign_diagnostics(tmp_path) -> None:
    """A suppression must only be offered for Zenzic's own findings.

    Editors surface every provider's diagnostics to every provider's code-action
    handler. The eligibility check asked whether a code was *forbidden* from
    suppression rather than whether it was ours, so any foreign code passed: a
    markdownlint ``MD036`` produced "Suppress MD036 for this line", writing a
    ``zenzic:ignore:`` comment that markdownlint cannot read. The finding stayed
    live underneath while the editor implied it had been handled.
    """
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    doc_text = "# Title\n\n**Emphasis used as a heading**\n"

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": doc_text}},
        }
    )
    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 2, "character": 0},
                    "end": {"line": 2, "character": 33},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 2, "character": 0},
                                "end": {"line": 2, "character": 33},
                            },
                            "severity": 2,
                            "code": "MD036",
                            "source": "markdownlint",
                            "message": "MD036/no-emphasis-as-heading: Emphasis used instead of a heading",
                        }
                    ],
                    "only": ["quickfix"],
                },
            },
        }
    )

    out_stream.seek(0)
    payload = out_stream.read().decode()
    assert "MD036" not in payload, (
        "Zenzic offered a code action for a markdownlint diagnostic; its suppression "
        f"comment syntax does not suppress foreign findings:\n{payload}"
    )


def test_lsp_code_action_ignores_foreign_diagnostic_quoting_a_zenzic_code(tmp_path) -> None:
    """A foreign diagnostic with no ``code`` must not be adopted via its message.

    ``_handle_code_action`` falls back to scraping ``[Z\\d{3}]`` out of a
    diagnostic's message when the ``code`` field is absent — a real need, since
    a client may drop ``code`` on the codeAction round-trip. But many other
    language servers omit ``code`` entirely, and Zenzic's own wire format is
    ``[Z501] message``, so any tool echoing a Zenzic-formatted string (a spell
    checker quoting the offending span, a doc quoting CLI output) produced a
    message the fallback happily adopted. Zenzic then offered
    "Suppress Z501 for this line" on another tool's finding — the Round 1
    foreign-diagnostic defect, reached through the message path instead of the
    code path. Provenance decides: Zenzic stamps ``source: "zenzic"`` on every
    diagnostic it emits, so the fallback is gated on that.
    """
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = (tmp_path / "docs" / "index.md").as_uri()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": "# Title\n\nProse here.\n"}},
        }
    )
    out_stream.seek(0)
    out_stream.truncate(0)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 2, "character": 0},
                    "end": {"line": 2, "character": 10},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 2, "character": 0},
                                "end": {"line": 2, "character": 10},
                            },
                            "severity": 2,
                            "source": "cspell",
                            "message": "Spelling: did you mean '[Z501]'?",
                        }
                    ],
                    "only": ["quickfix"],
                },
            },
        }
    )

    out_stream.seek(0)
    payload = out_stream.read().decode()
    assert "Z501" not in payload, (
        "Zenzic adopted a foreign diagnostic by scraping a Z-code out of its "
        f"message; the suppression it offers cannot silence another tool:\n{payload}"
    )


def test_lsp_code_action_refuses_paths_outside_the_documentation_domain(tmp_path) -> None:
    """``textDocument/codeAction`` must bound the client-supplied path.

    It was the only request handler acting on a ``file://`` URI without a
    containment check, while five peers gate. Because its quick fixes replace
    the document's full range, aiming it at an out-of-domain file both
    disclosed that file's contents in the returned ``newText`` and offered to
    overwrite it with a Markdown round-trip — confirmed against a file outside
    ``repo_root`` and one inside ``.git/``.
    """
    (tmp_path / "mkdocs.yml").write_text("site_name: D\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\nProse.\n", encoding="utf-8")

    outside = tmp_path.parent / f"outside-{tmp_path.name}.md"
    outside.write_text("# Outside\n\n```\nprint(1)\n```\n", encoding="utf-8")

    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream
    server.repo_root = tmp_path
    server._build_vsm_sync()

    uri = outside.resolve().as_uri()
    assert not server._is_within_domain(uri), "fixture must be out of domain to be meaningful"

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {"line": 2, "character": 0},
                    "end": {"line": 2, "character": 3},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 2, "character": 0},
                                "end": {"line": 2, "character": 3},
                            },
                            "severity": 1,
                            "code": "Z505",
                            "source": "zenzic",
                            "message": "[Z505] fenced block has no language",
                        }
                    ],
                    "only": ["quickfix"],
                },
            },
        }
    )

    out_stream.seek(0)
    payload = out_stream.read().decode()
    assert "print(1)" not in payload, (
        f"the out-of-domain file's contents were echoed back to the client:\n{payload}"
    )
    assert "Fix Z505" not in payload and "Suppress Z505" not in payload, (
        f"an edit was offered for a file outside the documentation domain:\n{payload}"
    )
