---
title: Architectural Explanations
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architectural Explanations

Deep dives into the architectural foundation, mathematical models, security boundaries, and determinism guarantees governing Zenzic.

---

## Core Foundations & Topology

<div class="grid cards" markdown>

- :material-sitemap:{ .lg .middle style="color: #6366f1;" } **[Architecture Deep Dive](architecture.md)**

    ---

    The 4-layer architecture: Client Entrypoints, Core Engine, Adapter Layer, and Deterministic Gate.

    [:material-arrow-right: Explore Architecture](architecture.md)

- :material-cpu-64-bit:{ .lg .middle style="color: #6366f1;" } **[Core Execution Mechanics](core-mechanics.md)**

    ---

    Single-pass AST evaluation, dual-stream credential scanning, and graph cycle resolution.

    [:material-arrow-right: Read Mechanics](core-mechanics.md)

- :material-magnify-scan:{ .lg .middle style="color: #6366f1;" } **[Discovery Engine](discovery.md)**

    ---

    Hierarchical exclusion resolution, immutable system guardrails, and .gitignore traversal.

    [:material-arrow-right: Read Discovery](discovery.md)

- :material-vector-polyline:{ .lg .middle style="color: #6366f1;" } **[Structural Integrity](structural-integrity.md)**

    ---

    Lossless AST compilation, Virtual Site Map (VSM) indexing, and polyglot link extraction.

    [:material-arrow-right: Read Foundations](structural-integrity.md)

</div>

---

## Mathematical Scoring & Governance

<div class="grid cards" markdown>

- :material-calculator:{ .lg .middle style="color: #10b981;" } **[Document Quality Score (DQS)](scoring-system.md)**

    ---

    The weighted mathematical formula, category ceilings, and non-linear penalties.

    [:material-arrow-right: Explore Scoring](scoring-system.md)

- :material-scale-balance:{ .lg .middle style="color: #10b981;" } **[Managed Technical Debt](exclusion-design.md)**

    ---

    Why unmonitored ignores degrade quality and how Zenzic bounds debt via the Suppression CAP.

    [:material-arrow-right: Read Governance](exclusion-design.md)

- :material-history:{ .lg .middle style="color: #10b981;" } **[Baseline Regression Tracking](baseline-tracking.md)**

    ---

    Snapshotting legacy documentation debt and enforcing zero new defects in pull requests.

    [:material-arrow-right: Read Baseline](baseline-tracking.md)

- :material-shield-lock:{ .lg .middle style="color: #10b981;" } **[Zero-Network Privacy Gate](privacy-gate.md)**

    ---

    Total isolation: why Zenzic never transmits source files, metadata, or telemetry over the wire.

    [:material-arrow-right: Read Privacy Gate](privacy-gate.md)

</div>

---

## Developer Experience & Tooling

<div class="grid cards" markdown>

- :material-magic-staff:{ .lg .middle style="color: #0284c7;" } **[Auto-Fix Philosophy](auto-fix-philosophy.md)**

    ---

    Atomic AST mutations, idempotency guarantees, and safe automated code block formatting.

    [:material-arrow-right: Read Auto-Fix](auto-fix-philosophy.md)

- :material-code-json:{ .lg .middle style="color: #0284c7;" } **[Language Server Architecture](language-server-architecture.md)**

    ---

    Real-time incremental AST parsing, LSP protocol handler, and debounce queue design.

    [:material-arrow-right: Read LSP Design](language-server-architecture.md)

- :material-github:{ .lg .middle style="color: #0284c7;" } **[GitHub Action Internals](github-action-internals.md)**

    ---

    Pure runner execution, zero API token dependency, and native SARIF generation.

    [:material-arrow-right: Read Action Internals](github-action-internals.md)

</div>
