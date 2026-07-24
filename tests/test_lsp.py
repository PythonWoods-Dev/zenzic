# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Zenzic Language Server (ZLS) foundation."""

import io
import json

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

    def encode_rpc(msg: dict) -> bytes:
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
    assert resp["result"]["capabilities"]["textDocumentSync"] == 2


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

    def encode_rpc(msg: dict) -> bytes:
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

    def encode_rpc(msg: dict) -> bytes:
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
    workspace_uri = f"file://{tmp_path.as_posix()}"
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

    def encode_rpc(msg: dict) -> bytes:
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
            "params": {"rootUri": f"file://{tmp_path}"},
        }
        req_initialized = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        # Open index.md
        req_open = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": f"file://{index_md}", "text": "[broken link](missing.md)"}
            },
        }

        def encode_rpc(msg: dict) -> bytes:
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
                            if d["code"] == "Z101":
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
                        "uri": f"file://{missing_md}",
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


def _collect_diagnostics(text: str, uri: str = "file:///fake/path/doc.md") -> list[dict]:
    """Run the ZLS on a single document and return all emitted diagnostics."""
    import io
    import json

    def encode_rpc(msg: dict) -> bytes:
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

    all_diagnostics: list[dict] = []
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

    def encode_rpc(msg: dict) -> bytes:
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
    owners_uri = f"file://{tmp_path}/i18n/OWNERS"
    yaml_uri = f"file://{tmp_path}/config.yaml"
    md_uri = f"file://{tmp_path}/docs/index.md"

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
    assert server._is_within_domain(f"file://{tmp_path}/README.md") is True

    # Active workspace with default docs_dir="docs"
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    server.repo_root = tmp_path

    assert server._is_within_domain(f"file://{docs_dir}/index.md") is True
    assert server._is_within_domain(f"file://{tmp_path}/README.md") is False
    assert server._is_within_domain(f"file://{tmp_path}/other/page.md") is False


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

    in_uri = f"file://{in_bounds_md.resolve()}"
    out_uri = f"file://{out_bounds_md.resolve()}"

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


def test_lsp_code_action_z121(tmp_path) -> None:
    """Verify textDocument/codeAction returns valid CodeAction WorkspaceEdit for Z121 fix."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = f"file://{tmp_path}/docs/index.md"
    doc_text = "<a>Link without href</a>\n"

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

    # Request code action for Z121 diagnostic
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": doc_uri},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 24},
                },
                "context": {
                    "diagnostics": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 24},
                            },
                            "code": "Z121",
                            "source": "Zenzic",
                            "message": "[Z121] Missing or empty href attribute",
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
    assert len(actions) == 1
    action = actions[0]
    assert action["title"] == 'Fix Z121: Inject placeholder href="#"'
    assert action["kind"] == "quickfix"
    assert doc_uri in action["edit"]["changes"]
    edits = action["edit"]["changes"][doc_uri]
    assert len(edits) == 1
    assert '<a href="#">' in edits[0]["newText"]


def test_lsp_code_action_unfixable(tmp_path) -> None:
    """Verify textDocument/codeAction returns empty list for unfixable diagnostics."""
    server = LanguageServer()
    out_stream = io.BytesIO()
    server.stdout = out_stream

    doc_uri = f"file://{tmp_path}/docs/index.md"
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": doc_uri, "text": "Some text\n"}},
        }
    )

    out_stream.seek(0)
    out_stream.truncate(0)

    # Z120 is unfixable (fixable=False)
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
                            "code": "Z120",
                            "source": "Zenzic",
                            "message": "[Z120] Relative link error",
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
    """Verify _sync_workspace_and_publish emits zenzic/dqsUpdate custom LSP notification."""
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
    assert "zenzic/dqsUpdate" in raw_output

    # Find the zenzic/dqsUpdate message
    dqs_msg = None
    for chunk in raw_output.split("\r\n\r\n"):
        if "zenzic/dqsUpdate" in chunk:
            lines = chunk.strip().splitlines()
            for line_str in lines:
                if line_str.startswith("{"):
                    dqs_msg = json.loads(line_str)
                    break

    assert dqs_msg is not None
    assert dqs_msg["method"] == "zenzic/dqsUpdate"
    assert "score" in dqs_msg["params"]
    assert "base_score" in dqs_msg["params"]
    assert "penalties" in dqs_msg["params"]
    assert dqs_msg["params"]["base_score"] == 100


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

    source_uri = f"file://{source_md.resolve()}"
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


def test_lsp_workspace_initialization_emits_initial_dqs(tmp_path) -> None:
    """Verify that initialized handler triggers workspace sync and emits initial DQS update without opening files."""
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
        "params": {"rootUri": f"file://{tmp_path.resolve()}"},
    }
    initialized_msg = {"jsonrpc": "2.0", "method": "initialized", "params": {}}

    server.handle_message(init_msg)
    server.handle_message(initialized_msg)

    stdout.seek(0)
    raw_output = stdout.read().decode("utf-8")

    assert "zenzic/dqsUpdate" in raw_output
    assert server.vsm is not None
    assert server.engine is not None


def test_lsp_excluded_files_produce_no_diagnostics(tmp_path) -> None:
    """Verify that files inside excluded_dirs (from .zenzic.toml) are dropped by LSP handlers and produce 0 diagnostics."""
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

    ex_uri = f"file://{ex_file.resolve()}"
    assert not server._is_within_domain(ex_uri)

    server.handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": ex_uri, "text": ex_file.read_text(encoding="utf-8")}
            },
        }
    )

    # Document was dropped by domain / exclusion gate
    assert ex_uri not in server.documents.documents


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

    source_uri = f"file://{source_md.resolve()}"
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
