---
title: "Zenzic v0.24.0: Interactive Intelligence"
slug: zenzic-v0240-interactive-intelligence
date: 2026-07-24
authors:
  - pythonwoods
description: >
  Introducing Zenzic v0.24.0 (Interactive Intelligence): LSP Code Actions with in-memory workspace edits, real-time DQS Status Bar visualization, and deterministic URI normalization fixes.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic v0.24.0 marks the transition from passive static validation to interactive, editor-native remediation. This release introduces LSP Code Actions for automated Quick Fixes, real-time Documentation Quality Score (DQS) streaming to the editor status bar, and critical URI normalization bugfixes.

<!-- more -->

## From Passive Validation to Interactive Remediation

Prior to v0.24.0, Zenzic detected structural defects, missing alt text, and dead suppressions, reporting them as diagnostics in the editor or CI pipeline. Remediation required authors to manually edit the Markdown buffer or run CLI commands.

Zenzic v0.24.0 bridges analysis and remediation directly inside the editor environment via Language Server Protocol (LSP) capabilities and custom JSON-RPC streaming.

---

## LSP Code Actions (Quick Fixes)

With `textDocument/codeAction` support, Zenzic now exposes deterministic auto-fix capabilities directly within the VS Code Lightbulb menu.

### In-Memory Mutation Architecture

Traditional LSP extensions often trigger direct filesystem writes during auto-fix requests. This introduces race conditions with the editor buffer, dirty file conflicts, and disk I/O overhead.

Zenzic solves this by leveraging its internal **Atomic Mutator** engine to compute edits completely in memory:

1. **Request Dispatch**: When an author selects a Quick Fix (e.g. for `Z121` Missing Alt Text or `Z603` Dead Suppression), VS Code dispatches a `textDocument/codeAction` request containing the target range and diagnostic code.
2. **In-Memory AST Mutation**: The Zenzic Language Server retrieves the buffer from `VirtualBufferOverlay`, applies the corresponding `Mutation` transformation in memory without touching disk, and computes the minimal set of `TextEdit` objects.
3. **`WorkspaceEdit` Payload**: The server packages the computed text edits into a standard LSP `WorkspaceEdit` response. VS Code applies the edits directly to the open editor buffer, preserving undo/redo history and avoiding dirty buffer conflicts.

---

## Real-Time DQS Visualization (VS Code Status Bar)

Zenzic v0.24.0 introduces the `zenzic/dqsUpdate` custom JSON-RPC notification channel.

### Zero-Disk I/O Scoring Engine

Calculating the global Documentation Quality Score (DQS) across hundreds of documentation pages could introduce latency if it required scanning disk files or rebuilding the Virtual Site Map (VSM).

The Zenzic Language Server computes the workspace DQS using a zero-disk-read model:

- **State Reuse**: The server aggregates diagnostic severity frequencies directly from the active in-memory VSM state (`vsm.values()`).
- **Real-Time Streaming**: Upon every incremental workspace analysis, the server dispatches a `zenzic/dqsUpdate` notification containing the global score, base score, and breakdown penalties.
- **Thin Client Rendering**: The VS Code extension listens on `client.onNotification('zenzic/dqsUpdate')` and immediately updates the editor status bar item (e.g. `$(dashboard) DQS: 98/100`).

---

## Deterministic Bugfixes and Stability

### 1. URI Normalization Parity (`LSP-FIX-001`)

In previous versions, relative Markdown links within nested subdirectories (such as `./target.md` in `docs/developers/explanation/adr-vault/records/`) produced false-positive `Z101` (Broken Link) findings in LSP mode.

This divergence stemmed from context-aware link resolution in `VSMBrokenLinkRule._to_canonical_url`, which previously restricted relative directory resolution to links containing `".."` segments. In v0.24.0:

- Relative links without `".."` are correctly resolved relative to the parent directory of the source file (`source_dir`).
- All `file://` URIs received over JSON-RPC undergo `urllib.parse.unquote()` percent-decoding before `Path.resolve()` conversion, eliminating path mismatches for encoded characters.

### 2. VS Code Remediation Command (`VSCODE-FIX-004`)

Fixed the executable command string sent to the VS Code terminal when prompting authors to update an outdated Zenzic Core binary. The action now executes `uv tool install --force zenzic` cleanly with an immediate newline, preventing unsubmitted command prompts.

---

## Upgrading

To update Zenzic Core globally via `uv`:

```bash
uv tool install --force zenzic
```

The Zenzic VS Code extension updates automatically via the Visual Studio Marketplace.
