---
title: "Shift-Left to the Keystroke: The Zenzic VS Code Extension"
slug: zenzic-vs-code-extension
date: 2026-07-18
authors:
  - pythonwoods
description: >
  Zenzic arrives in the editor. Introducing the official VS Code Extension: sub-50ms deterministic diagnostics, credential scanning, and real-time topological validation.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

Since its inception, Zenzic has operated as a strict, deterministic gatekeeper for CI/CD pipelines. It ensures that no broken links, malformed topology, or hardcoded credentials ever reach production.

Today, we are eliminating the latency between authoring a defect and discovering it. We are officially releasing the **Zenzic VS Code Extension**, bringing the deterministic precision of our engine directly into your authoring environment.

<!-- more -->

![Shift-Left to the Keystroke: The Zenzic VS Code Extension](../../assets/images/blog/zenzic-vs-code-extension.webp)

## The Thin Client Architecture

Most documentation linters suffer from architectural bloat, bundling heavy Node.js parsers or embedding redundant logic directly into the editor extension. This leads to high memory consumption and fragmented rule sets where the editor behaves differently than the CI pipeline.

We rejected this model. The Zenzic VS Code extension is a strictly **Thin Client**.

It contains zero parsing logic, zero regex engines, and zero validation rules. Instead, it utilizes the Language Server Protocol (LSP) over standard I/O to communicate directly with your local Zenzic Python binary.

The result is absolute parity. The exact same engine that governs your GitHub Actions pipeline is now validating your keystrokes in real-time.

## Sub-50ms Topological Feedback

By leveraging the `zenzic.lsp` module and the newly decoupled `IncrementalAnalysisEngine` (introduced in Core v0.23.0), the extension maintains an in-memory `VirtualBufferOverlay`.

When a document is modified, the engine does not rebuild the entire workspace. It performs an $O(K)$ incremental patch on the Virtual Site Map (VSM), re-evaluating only the modified file and its direct topological dependents. This guarantees sub-50ms latency while preserving graph-wide integrity.

- **Z201 (Credential Leak):** Paste a GitHub token into your markdown, and it is flagged instantly.
- **Z101 (Missing Target):** Type a link to a non-existent file, and the diagnostic appears before you save.
- **Z102 (Broken Anchor):** Modify a heading in `file_b.md`, and any open buffer linking to that specific anchor is immediately invalidated.

## How to Get Started

The extension is now publicly available on the Visual Studio Marketplace.

1. **Install the Core Engine:** The extension requires the Zenzic Python binary (v0.23.1 or higher) to operate.

   ```bash
   uv tool install --force zenzic
   ```

2. **Install the Extension:** Search for `Zenzic` in the VS Code Extensions panel, or install it via the command line:

   ```bash
   code --install-extension pythonwoods.zenzic-vscode
   ```

3. **Configure (Optional):** If you use a local virtual environment, point the extension to it in your VS Code `settings.json`:

   ```json
   {
     "zenzic.executablePath": "${workspaceFolder}/.venv/bin/zenzic"
   }
   ```

No cloud dependencies. No telemetry. No probabilistic AI guessing. Just deterministic rules enforcing structural integrity.
