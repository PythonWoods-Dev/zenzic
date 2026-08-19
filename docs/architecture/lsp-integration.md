<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Zenzic Language Server (ZLS) Integration

> **ADR coverage:** ADR-075 (Radical Unawareness), ADR-020 (Mirror Law), ADR-013 (RE2 Discipline)

---

## JSON-RPC `stdio` Interface

The `LanguageServer` class in `zenzic.lsp.server` acts as a **stateless transport proxy**: it reads JSON-RPC 2.0 messages from `stdin` and writes responses and notifications to `stdout`. It holds no knowledge of file relationships, graph topology, or cross-document dependencies.

Supported lifecycle events:
| Method | Action |
|---|---|
| `initialize` | Load `ZenzicConfig`, build `AdaptiveRuleEngine`, set `repo_root` |
| `initialized` | Trigger `_build_vsm_sync()`, register `workspace/didChangeWatchedFiles` |
| `textDocument/didOpen` | Inject buffer into `VirtualBufferOverlay`, mark URI dirty |
| `textDocument/didChange` | Update overlay buffer, mark URI dirty (debounced 300ms) |
| `textDocument/didClose` | Evict buffer from overlay |
| `textDocument/hover` | Query VSM route for typed `ZenzicDiagnostic`, serialize at boundary |
| `workspace/didChangeWatchedFiles` | Patch VSM route table O(1) per change |

---

## Strict Diagnostic Typing

All diagnostics are represented internally as `ZenzicDiagnostic` dataclass instances (defined in `zenzic.models.diagnostics`):

```python
@dataclass(frozen=True)
class ZenzicDiagnostic:
    range: DiagnosticRange      # DiagnosticPosition(line, character) × 2
    severity: Severity          # IntEnum: ERROR=1, WARNING=2, INFORMATION=3
    code: str                   # Z-Code string, e.g. "Z101"
    source: str                 # Always "zenzic"
    message: str                # Human-readable description
```

The `to_lsp_dict()` method is the **single serialization boundary**. Untyped dicts are never used for diagnostic payloads; `Any` is forbidden in the diagnostic model. At the serialization boundary, `to_lsp_dict()` formats the diagnostic payload per LSP 3.16/3.17 specifications:

- Prepends the Z-Code prefix to the emitted `message` string (`[{code}] {message}`).
- Includes the `codeDescription` property with `href` pointing to `https://zenzic.dev/docs/reference/finding-codes#{code}`.

Internal `ZenzicDiagnostic` instances retain unformatted, raw messages to preserve core engine independence.

---

## VirtualBufferOverlay

`VirtualBufferOverlay` (in `zenzic.models.vsm`) serves two purposes:

1. **Buffer registry**: maps `file://` URIs to live in-memory text, replacing disk reads during validation.
2. **Reverse index owner**: maintains `incoming_links: dict[str, set[Path]]`, a mapping from canonical URL to the set of files that link to it. This is the sole location tracking graph topology.

The `update()` method automatically calls `_reindex_outgoing_links()`, which re-parses the changed buffer's Markdown links and HTML nodes via `_extract_inline_links_with_lines` and `PolyglotExtractor`, rebuilding the relevant reverse-index entries in O(link count) time.

```text
overlay.dependents_of(canonical_url) -> frozenset[Path]   # O(1)
overlay.update(uri, content)                               # O(links in buffer)
overlay.remove(uri)                                        # O(total URLs in index)
```

---

## Incremental VSM Update Mechanism

Upon a `didChange` event, the `LanguageServer` delegates analysis entirely to the transport-agnostic `IncrementalAnalysisEngine` (in `zenzic.core.incremental`).

The engine executes the following deterministic O(K) pipeline:

1. **Incremental cache update** — the modified URI is read from `overlay.buffers` (or disk if full sync); the engine's internal `md_contents_cache` and `anchors_cache` are patched atomically.
2. **VSM topology patch** — the engine patches the `VirtualSiteMap` route in-place, without full rebuilds for incremental changes.
3. **Dependent expansion** — for each modified file, the engine queries the VSM reverse index (`incoming_links`) to retrieve the set of files containing links that resolve to the modified file. This lookup is O(1).
4. **Targeted validation** — the `AdaptiveRuleEngine` and Uniform Resolver Pipeline (URP) checks run *only* against the modified file and its topological dependents.
5. **Typed store (Mirror Law)** — the engine computes `list[ZenzicDiagnostic]` instances and stores them on the respective `Route.diagnostics` fields.
6. **Serialization boundary** — the engine returns a mapping of URIs to typed diagnostics. The `LanguageServer` then serializes these via `[d.to_lsp_dict() for d in typed_diags]` to produce the JSON-RPC `publishDiagnostics` payload. This is the only location where typed diagnostics are converted to dicts.

---

## Client Version Handshake & Capability Governance

To uphold ADR-075 (Radical Unawareness), the Zenzic Language Server core contains zero editor-specific code. Thin client integrations (such as `zenzic-vscode`) execute a pre-initialization version check before opening JSON-RPC streams:

1. **Minimum Core Baseline**: Client extensions define and enforce a minimum required Zenzic Core version (`MIN_CORE_VERSION`) to guarantee feature set compatibility.
2. **Execution Safety**: Client extensions execute `<executablePath> --version` via `child_process.execFile` (disabling shell interpolation to eliminate injection vectors).
3. **Transport Handshake**: The client verifies the core version before starting stdin/stdout stdio streams.

For user-facing installation, configuration, and editor troubleshooting, see the [VS Code Extension User Guide](../editor/vscode.md).
