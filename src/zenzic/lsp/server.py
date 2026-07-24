# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Baseline JSON-RPC 2.0 communication protocol over stdio."""

from __future__ import annotations

import json
import os
import select
import sys
import time
import traceback
from pathlib import Path
from typing import Any, BinaryIO, TypedDict, cast
from urllib.parse import unquote, urlsplit

from zenzic.core.adapters import BaseAdapter, get_adapter
from zenzic.core.discovery import DOC_SUFFIXES, iter_markdown_sources, walk_files
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.rules import AdaptiveRuleEngine
from zenzic.core.scanner import _build_rule_engine
from zenzic.lsp.documents import DocumentManager
from zenzic.models.config import ZenzicConfig
from zenzic.models.diagnostics import (
    ZenzicDiagnostic,
)
from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap, build_vsm


class JsonRpcMessage(TypedDict, total=False):
    """PEP 484 TypedDict for JSON-RPC 2.0 message validation."""

    jsonrpc: str
    id: int | str
    method: str
    params: dict[str, Any]


class LanguageServer:
    """Dependency-free JSON-RPC 2.0 dispatcher over raw byte streams."""

    def __init__(self, stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> None:
        """Initialize the server with specific or default byte streams."""
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.shutdown_received = False
        self.exit_received = False
        self.exit_code = 0
        self.documents = DocumentManager()

        # Phase 2: Diagnostic Engine
        self.config: ZenzicConfig | None = None
        self.rule_engine: AdaptiveRuleEngine | None = None
        self.exclusion_mgr: LayeredExclusionManager | None = None

        # Phase 3: Debounce
        self.dirty_documents: dict[str, float] = {}

        # Phase 4: VSM Integration
        self.repo_root: Path | None = None
        self.adapter: BaseAdapter | None = None
        self.vsm: VirtualSiteMap | None = None
        self.overlay: VirtualBufferOverlay | None = None

        # Phase 5: Decoupled Incremental Engine (ADR-075)
        self.engine: IncrementalAnalysisEngine | None = None

    def send_message(self, message: dict[str, Any]) -> None:
        """Encode and send a JSON-RPC message to stdout."""
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
            "ascii"
        )
        self.stdout.write(header + body)
        self.stdout.flush()

    def send_error(self, request_id: int | str | None, code: int, message: str) -> None:
        """Send a JSON-RPC error response."""
        response: dict[str, Any] = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
        if request_id is not None:
            response["id"] = request_id
        self.send_message(response)

    def send_response(
        self,
        request_id: int | str,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        """Send a JSON-RPC response."""
        response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            response["error"] = error
        else:
            response["result"] = result
        self.send_message(response)

    def serve(self) -> None:
        """Run the main synchronous event loop with debounce multiplexing."""
        import io

        buffer = bytearray()

        while not self.exit_received:
            try:
                # 1. Process Debounced Dirty Documents
                self._flush_dirty_documents()

                # 2. Yield and wait for input
                try:
                    rlist, _, _ = select.select([self.stdin], [], [], 0.1)
                except (ValueError, OSError, io.UnsupportedOperation, AttributeError):
                    # Mock testing stream fallback
                    rlist = [self.stdin]

                if not rlist:
                    continue

                # 3. Fast non-blocking chunk ingestion
                try:
                    fd = self.stdin.fileno()
                    chunk = os.read(fd, 8192)
                except Exception:
                    chunk = self.stdin.read(8192)

                if not chunk:
                    self.exit_received = True
                    break

                buffer.extend(chunk)

                # 4. Extract and route fully buffered messages
                while True:
                    header_end = buffer.find(b"\r\n\r\n")
                    if header_end == -1:
                        break

                    header_data = buffer[:header_end]
                    content_length = 0
                    for line in header_data.split(b"\r\n"):
                        if b":" in line:
                            key, val = line.split(b":", 1)
                            if key.decode("ascii").strip().lower() == "content-length":
                                content_length = int(val.decode("ascii").strip())

                    msg_start = header_end + 4
                    if len(buffer) < msg_start + content_length:
                        break

                    body = buffer[msg_start : msg_start + content_length]
                    buffer = buffer[msg_start + content_length :]

                    try:
                        raw_msg = json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError as e:
                        self.send_error(None, -32700, f"Parse error: {e}")
                        continue

                    message = cast(JsonRpcMessage, raw_msg)
                    if message.get("jsonrpc") != "2.0":
                        self.send_error(
                            message.get("id"),
                            -32600,
                            "Invalid Request: missing or invalid jsonrpc version",
                        )
                        continue

                    self.handle_message(message)

            except Exception as e:
                sys.stderr.write(f"ZLS Error: {e}\n{traceback.format_exc()}\n")
                sys.stderr.flush()

        # Emit any remaining dirty documents on clean exit
        self._flush_dirty_documents(force=True)

    def _flush_dirty_documents(self, force: bool = False) -> None:
        """Collect expired dirty URIs and trigger incremental validation."""
        now = time.time()
        incremental_uris: set[str] = set()
        for uri, ts in list(self.dirty_documents.items()):
            if force or now - ts >= 0.3:
                incremental_uris.add(uri)
                del self.dirty_documents[uri]
        if incremental_uris:
            self._sync_workspace_and_publish(incremental_uris)

    def _build_vsm_sync(self) -> None:
        """Synchronously build the initial VSM and instantiate the engine."""
        if not self.repo_root:
            return

        if not self.config:
            self.config, _ = ZenzicConfig.load(self.repo_root)

        if not self.rule_engine:
            self.rule_engine = _build_rule_engine(self.config)

        docs_root = self.repo_root / self.config.docs_dir
        if not self.exclusion_mgr:
            self.exclusion_mgr = LayeredExclusionManager(
                self.config, repo_root=self.repo_root, docs_root=docs_root
            )

        md_contents: dict[Path, str] = {}
        for md_file in iter_markdown_sources(docs_root, self.config, self.exclusion_mgr):
            try:
                md_contents[md_file.resolve()] = md_file.read_text(encoding="utf-8")
            except OSError:
                continue

        # Register static asset files (HTML, images, etc.) present in docs_root into VSM
        if docs_root.is_dir():
            for file_path in walk_files(
                docs_root, set(self.config.excluded_dirs), self.exclusion_mgr, self.config
            ):
                if file_path.is_dir() or file_path.is_symlink() or file_path.suffix in DOC_SUFFIXES:
                    continue
                if self.exclusion_mgr.should_exclude_file(file_path, docs_root):
                    continue
                resolved_path = file_path.resolve()
                if resolved_path not in md_contents:
                    md_contents[resolved_path] = ""

        self.adapter = get_adapter(self.config.build_context, docs_root, self.repo_root)
        self.vsm = build_vsm(self.adapter, docs_root, md_contents, repo_root=self.repo_root)
        assert self.vsm is not None
        self.overlay = VirtualBufferOverlay(self.vsm)
        # Populate overlay with currently open documents
        for uri, text in self.documents.documents.items():
            self.overlay.update(uri, text)

        # Instantiate the decoupled incremental engine (ADR-075)
        assert self.rule_engine is not None
        self.engine = IncrementalAnalysisEngine(
            config=self.config,
            rule_engine=self.rule_engine,
            adapter=self.adapter,
            docs_root=docs_root,
            repo_root=self.repo_root,
        )
        self._flush_dirty_documents()

    def _is_supported_doc_uri(self, uri: str) -> bool:
        """Return True if the URI has a supported documentation file extension (DOC_SUFFIXES)."""
        if not uri:
            return False
        parsed = urlsplit(uri)
        path_str = unquote(parsed.path) if parsed.scheme else unquote(uri)
        return Path(path_str).suffix.lower() in DOC_SUFFIXES

    def _is_within_domain(self, uri: str) -> bool:
        """Return True if the URI is within the configured documentation domain and not excluded."""
        if not uri or self.repo_root is None:
            return True

        try:
            if not self.config:
                self.config, _ = ZenzicConfig.load(self.repo_root)

            docs_root = (self.repo_root / self.config.docs_dir).resolve()
            if not docs_root.is_dir():
                docs_root = self.repo_root.resolve()

            if not self.exclusion_mgr:
                self.exclusion_mgr = LayeredExclusionManager(
                    self.config, repo_root=self.repo_root, docs_root=docs_root
                )

            parsed = urlsplit(uri)
            path_str = unquote(parsed.path) if parsed.scheme else unquote(uri)
            path = Path(path_str).resolve()

            # Enforce LayeredExclusionManager (Layer 3 User Exclusions & Guardrails)
            if self.exclusion_mgr.should_exclude_file(path, docs_root):
                return False

            if path.is_relative_to(docs_root):
                return True

            if not self.adapter:
                self.adapter = get_adapter(self.config.build_context, docs_root, self.repo_root)

            if self.adapter:
                extra_roots = self.adapter.get_extra_content_roots(self.repo_root)
                for extra_root in extra_roots:
                    if path.is_relative_to(extra_root.resolve()):
                        return True
        except Exception:
            return False

        return False

    def _handle_file_changes(self, changes: list[dict[str, Any]]) -> None:
        """Incrementally update file caches and trigger revalidation."""
        if self.vsm is None or not self.adapter or not self.config:
            return

        assert isinstance(self.vsm, VirtualSiteMap)

        for change in changes:
            uri = change.get("uri", "")
            change_type = change.get("type")
            if (
                not uri.startswith("file://")
                or not self._is_supported_doc_uri(uri)
                or not self._is_within_domain(uri)
            ):
                continue
            from urllib.parse import unquote

            file_path = Path(unquote(uri[7:])).resolve()

            if change_type in (1, 2):  # Created or Changed
                try:
                    text = file_path.read_text(encoding="utf-8")
                    if self.engine is not None:
                        self.engine.update_file_cache(file_path, text)
                except OSError:
                    pass
            elif change_type == 3:  # Deleted
                if self.engine is not None:
                    self.engine.remove_file_cache(file_path)

            self.dirty_documents[uri] = 0.0

        for open_uri in self.documents.documents:
            self.dirty_documents[open_uri] = 0.0
        self._flush_dirty_documents()

    def handle_message(self, message: JsonRpcMessage) -> None:
        """Dispatch a single JSON-RPC message to the correct handler."""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        if not method:
            self.send_error(msg_id, -32600, "Invalid Request: missing method")
            return

        if method == "initialize":
            assert msg_id is not None
            root_uri = params.get("rootUri")
            if root_uri and root_uri.startswith("file://"):
                self.repo_root = Path(root_uri[7:])
            elif params.get("workspaceFolders"):
                first_ws = params["workspaceFolders"][0]
                if first_ws.get("uri", "").startswith("file://"):
                    self.repo_root = Path(first_ws["uri"][7:])

            self.send_response(
                msg_id,
                result={
                    "capabilities": {
                        "textDocumentSync": 2,  # Incremental sync (Zero-DBT Enforcement)
                        "hoverProvider": True,
                        "codeActionProvider": True,
                    },
                    "serverInfo": {"name": "Zenzic Language Server", "version": "0.21.0"},
                },
            )

            # Eagerly initialize configuration and engine on 'initialize'
            if self.repo_root and not self.config:
                self.config, _ = ZenzicConfig.load(self.repo_root)
                self.rule_engine = _build_rule_engine(self.config)

        elif method == "initialized":
            if self.repo_root:
                self.send_message(
                    {
                        "jsonrpc": "2.0",
                        "id": "watch-md",
                        "method": "client/registerCapability",
                        "params": {
                            "registrations": [
                                {
                                    "id": "watch-md",
                                    "method": "workspace/didChangeWatchedFiles",
                                    "registerOptions": {"watchers": [{"globPattern": "**/*.md"}]},
                                }
                            ]
                        },
                    }
                )
                self._build_vsm_sync()
                self._sync_workspace_and_publish()
        elif method == "workspace/didChangeWatchedFiles":
            self._handle_file_changes(params.get("changes", []))
        elif method == "shutdown":
            self.shutdown_received = True
            if msg_id is not None:
                self.send_response(msg_id, result=None)
        elif method == "exit":
            self.exit_received = True
            self.exit_code = 0 if self.shutdown_received else 1
        elif method == "textDocument/didOpen":
            uri = params.get("textDocument", {}).get("uri", "")
            if not self._is_supported_doc_uri(uri) or not self._is_within_domain(uri):
                return
            self.documents.did_open(params)
            if uri in self.documents.documents:
                if self.overlay:
                    self.overlay.update(uri, self.documents.documents[uri])
                self.dirty_documents[uri] = time.time()
        elif method == "textDocument/didChange":
            uri = params.get("textDocument", {}).get("uri", "")
            if not self._is_supported_doc_uri(uri) or not self._is_within_domain(uri):
                return
            self.documents.did_change(params)
            if uri in self.documents.documents:
                if self.overlay:
                    self.overlay.update(uri, self.documents.documents[uri])
                self.dirty_documents[uri] = time.time()
        elif method == "textDocument/hover":
            self._handle_hover(params, msg_id)
        elif method == "textDocument/codeAction":
            self._handle_code_action(params, msg_id)
        elif method == "textDocument/didClose":
            # Memory Hygiene: purge the document state entirely
            pass

    def _sync_workspace_and_publish(self, incremental_uris: set[str] | None = None) -> None:
        """Run validation incrementally via the decoupled engine.

        Delegates all analysis to ``IncrementalAnalysisEngine`` (ADR-075).
        The LSP server handles only JSON-RPC serialization and publishing.
        """
        repo_root = self.repo_root or Path("/")

        if not self.config:
            if self.repo_root:
                self.config, _ = ZenzicConfig.load(self.repo_root)
            else:
                self.config = ZenzicConfig()
        if not self.rule_engine:
            self.rule_engine = _build_rule_engine(self.config)

        docs_root = repo_root / self.config.docs_dir if self.repo_root else Path("/_zenzic_virtual")

        if not self.adapter:
            self.adapter = get_adapter(self.config.build_context, docs_root, repo_root)
            if self.vsm is None:
                self.vsm = VirtualSiteMap()

            assert isinstance(self.vsm, VirtualSiteMap)

            if self.overlay is None:
                self.overlay = VirtualBufferOverlay(self.vsm)
                for open_uri, open_text in self.documents.documents.items():
                    self.overlay.update(open_uri, open_text)

        assert isinstance(self.vsm, VirtualSiteMap)

        # Instantiate engine if needed (ADR-075: transport-agnostic analysis)
        if self.engine is None:
            assert self.rule_engine is not None
            self.engine = IncrementalAnalysisEngine(
                config=self.config,
                rule_engine=self.rule_engine,
                adapter=self.adapter,
                docs_root=docs_root,
                repo_root=repo_root,
            )

        # Delegate analysis to the engine
        assert self.overlay is not None
        results = self.engine.process_changes(self.vsm, self.overlay, incremental_uris)

        # Serialize at transport boundary and publish via JSON-RPC
        # to_lsp_dict() is the ONLY serialization site in the codebase
        for uri, typed_diags in results.items():
            self.send_message(
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/publishDiagnostics",
                    "params": {
                        "uri": uri,
                        "diagnostics": [d.to_lsp_dict() for d in typed_diags],
                    },
                }
            )

        # Calculate global DQS from VSM state and emit zenzic/dqsUpdate notification
        findings_counts: dict[str, int] = {}
        for route in self.vsm.values():
            for diag in route.diagnostics:
                findings_counts[diag.code] = findings_counts.get(diag.code, 0) + 1

        from zenzic.core.scorer import compute_score

        score_report = compute_score(findings_counts)

        self.send_message(
            {
                "jsonrpc": "2.0",
                "method": "zenzic/dqsUpdate",
                "params": {
                    "score": score_report.score,
                    "base_score": 100,
                    "penalties": 100 - score_report.score,
                },
            }
        )

    def _handle_hover(self, params: dict[str, Any], msg_id: int | str | None) -> None:
        if msg_id is None or self.vsm is None or not self.repo_root or not self.config:
            return

        assert isinstance(self.vsm, VirtualSiteMap)

        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        pos = params.get("position", {})
        line = pos.get("line", 0)
        char = pos.get("character", 0)

        docs_root = self.repo_root / self.config.docs_dir
        try:
            from urllib.parse import unquote

            rel = Path(unquote(uri[7:])).resolve().relative_to(docs_root.resolve()).as_posix()
        except ValueError:
            self.send_response(msg_id, result=None)
            return

        target_route = None
        for route in self.vsm.values():
            if route.source == rel:
                target_route = route
                break

        if not target_route:
            self.send_response(msg_id, result=None)
            return

        matched: ZenzicDiagnostic | None = None
        for d in target_route.diagnostics:
            s_line = d.range.start.line
            e_line = d.range.end.line
            if s_line <= line <= e_line:
                if s_line == line and char < d.range.start.character:
                    continue
                if e_line == line and char > d.range.end.character:
                    continue
                matched = d
                break

        if not matched:
            self.send_response(msg_id, result=None)
            return

        code = matched.code
        from zenzic.core.codes import CODE_DEFINITIONS, CODE_DESCRIPTIONS

        defn = CODE_DEFINITIONS.get(code)
        desc = CODE_DESCRIPTIONS.get(code, "No remediation guidance available.")

        contents: list[str] = []
        if defn:
            contents.append(
                f"**{code}** (Penalty: -{defn.penalty} pts, Category: {defn.category or 'ungraded'})"
            )
        else:
            contents.append(f"**{code}**")
        contents.append(desc)

        self.send_response(
            msg_id,
            result={"contents": {"kind": "markdown", "value": "\n\n".join(contents)}},
        )

    def _handle_code_action(self, params: dict[str, Any], msg_id: int | str | None) -> None:
        """Handle textDocument/codeAction JSON-RPC requests by generating CodeActions with WorkspaceEdit."""
        if msg_id is None:
            return

        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        context = params.get("context", {})
        diagnostics = context.get("diagnostics", [])

        if not uri or not diagnostics:
            self.send_response(msg_id, result=[])
            return

        content: str | None = None
        if uri in self.documents.documents:
            content = self.documents.documents[uri]
        elif uri.startswith("file://"):
            try:
                from urllib.parse import unquote

                content = Path(unquote(uri[7:])).resolve().read_text(encoding="utf-8")
            except OSError:
                content = None

        if content is None:
            self.send_response(msg_id, result=[])
            return

        import re

        from zenzic.core.codes import CODE_DEFINITIONS
        from zenzic.core.mutator import (
            DeadSuppressionMutation,
            EmptyLinkTextMutation,
            HtmlMissingHrefMutation,
            Mutation,
            Mutator,
        )
        from zenzic.core.parser import parse, serialize

        code_actions: list[dict[str, Any]] = []

        for diag in diagnostics:
            raw_code = diag.get("code")
            code = str(raw_code) if raw_code is not None else ""
            if not code and "message" in diag:
                m = re.search(r"\[(Z\d{3})\]", str(diag["message"]))
                if m:
                    code = m.group(1)

            defn = CODE_DEFINITIONS.get(code)
            if not defn or not getattr(defn, "fixable", False):
                continue

            mutations: list[Mutation] = []
            title_desc = ""

            if code == "Z121":
                mutations.append(HtmlMissingHrefMutation())
                title_desc = 'Inject placeholder href="#"'
            elif code == "Z603":
                line_no = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                mutations.append(DeadSuppressionMutation({line_no}))
                title_desc = "Remove dead inline suppression"
            elif code == "Z108":
                mutations.append(EmptyLinkTextMutation())
                title_desc = "Inject placeholder link text"
            else:
                continue

            try:
                ast = parse(content)
                mutator = Mutator(mutations)
                new_ast, changed = mutator.mutate(ast)
            except Exception:
                changed = False

            if changed:
                new_content = serialize(new_ast)
                lines = content.splitlines(keepends=True)
                total_lines = max(0, len(lines) - 1)
                last_line_len = len(lines[-1]) if lines else 0

                full_range = {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": total_lines, "character": last_line_len},
                }

                action = {
                    "title": f"Fix {code}: {title_desc}",
                    "kind": "quickfix",
                    "diagnostics": [diag],
                    "edit": {
                        "changes": {
                            uri: [
                                {
                                    "range": full_range,
                                    "newText": new_content,
                                }
                            ]
                        }
                    },
                }
                code_actions.append(action)

        self.send_response(msg_id, result=code_actions)
