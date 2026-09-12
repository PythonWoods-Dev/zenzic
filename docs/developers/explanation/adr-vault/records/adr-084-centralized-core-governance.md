---
description: "Architectural Decision Record centralizing directory_policies and per_file_ignores governance evaluation inside zenzic.core.governance, shared identically by the CLI and LSP analysis paths."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 084: Centralized Core Governance

This document details the architectural specification and contract for ADR 084: Centralized Core Governance within the Zenzic ecosystem.

---

## Context

In prior releases, governance evaluation (`directory_policies` and `per_file_ignores`) executed inside the CLI runner's own post-scan pipeline. The Language Server's incremental single-file analysis path did not go through that same pipeline, so an edit evaluated by the LSP could bypass a global directory policy that the exact same file would have hit under a terminal `zenzic check all` run. This produced diagnostic divergence between CI/terminal output and the VS Code Problems panel for the same source file.

---

## Decision

Governance evaluation is centralized in `zenzic.core.governance`, exposing `apply_per_file_ignores()` and `apply_directory_policies()` as the single implementation both analysis paths call:

1. **CLI path**: `_check.py`, `_audit.py`, `_standalone.py`, and `_lab.py` all filter their findings through `zenzic.cli._governance`'s thin wrappers around the same two Core functions.
2. **LSP path**: `IncrementalAnalysisEngine._analyze_file` (`incremental.py`) calls `apply_per_file_ignores()` and `apply_directory_policies()` directly from `zenzic.core.governance` on every incremental document edit, before diagnostics are emitted to the editor.
3. **No independent LSP-side governance logic**: the LSP does not re-implement or approximate directory-policy or per-file-ignore filtering — it calls the identical Core functions the CLI calls.

---

## Rationale

Two independently maintained governance filters — one for the CLI, one for the LSP — would inevitably drift: a new policy rule, a fixed edge case, or a changed precedence order applied to one path and not the other silently reintroduces the exact divergence this decision closes. A single shared implementation, called identically by both consumers, makes that class of drift structurally impossible rather than a discipline to remember on every future governance change.

---

## Invariants

- `directory_policies` and `per_file_ignores` filtering logic exists in exactly one place, `zenzic.core.governance`'s `apply_directory_policies()` and `apply_per_file_ignores()`.
- Every analysis entry point that reports governance-filtered findings — CLI (`_check.py`, `_audit.py`, `_standalone.py`, `_lab.py`) and LSP (`incremental.py`) — calls these same two functions, directly or through a thin non-behavior-changing wrapper (`zenzic.cli._governance`).
- A file inspected via `zenzic check all` in CI and the identical file open in the VS Code Problems panel report identical governance-filtered findings for identical source content and identical `.zenzic.toml` policy configuration.

---

## Consequences

- Whether a document is analyzed via the terminal CLI or live inside the editor, `directory_policies` and `per_file_ignores` produce identical suppression/labeling results — no separate LSP-specific governance code path exists to drift out of sync.
- A future governance-filtering change (a new policy type, a precedence fix) is written once in `zenzic.core.governance` and is automatically effective for both consumers, with no separate LSP-side patch required.
- This ADR governs `directory_policies`/`per_file_ignores` centralization specifically. A separate, narrower implementation detail — stripping backtick inline code spans and skipping fenced code blocks so didactic suppression-comment examples in prose are not miscounted as active suppressions (`suppressions.py`, `rules.py`, `scanner.py`) — previously cited this same ADR number but governs a different concern; those citations have been reworded as plain comments describing the behavior directly, since it was never actually this decision's subject.
