---
description: "Architectural Decision Record establishing Single-Pass AST Compilation and Command-Query Segregation (CQS) for the Zenzic CLI."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 091: Single-Pass AST Compilation & Command-Query Segregation (CQS)

This document details the architectural specification and contract for ADR 091: Single-Pass AST Compilation and Command-Query Segregation within the Zenzic ecosystem.

---

## Context

A double invocation of document scanning was discovered in the CLI collection layer, degrading end-to-end execution to $O(2N)$. Furthermore, proposals arose to merge mutation flags (`--stamp`) into read-only validation commands (`check all`), threatening the Single Responsibility Principle (SRP).

---

## Decision

1. **Single-Pass Invariant**: The document graph, AST token streams, and reference mappings must be compiled **exactly once** per CLI command. Downstream validators (`validate_links_structured`, orphan detection, asset analyzers) must receive precomputed in-memory reports rather than re-traversing the filesystem.
2. **Command-Query Segregation (CQS)**:
   - **`zenzic check` (Query/Read-Only)**: Pure static inspection. Evaluates rules, topological references, credentials, and policies. It must never mutate any file on disk.
   - **`zenzic score` & `zenzic fix` (Command/Write)**: Mutating operations. Calculates DQS metrics, stamps status badges on disk (`--stamp`), or applies lossless AST auto-remediations.

---

## Rationale

Decoupling validation from mutation prevents monolithic CLI commands, guarantees predictable testability, and ensures that static analysis runs in strict linear time $O(N)$. Passing precomputed reports between modules eliminates redundant multiprocess pool coordination.

---

## Invariants

- Total filesystem reads remain strictly $O(N)$ across all CLI subcommands.
- `zenzic check` subcommands are guaranteed to be side-effect free and read-only.
- All mutating commands must be explicit and idempotent.

---

## Consequences

- End-to-end verification speedup across multi-hundred file repositories.
- Strict isolation between static rule evaluation and badge/metric persistence.
- Deterministic, easily parallelizable AST visitor pipelines.

For related specifications, see [ADR 021: Parallel Audit](./adr-021-parallel-audit.md) and the [ADR Vault](../index.md).
