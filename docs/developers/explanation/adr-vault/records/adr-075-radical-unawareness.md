---
description: "Architectural Decision Record explaining why the Zenzic Core is decoupled from every consumer environment — CI runners, editors and LSP clients, AI systems, and build frameworks alike."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 075: Radical Unawareness

This section details the specifications and guidelines for ADR 075: Radical Unawareness within the Zenzic ecosystem.

---

## Context

Tight coupling between the Core logic and any specific consumer creates fragile architectures and vendor lock-in. Continuous Integration (CI) runners were the first such consumer, but they are not the only one: the Core is also driven by editors through the Language Server Protocol, by AI systems, and by the documentation build frameworks it analyses.

---

## Decision

The Core completely ignores its consumers. It holds no knowledge of CI runners, of editors or LSP transports, of AI systems, or of the build frameworks whose projects it analyses.

---

## Rationale

By maintaining "radical unawareness" of the execution environment, the Core remains portable, pure, and easy to run locally or anywhere else. The scope is deliberately broad:

- **CI runners** (e.g. GitHub Actions, GitLab CI) — no runner-specific logic or environment probing.
- **Editors and LSP clients** (e.g. VS Code) — no knowledge of JSON-RPC, LSP, or any transport layer. `IncrementalAnalysisEngine` performs analysis natively and returns plain findings; the transport is somebody else's problem.
- **AI systems** — no consumer-specific output shaping. The Core emits the same structured findings regardless of what reads them.
- **Build frameworks** (e.g. MkDocs, Zensical, Sphinx) — engine specifics are confined to the adapter layer, so the Core analyses a unified model rather than any one framework's configuration.

This is one invariant with one meaning, applied to every consumer class.

---

## Invariants

- Core must not contain logic or checks specific to any consumer — CI platform, editor/LSP client, AI system, or build framework.
- Core must rely entirely on standard interfaces (CLI, API) irrespective of the consumer.
- Consumer-specific concerns belong in the layer that owns them: the adapter layer for build frameworks, the LSP server for editor transport, the Action wrapper for CI.

---

## Consequences

- Total portability of the Core analyzer.
- Every consumer environment must adapt to the Core's standard interface, not the other way around.
- A new consumer class can be added without touching the Core, which is what made the LSP server and the GitHub Action possible as thin clients over an unchanged engine.
