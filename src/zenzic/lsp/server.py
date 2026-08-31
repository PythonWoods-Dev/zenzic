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
from urllib.parse import urlsplit
from urllib.request import url2pathname

from zenzic import __version__
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


def uri_to_path(uri: str) -> Path:
    """Convert a file:// URI to a cross-platform pathlib.Path."""
    parsed = urlsplit(uri)
    return Path(url2pathname(parsed.path))


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
        self._full_sync_pending: bool = False

        # Phase 4: VSM Integration
        self.repo_root: Path | None = None
        self.adapter: BaseAdapter | None = None
        self.vsm: VirtualSiteMap | None = None
        self.overlay: VirtualBufferOverlay | None = None

        # Phase 5: Decoupled Incremental Engine (ADR-075)
        self.engine: IncrementalAnalysisEngine | None = None

        # Diagnostics tracking to prevent ghost diagnostics on file deletion
        self.file_diagnostics: set[str] = set()

        # Auto-fix-on-save (textDocument/willSaveWaitUntil) -- off by default,
        # user opt-in via the zenzic.autoFixOnSave client setting.
        self.auto_fix_on_save: bool = False

        # Auto-repair inbound links on rename (workspace/willRenameFiles) --
        # off by default, user opt-in via zenzic.autoRepairLinksOnRename.
        self.auto_repair_links_on_rename: bool = False

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
        if self._full_sync_pending:
            if force or (not self.dirty_documents):
                self._full_sync_pending = False
                self.dirty_documents.clear()
                self._sync_workspace_and_publish(None)
                return
        if incremental_uris:
            self._sync_workspace_and_publish(incremental_uris)

    def _resolve_docs_root(self) -> Path:
        """Resolve docs_root with fallback to repo_root when docs/ doesn't exist.

        Single Source of Truth for docs_root resolution across all LSP server
        operations.  The fallback only triggers when the configured ``docs_dir``
        does not exist on disk — an LSP-specific convenience for unconfigured
        workspaces.
        """
        if self.repo_root is None or self.config is None:
            raise RuntimeError("LSP server not initialized: repo_root or config is None")
        docs_root = (self.repo_root / self.config.docs_dir).resolve()
        if not docs_root.is_dir():
            docs_root = self.repo_root.resolve()
        return docs_root

    def _build_vsm_sync(self) -> None:
        """Synchronously build the initial VSM and instantiate the engine."""
        if not self.repo_root:
            return

        if not self.config:
            self.config, _ = ZenzicConfig.load(self.repo_root)

        if not self.rule_engine:
            self.rule_engine = _build_rule_engine(self.config)

        docs_root = self._resolve_docs_root()
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

        static_assets: set[Path] = set()
        if docs_root.is_dir():
            for file_path in walk_files(
                docs_root, set(self.config.excluded_dirs), self.exclusion_mgr, self.config
            ):
                if file_path.is_dir() or file_path.is_symlink() or file_path.suffix in DOC_SUFFIXES:
                    continue
                if self.exclusion_mgr.should_exclude_file(file_path, docs_root):
                    continue
                static_assets.add(file_path.resolve())

        self.adapter = get_adapter(self.config.build_context, docs_root, self.repo_root)
        self.vsm = build_vsm(
            self.adapter,
            docs_root,
            md_contents,
            repo_root=self.repo_root,
            static_assets=static_assets,
        )
        self.overlay = VirtualBufferOverlay(self.vsm)
        # Populate overlay with currently open documents
        for uri, text in self.documents.documents.items():
            self.overlay.update(uri, text)

        # Instantiate the decoupled incremental engine (ADR-075)
        if self.rule_engine is not None:
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
        return uri_to_path(uri).suffix.lower() in DOC_SUFFIXES

    def _is_within_domain(self, uri: str) -> bool:
        """Return True if the URI is within the configured documentation domain and not excluded."""
        if not uri or self.repo_root is None:
            return True

        if self._is_config_file_change(uri):
            return True

        try:
            if not self.config:
                self.config, _ = ZenzicConfig.load(self.repo_root)

            docs_root = self._resolve_docs_root()

            if not self.exclusion_mgr:
                self.exclusion_mgr = LayeredExclusionManager(
                    self.config, repo_root=self.repo_root, docs_root=docs_root
                )

            path = uri_to_path(uri).resolve()

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

    def _is_config_file_change(self, uri: str) -> bool:
        """Return True if *uri* corresponds to a watched Zenzic or Adapter configuration file."""
        if not uri or not uri.startswith("file://"):
            return False
        try:
            file_path = uri_to_path(uri)
            filename = file_path.name
        except Exception:
            return False

        if filename in (".zenzic.toml", ".zenzic.local.toml", "pyproject.toml"):
            return True
        if self.adapter and filename in self.adapter.watched_config_files:
            return True
        return False

    def _handle_file_changes(self, changes: list[dict[str, Any]]) -> None:
        """Incrementally update file caches and trigger revalidation, hot-reloading config on changes."""
        # Directory-event fallback (ADR-075 / Mirror Law):
        # When VS Code emits a watched-files event whose URI points to a
        # directory (no recognised doc extension), it signals a structural
        # filesystem change — typically a directory move, rename, or bulk
        # creation.  The server must NOT attempt to traverse the filesystem or
        # inspect engine internals to synthesise per-file events (separation of
        # concerns).  Instead, we delegate to a full workspace sync, which
        # instructs the Core Engine to rebuild the VSM from scratch.  The engine
        # will then emit empty-diagnostic arrays for any previously-active URIs
        # that have disappeared from the VSM, satisfying LSP-FIX-017.
        from zenzic.core.discovery import DOC_SUFFIXES

        for change in changes:
            uri = change.get("uri", "")
            if not uri.startswith("file://"):
                continue
            try:
                path = uri_to_path(uri)
            except (ValueError, OSError):
                continue
            if path.suffix.lower() not in DOC_SUFFIXES and not self._is_config_file_change(uri):
                # This URI has no recognised doc extension — treat as a
                # directory-level event and flag for a debounced full workspace sync.
                if change.get("type") == 3:  # Directory deleted
                    prefix = uri.rstrip("/") + "/"

                    # ── LSP-FIX-019: Fast Ghost Clearing ─────────────────────
                    # Emit publishDiagnostics [] for every active-diagnostic URI
                    # that falls under the deleted directory — **before** setting
                    # _full_sync_pending.  This clears the PROBLEMS panel
                    # instantaneously (O(A), A = |file_diagnostics|), independently
                    # of how long the subsequent Full Sync takes.
                    # Constraint: must not block the event loop (no filesystem I/O).
                    for ghost_uri in list(self.file_diagnostics):
                        if ghost_uri == uri or ghost_uri.startswith(prefix):
                            self.send_message(
                                {
                                    "jsonrpc": "2.0",
                                    "method": "textDocument/publishDiagnostics",
                                    "params": {"uri": ghost_uri, "diagnostics": []},
                                }
                            )
                            self.file_diagnostics.discard(ghost_uri)
                            # Keep engine's set in sync to avoid redundant
                            # ghost-clearing passes during the subsequent full sync.
                            if self.engine is not None:
                                self.engine._uris_with_active_diagnostics.discard(ghost_uri)

                    # ── Cache eviction ────────────────────────────────────────
                    # Remove child URIs from overlay and document manager so the
                    # engine does not re-analyse stale in-memory content during
                    # the full sync that follows.
                    if self.overlay:
                        for buf_uri in list(self.overlay.buffers.keys()):
                            if buf_uri == uri or buf_uri.startswith(prefix):
                                self.overlay.remove(buf_uri)
                    for doc_uri in list(self.documents.documents.keys()):
                        if doc_uri == uri or doc_uri.startswith(prefix):
                            self.documents.documents.pop(doc_uri, None)
                            self.dirty_documents.pop(doc_uri, None)

                self._full_sync_pending = True
                self.dirty_documents[uri] = time.time()
                continue

        # Hot-reload configuration if any watched config file changed
        if any(self._is_config_file_change(change.get("uri", "")) for change in changes):
            from zenzic.core.adapters._factory import clear_adapter_cache

            clear_adapter_cache()
            if self.repo_root:
                self.config, _ = ZenzicConfig.load(self.repo_root)
            else:
                self.config = ZenzicConfig()
            self.exclusion_mgr = None
            self.adapter = None
            self.engine = None
            self.vsm = None
            self._build_vsm_sync()
            self._sync_workspace_and_publish()
            return

        if self.vsm is None or not self.adapter or not self.config:
            return

        for change in changes:
            uri = change.get("uri", "")
            change_type = change.get("type")

            if not (
                self._is_supported_doc_uri(uri) or self._is_config_file_change(uri)
            ) or not self._is_within_domain(uri):
                continue

            file_path = uri_to_path(uri).resolve()

            if change_type in (1, 2):  # Created or Changed
                try:
                    text = file_path.read_text(encoding="utf-8")
                    if self.overlay and uri in self.documents.documents:
                        self.overlay.update(uri, text)
                    if self.engine is not None:
                        self.engine.update_file_cache(file_path, text)
                except OSError:
                    pass
            elif change_type == 3:  # Deleted
                if self.overlay:
                    self.overlay.remove(uri)
                if self.engine is not None:
                    self.engine.remove_file_cache(file_path)
                # State Hygiene (LSP-FIX-015): evict the deleted URI from all
                # in-memory caches so it is never re-scheduled for analysis.
                self.documents.documents.pop(uri, None)
                self.dirty_documents.pop(uri, None)
                # LSP contract: an empty diagnostics array clears stale entries
                # from the editor's PROBLEMS panel immediately. Without this,
                # VS Code retains ghost diagnostics until the next full scan.
                self.send_message(
                    {
                        "jsonrpc": "2.0",
                        "method": "textDocument/publishDiagnostics",
                        "params": {"uri": uri, "diagnostics": []},
                    }
                )
                self.file_diagnostics.discard(uri)
                continue  # Deleted files must NOT be re-added to dirty_documents

            self.dirty_documents[uri] = time.time()

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
            if msg_id is None:
                return
            root_uri = params.get("rootUri")
            if root_uri and root_uri.startswith("file://"):
                self.repo_root = uri_to_path(root_uri)
            elif params.get("workspaceFolders"):
                first_ws = params["workspaceFolders"][0]
                if first_ws.get("uri", "").startswith("file://"):
                    self.repo_root = uri_to_path(first_ws["uri"])

            init_options = params.get("initializationOptions") or {}
            if isinstance(init_options, dict) and "autoFixOnSave" in init_options:
                self.auto_fix_on_save = bool(init_options["autoFixOnSave"])
            if isinstance(init_options, dict) and "autoRepairLinksOnRename" in init_options:
                self.auto_repair_links_on_rename = bool(init_options["autoRepairLinksOnRename"])

            self.send_response(
                msg_id,
                result={
                    "capabilities": {
                        # Object form (not the bare TextDocumentSyncKind int) is
                        # required to additionally declare willSaveWaitUntil --
                        # vscode-languageclient only auto-forwards
                        # workspace.onWillSaveTextDocument to the server when this
                        # is true (textSynchronization.js checks
                        # textDocumentSyncOptions.willSaveWaitUntil).
                        "textDocumentSync": {
                            "openClose": True,
                            "change": 2,  # Incremental sync (Zero-DBT Enforcement)
                            "willSaveWaitUntil": True,
                        },
                        "hoverProvider": True,
                        "codeActionProvider": True,
                        # workspace/willRenameFiles: vscode-languageclient only
                        # auto-forwards vscode.workspace.onWillRenameFiles when
                        # this filter is declared (fileOperations.js).
                        "workspace": {
                            "fileOperations": {
                                "willRename": {
                                    "filters": [
                                        {
                                            "scheme": "file",
                                            "pattern": {"glob": "**/*.{md,mdx,markdown}"},
                                        }
                                    ]
                                }
                            }
                        },
                    },
                    "serverInfo": {"name": "Zenzic Language Server", "version": __version__},
                },
            )

            # Eagerly initialize configuration and engine on 'initialize'
            if self.repo_root and not self.config:
                self.config, _ = ZenzicConfig.load(self.repo_root)
                self.rule_engine = _build_rule_engine(self.config)

        elif method == "initialized":
            if self.repo_root:
                self._build_vsm_sync()
                watchers: list[dict[str, str]] = [
                    # File-level watchers: individual .md/.mdx changes
                    {"globPattern": "**/*.md"},
                    {"globPattern": "**/*.mdx"},
                    # Directory-level watcher (LSP-FIX-018): catches folder
                    # creation, rename, and deletion events that VS Code does
                    # NOT surface via the file-only patterns above.
                    # Without this, deleting a folder leaves ghost diagnostics
                    # in the editor's PROBLEMS panel.
                    {"globPattern": "**/"},
                    {"globPattern": "**/.zenzic.toml"},
                    {"globPattern": "**/.zenzic.local.toml"},
                ]
                if self.adapter:
                    for cfg_file in self.adapter.watched_config_files:
                        watchers.append({"globPattern": f"**/{cfg_file}"})

                self.send_message(
                    {
                        "jsonrpc": "2.0",
                        "id": "watch-files",
                        "method": "client/registerCapability",
                        "params": {
                            "registrations": [
                                {
                                    "id": "watch-files",
                                    "method": "workspace/didChangeWatchedFiles",
                                    "registerOptions": {"watchers": watchers},
                                }
                            ]
                        },
                    }
                )
                self._sync_workspace_and_publish()
                # Emit core version to VS Code Output panel (LSP-INFO-001).
                # This is the canonical way to verify which core binary is active
                # without leaving the editor. Visible via Output → Zenzic Language Server.
                self.send_message(
                    {
                        "jsonrpc": "2.0",
                        "method": "window/logMessage",
                        "params": {
                            "type": 3,  # Info
                            "message": (
                                f"Zenzic Language Server v{__version__} started. "
                                f"Core binary: {sys.executable}"
                            ),
                        },
                    }
                )

        elif method == "workspace/didChangeWatchedFiles":
            changes = params.get("changes", [])
            self._handle_file_changes(changes)

        elif method == "workspace/didChangeConfiguration":
            settings = params.get("settings") or {}
            zenzic_settings = settings.get("zenzic") if isinstance(settings, dict) else None
            if isinstance(zenzic_settings, dict) and "autoFixOnSave" in zenzic_settings:
                self.auto_fix_on_save = bool(zenzic_settings["autoFixOnSave"])
            if isinstance(zenzic_settings, dict) and "autoRepairLinksOnRename" in zenzic_settings:
                self.auto_repair_links_on_rename = bool(zenzic_settings["autoRepairLinksOnRename"])

        elif method == "shutdown":
            self.shutdown_received = True
            if msg_id is not None:
                self.send_response(msg_id, result=None)
        elif method == "exit":
            self.exit_received = True
            self.exit_code = 0 if self.shutdown_received else 1
        elif method == "textDocument/didOpen":
            uri = params.get("textDocument", {}).get("uri", "")
            if not (
                self._is_supported_doc_uri(uri) or self._is_config_file_change(uri)
            ) or not self._is_within_domain(uri):
                return
            self.documents.did_open(params)
            if uri in self.documents.documents:
                if self.overlay:
                    self.overlay.update(uri, self.documents.documents[uri])
                self.dirty_documents[uri] = 0.0
        elif method == "textDocument/didChange":
            uri = params.get("textDocument", {}).get("uri", "")
            if not (
                self._is_supported_doc_uri(uri) or self._is_config_file_change(uri)
            ) or not self._is_within_domain(uri):
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
        elif method == "textDocument/willSaveWaitUntil":
            self._handle_will_save_wait_until(params, msg_id)
        elif method == "workspace/willRenameFiles":
            self._handle_will_rename_files(params, msg_id)
        elif method == "textDocument/didClose":
            uri = params.get("textDocument", {}).get("uri", "")
            self.documents.did_close(params)
            self.dirty_documents.pop(uri, None)
            if self.overlay:
                self.overlay.remove(uri)

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

        docs_root = self._resolve_docs_root() if self.repo_root else Path("/_zenzic_virtual")

        if not self.exclusion_mgr and self.repo_root:
            self.exclusion_mgr = LayeredExclusionManager(
                self.config, repo_root=self.repo_root, docs_root=docs_root
            )

        if not self.adapter:
            self.adapter = get_adapter(self.config.build_context, docs_root, repo_root)

        if self.vsm is None:
            self.vsm = VirtualSiteMap()

        if self.overlay is None:
            self.overlay = VirtualBufferOverlay(self.vsm)
            for open_uri, open_text in self.documents.documents.items():
                self.overlay.update(open_uri, open_text)

        # Instantiate engine if needed (ADR-075: transport-agnostic analysis)
        if self.rule_engine is None:
            return
        is_full_rebuild = self.engine is None
        if self.engine is None:
            self.engine = IncrementalAnalysisEngine(
                config=self.config,
                rule_engine=self.rule_engine,
                adapter=self.adapter,
                docs_root=docs_root,
                repo_root=repo_root,
            )

        # Delegate analysis to the engine
        if self.overlay is None:
            return
        results = self.engine.process_changes(self.vsm, self.overlay, incremental_uris)

        # Serialize at transport boundary and publish via JSON-RPC
        # to_lsp_dict() is the ONLY serialization site in the codebase
        for uri, typed_diags in results.items():
            # file_diagnostics tracks URIs with *active* (non-empty) diagnostics.
            # Discard when the list is empty so ghost-clearing broadcasts are not
            # double-emitted on the next full rebuild (LSP-FIX-017 correctness).
            if typed_diags:
                self.file_diagnostics.add(uri)
            else:
                self.file_diagnostics.discard(uri)
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

        # State Hygiene (LSP-FIX-017): Clear ghost diagnostics for files that no longer exist.
        # If a file was deleted or its route removed, process_changes won't return it in results,
        # so we must actively detect missing URIs and broadcast an empty diagnostics array.
        # PERF: Only run this on full topology rebuilds to avoid O(N) resolve() calls during incremental typing.
        if is_full_rebuild and self.engine is not None:
            dead_uris = []
            for uri in list(self.file_diagnostics):
                path = uri_to_path(uri).resolve()
                if path not in self.engine.md_contents_cache:
                    self.send_message(
                        {
                            "jsonrpc": "2.0",
                            "method": "textDocument/publishDiagnostics",
                            "params": {"uri": uri, "diagnostics": []},
                        }
                    )
                    dead_uris.append(uri)
            for dead_uri in dead_uris:
                self.file_diagnostics.remove(dead_uri)

        # DQS emission intentionally removed (LSP-FIX-014).
        # The LSP operates in incremental mode and only sees topological findings
        # (Z1xx/Z4xx). Content findings (Z5xx) on closed files are never analysed,
        # so any DQS computed here would be non-deterministically lower than the
        # CLI batch score. Emitting a misleading score violates the Determinism
        # invariant. The authoritative DQS is produced exclusively by the CLI
        # (`zenzic check all --strict`) in CI/CD batch mode.

    def _handle_hover(self, params: dict[str, Any], msg_id: int | str | None) -> None:
        if msg_id is None or self.vsm is None or not self.repo_root or not self.config:
            return

        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        pos = params.get("position", {})
        line = pos.get("line", 0)
        char = pos.get("character", 0)

        docs_root = self._resolve_docs_root()
        try:
            rel = uri_to_path(uri).resolve().relative_to(docs_root.resolve()).as_posix()
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
            # No active diagnostic here. A suppression directive on this line is
            # the likely reason there is nothing to report, and explaining that is
            # more useful than an empty hover — it is the only way to see, without
            # editing the file, whether a `zenzic:ignore` comment is doing anything.
            suppression_md = self._explain_suppression_at(uri, line)
            self.send_response(
                msg_id,
                result=(
                    {"contents": {"kind": "markdown", "value": suppression_md}}
                    if suppression_md
                    else None
                ),
            )
            return

        code = matched.code
        from zenzic.core.codes import (
            CODE_DEFINITIONS,
            CODE_DESCRIPTIONS,
            NON_INLINE_SUPPRESSIBLE_CODES,
            NON_SUPPRESSIBLE_CODES,
        )

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

        # The finding is live, so say why an inline comment would not silence it.
        # Reaching for one is the natural next move after reading a diagnostic, and
        # for these two families it is the wrong move.
        if code in NON_SUPPRESSIBLE_CODES:
            contents.append(
                "🔒 **Not suppressible.** This is a Tier-0 security code — no inline "
                "comment or configuration can silence it."
            )
        elif code in NON_INLINE_SUPPRESSIBLE_CODES:
            contents.append(
                "⚙️ **Not suppressible inline** (ADR-093). Govern this code through "
                "`.zenzic.toml`'s `directory_policies` or `per_file_ignores`; an inline "
                "comment here would be reported as a dead suppression (`Z603`)."
            )

        self.send_response(
            msg_id,
            result={"contents": {"kind": "markdown", "value": "\n\n".join(contents)}},
        )

    def _explain_suppression_at(self, uri: str, line: int) -> str | None:
        """Markdown explaining any suppression directive on *line*, else ``None``.

        Read-only by construction: it asks :meth:`SuppressionTracker.explain_suppression`,
        never ``is_suppressed``. The latter consumes the directive it matches, so a
        hover built on it would silently erase the ``Z603`` dead-suppression finding
        for the very comment the user is pointing at.
        """
        text = self.documents.documents.get(uri)
        if text is None:
            return None

        from zenzic.core.suppressions import SuppressionTracker

        line_no = line + 1  # LSP positions are 0-based; directives are 1-based.
        try:
            tracker = SuppressionTracker(uri_to_path(uri), text)
        except Exception:
            return None

        directive = next((d for d in tracker.directives if d.line_no == line_no), None)
        if directive is None:
            return None

        code = directive.code
        if code == "DATA-ZENZIC-IGNORE":
            return (
                "**Suppression directive** — `data-zenzic-ignore`\n\n"
                "Silences HTML hygiene findings (`Z12x`) on this element."
            )

        verdict = tracker.explain_suppression(line_no, code)
        header = f"**Suppression directive** — `{code}`"

        if verdict.source == "non-suppressible":
            body = (
                f"🔒 **Has no effect.** `{code}` is a Tier-0 security code and cannot be "
                "suppressed by any mechanism. This comment is reported as `Z603`."
            )
        elif verdict.source == "non-inline-suppressible":
            body = (
                f"⚙️ **Has no effect** (ADR-093). `{code}` is governed only through "
                "`.zenzic.toml` — `directory_policies` or `per_file_ignores` — never by an "
                "inline comment. This comment is reported as `Z603`."
            )
        elif verdict.source == "directory-policy":
            body = (
                f"↩️ **Redundant.** `{code}` is already covered for this file by the "
                f"`directory_policies` pattern `{verdict.pattern}` in `.zenzic.toml`, so this "
                "comment adds nothing and is reported as `Z603`."
            )
        elif verdict.source == "force-audit":
            body = (
                "🔍 **Ignored for this run.** `--audit` mode is active, which deliberately "
                "reports every finding regardless of suppression."
            )
        elif verdict.source == "inline":
            body = f"✅ **Active.** Suppresses `{code}` findings on this line."
        else:
            body = (
                f"⚠️ **Nothing to suppress.** No `{code}` finding occurs on this line, so this "
                "comment is reported as a dead suppression (`Z603`). Remove it."
            )

        return f"{header}\n\n{body}"

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
                content = uri_to_path(uri).resolve().read_text(encoding="utf-8")
            except OSError:
                content = None

        if content is None:
            self.send_response(msg_id, result=[])
            return

        from zenzic.core import regex as re
        from zenzic.core.codes import (
            CODE_DEFINITIONS,
            NON_INLINE_SUPPRESSIBLE_CODES,
            NON_SUPPRESSIBLE_CODES,
        )
        from zenzic.core.mutator import (
            BareUrlMutation,
            DeadSuppressionMutation,
            EmptyLinkTextMutation,
            HeadingPunctuationMutation,
            MalformedListMutation,
            Mutation,
            Mutator,
            UntaggedCodeBlockMutation,
        )
        from zenzic.core.parser import parse, serialize

        code_actions: list[dict[str, Any]] = []

        for diag in diagnostics:
            raw_code = diag.get("code")
            diag_code = str(raw_code) if raw_code is not None else ""
            if not diag_code and "message" in diag:
                m = re.search(r"\[(Z\d{3})\]", str(diag["message"]))
                if m:
                    diag_code = m.group(1)

            defn = CODE_DEFINITIONS.get(diag_code)
            if defn and getattr(defn, "fixable", False):
                mutations: list[Mutation] = []
                title = ""

                if diag_code == "Z108":
                    mutations.append(EmptyLinkTextMutation())
                    title = "Fix Z108: Inject placeholder link text ('TODO')"
                elif diag_code == "Z505":
                    mutations.append(UntaggedCodeBlockMutation())
                    title = "Fix Z505: Inject language specifier ('text')"
                elif diag_code == "Z603":
                    line_no = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                    mutations.append(DeadSuppressionMutation({line_no}))
                    title = "Fix Z603: Remove dead inline suppression"
                elif diag_code == "Z515":
                    mutations.append(BareUrlMutation())
                    title = "Fix Z515: Wrap bare URL in angle brackets"
                elif diag_code == "Z517":
                    mutations.append(HeadingPunctuationMutation())
                    title = "Fix Z517: Strip trailing heading punctuation"
                elif diag_code == "Z520":
                    mutations.append(MalformedListMutation())
                    title = "Fix Z520: Convert to a valid Markdown list"

                if mutations:
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
                            "title": title,
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

            if diag_code and diag_code in NON_INLINE_SUPPRESSIBLE_CODES:
                suppress_action = {
                    "title": f"Suppress {diag_code} (configure via .zenzic.toml)",
                    "kind": "quickfix",
                    "diagnostics": [diag],
                    "disabled": {
                        "reason": (
                            f"{diag_code} is a topological finding. "
                            "Configure suppression in .zenzic.toml via [directory_policies] or [per_file_ignores]."
                        )
                    },
                }
                code_actions.append(suppress_action)
            elif diag_code and diag_code not in NON_SUPPRESSIBLE_CODES:
                insert_line = max(0, diag.get("range", {}).get("start", {}).get("line", 0))
                # Use a large character index to append to the end of the line
                insert_char = 9999

                suppress_action = {
                    "title": f"Suppress {diag_code} for this line",
                    "kind": "quickfix",
                    "diagnostics": [diag],
                    "edit": {
                        "changes": {
                            uri: [
                                {
                                    "range": {
                                        "start": {"line": insert_line, "character": insert_char},
                                        "end": {"line": insert_line, "character": insert_char},
                                    },
                                    "newText": f" <!-- zenzic:ignore:{diag_code} -->",
                                }
                            ]
                        }
                    },
                }
                code_actions.append(suppress_action)

        self.send_response(msg_id, result=code_actions)

    def _handle_will_save_wait_until(
        self, params: dict[str, Any], msg_id: int | str | None
    ) -> None:
        """Handle textDocument/willSaveWaitUntil: auto-fix-on-save.

        Reuses the exact same Mutation classes as manual Quick Fix
        (:meth:`_handle_code_action`) and ``zenzic fix`` -- no new fix logic,
        only a new trigger.  Off unless ``self.auto_fix_on_save`` is True
        (client opt-in via the ``zenzic.autoFixOnSave`` setting).

        Safety gate: a fixable code is skipped entirely for this save if ANY
        occurrence of that code anywhere in the file is inline-suppressed --
        the Mutation classes have no per-occurrence location scoping (only
        DeadSuppressionMutation does), so partial suppression cannot be
        respected surgically; skipping the whole code is the fail-safe choice
        over silently "fixing" a suppressed occurrence against user intent.
        """
        if msg_id is None:
            return
        if not self.auto_fix_on_save:
            self.send_response(msg_id, result=[])
            return

        uri = params.get("textDocument", {}).get("uri", "")
        content = self.documents.documents.get(uri)
        if content is None or not uri.startswith("file://") or self.config is None:
            self.send_response(msg_id, result=[])
            return

        from zenzic.core.codes import CODE_DEFINITIONS
        from zenzic.core.mutator import (
            BareUrlMutation,
            EmptyLinkTextMutation,
            HeadingPunctuationMutation,
            MalformedListMutation,
            Mutation,
            Mutator,
            UntaggedCodeBlockMutation,
        )
        from zenzic.core.parser import parse, serialize
        from zenzic.core.scanner import _scan_single_file

        path = uri_to_path(uri)
        try:
            report, _ = _scan_single_file(
                path, self.config, rule_engine=self.rule_engine, text=content
            )
        except Exception:
            # Fail-safe: an unexpected scan error must never silently corrupt
            # the file -- skip this save cycle's auto-fix entirely.
            self.send_response(msg_id, result=[])
            return

        suppressed_codes: set[str] = set()
        if report.suppression_tracker is not None:
            suppressed_codes = {d.code for d in report.suppression_tracker.directives if d.consumed}

        active_fixable_codes = {
            f.rule_id
            for f in report.rule_findings
            if (defn := CODE_DEFINITIONS.get(f.rule_id)) and getattr(defn, "fixable", False)
        }
        codes_to_fix = active_fixable_codes - suppressed_codes

        mutation_factory: dict[str, type] = {
            "Z108": EmptyLinkTextMutation,
            "Z505": UntaggedCodeBlockMutation,
            "Z515": BareUrlMutation,
            "Z517": HeadingPunctuationMutation,
            "Z520": MalformedListMutation,
            # Z603 (DeadSuppressionMutation) deliberately excluded: it needs
            # specific dead-suppression line numbers as constructor state,
            # which is exactly the kind of new fix-selection logic this
            # trigger must not invent; dead suppressions stay reachable via
            # the existing per-diagnostic Quick Fix and `zenzic fix`.
        }
        mutations: list[Mutation] = [
            mutation_factory[code]() for code in codes_to_fix if code in mutation_factory
        ]

        if not mutations:
            self.send_response(msg_id, result=[])
            return

        try:
            ast = parse(content)
            mutator = Mutator(mutations)
            new_ast, changed = mutator.mutate(ast)
        except Exception:
            # Ambiguous/failed mutation: skip and notify via the log, never guess.
            self.send_message(
                {
                    "jsonrpc": "2.0",
                    "method": "window/logMessage",
                    "params": {
                        "type": 2,  # Warning
                        "message": f"Zenzic auto-fix-on-save: mutation failed for {uri}, skipped.",
                    },
                }
            )
            self.send_response(msg_id, result=[])
            return

        if not changed:
            self.send_response(msg_id, result=[])
            return

        new_content = serialize(new_ast)
        lines = content.splitlines(keepends=True)
        total_lines = max(0, len(lines) - 1)
        last_line_len = len(lines[-1]) if lines else 0
        full_range = {
            "start": {"line": 0, "character": 0},
            "end": {"line": total_lines, "character": last_line_len},
        }
        self.send_response(msg_id, result=[{"range": full_range, "newText": new_content}])

    def _handle_will_rename_files(self, params: dict[str, Any], msg_id: int | str | None) -> None:
        """Handle workspace/willRenameFiles: auto-repair inbound links.

        Reuses ``resolve_href_target`` (unchanged) via
        :class:`~zenzic.core.mutator.RenameLinkMutation` to find and rewrite
        relative links pointing at each renamed file's OLD path -- no new
        link-resolution logic, only new fix-application logic matching the
        codebase's existing Mutation pattern.

        Scope is bounded by the VSM's existing ``incoming_links`` reverse
        index (canonical URL -> set of linking file paths) -- an O(1) lookup
        per rename, not a workspace-wide scan.

        Off unless ``self.auto_repair_links_on_rename`` is True.  Skips (does
        not guess) when: the renamed file isn't a tracked Markdown/MDX
        document, it has no VSM entry, a linking file is excluded via
        ``.zenzic.toml``, or a link uses an alias href style
        (``RenameLinkMutation`` itself declines those).
        """
        if msg_id is None:
            return
        if not self.auto_repair_links_on_rename:
            self.send_response(msg_id, result=None)
            return
        if self.vsm is None or self.config is None or self.repo_root is None:
            self.send_response(msg_id, result=None)
            return

        from zenzic.core.discovery import DOC_SUFFIXES
        from zenzic.core.mutator import Mutator, RenameLinkMutation
        from zenzic.core.parser import parse, serialize

        docs_root = self._resolve_docs_root()
        docs_root_str = str(docs_root)
        repo_root_str = str(self.repo_root)

        changes: dict[str, list[dict[str, Any]]] = {}
        skipped_files: list[str] = []

        for file_op in params.get("files", []):
            old_uri = file_op.get("oldUri", "")
            new_uri = file_op.get("newUri", "")
            if not old_uri.startswith("file://") or not new_uri.startswith("file://"):
                continue
            try:
                old_path = uri_to_path(old_uri)
                new_path = uri_to_path(new_uri)
            except Exception:  # noqa: S112 -- malformed URI, skip this pair silently
                continue
            if old_path.suffix.lower() not in DOC_SUFFIXES:
                continue

            try:
                old_rel_posix = old_path.resolve().relative_to(docs_root.resolve()).as_posix()
            except ValueError:
                continue  # renamed file is outside docs_root -- not VSM-tracked

            canonical_url = next(
                (url for url, route in self.vsm.items() if route.source == old_rel_posix), None
            )
            if canonical_url is None:
                continue  # not in the VSM (excluded, or VSM stale) -- skip, don't guess

            linking_files = self.vsm.incoming_links.get(canonical_url, set())
            old_abs = str(old_path.resolve())
            new_abs = str(new_path.resolve())

            for linking_path in linking_files:
                if self.exclusion_mgr is not None and self.exclusion_mgr.should_exclude_file(
                    linking_path, docs_root
                ):
                    skipped_files.append(str(linking_path))
                    continue

                linking_uri = linking_path.resolve().as_uri()
                content = self.documents.documents.get(linking_uri)
                if content is None:
                    try:
                        content = linking_path.read_text(encoding="utf-8")
                    except OSError:
                        skipped_files.append(str(linking_path))
                        continue

                try:
                    mutation = RenameLinkMutation(
                        source_file=linking_path,
                        docs_root_str=docs_root_str,
                        repo_root_str=repo_root_str,
                        old_abs=old_abs,
                        new_abs=new_abs,
                    )
                    ast = parse(content)
                    new_ast, changed = Mutator([mutation]).mutate(ast)
                except Exception:
                    skipped_files.append(str(linking_path))
                    continue

                if not changed:
                    continue

                new_content = serialize(new_ast)
                lines = content.splitlines(keepends=True)
                total_lines = max(0, len(lines) - 1)
                last_line_len = len(lines[-1]) if lines else 0
                changes[linking_uri] = [
                    {
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": total_lines, "character": last_line_len},
                        },
                        "newText": new_content,
                    }
                ]

        if skipped_files:
            self.send_message(
                {
                    "jsonrpc": "2.0",
                    "method": "window/logMessage",
                    "params": {
                        "type": 2,  # Warning
                        "message": (
                            "Zenzic auto-repair-on-rename: skipped "
                            f"{len(skipped_files)} file(s) (excluded, unreadable, "
                            f"or mutation error): {', '.join(skipped_files)}"
                        ),
                    },
                }
            )

        if not changes:
            self.send_response(msg_id, result=None)
            return

        self.send_response(msg_id, result={"changes": changes})
