---
title: "Zenzic v0.27.0: Deterministic Quality Platform"
slug: zenzic-v0270-deterministic-quality-platform
date: 2026-08-02
authors:
  - pythonwoods
description: >
  Zenzic v0.27.0 evolves the engine from a strict link validator into a comprehensive Quality Platform, introducing topological graph analysis (Smart Link Graph), line-shift invariant baseline tracking, zero-LLM semantic linting, and formal configuration schema validation.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic v0.27.0 expands the engine from a structural validator into a full **Deterministic Quality Platform**, introducing evolutionary baseline tracking, topological graph analysis, mathematical content readability linting, and formal TOML configuration validation.

<!-- more -->

## Evolving Beyond Link Checking

Document integrity requires more than confirming that target Markdown files exist on disk. Enterprise documentation suites suffer from topological isolation, structural drift in heading hierarchies, unreadably verbose prose, and legacy technical debt that prevents adopting CI/CD quality gates.

Zenzic v0.27.0 addresses these operational realities through four architectural components, maintaining zero-LLM determinism and $O(N)$ execution bounds across all rules.

---

## 1. Smart Link Graph & Topological Analysis (`Z4xx`)

The Virtual Site Map (VSM) now constructs an adjacency matrix over your document network during Pass 1.5, running Breadth-First Search (BFS) starting from defined site entry points in $\Theta(V + E)$ time:

- **Z410 (`UNREACHABLE_GRAPH_NODE`)**: Identifies documentation pages on disk that are completely isolated or unreachable through any navigation link path starting from entry points.
- **Z411 (`DEAD_END_NODE`)**: Identifies documentation pages containing zero outgoing links, stranding readers without navigation pathways to continue exploring.

---

## 2. Baseline & Regression Tracking (`.zenzic-baseline.json`)

To enable immediate adoption of strict CI/CD gates on repositories with existing technical debt, Zenzic v0.27.0 introduces deterministic baseline snapshots:

```bash
# Capture current repository findings into baseline snapshot
zenzic check all --update-baseline

# Validate Pull Requests against baseline in CI/CD
zenzic check all --baseline .zenzic-baseline.json
```

### Line-Shift Invariant Signatures

Finding signatures are computed using SHA-256 hashes excluding line numbers:

$$\text{Signature} = \text{SHA256}[\text{RuleCode} + \text{PosixPath} + \text{ContextTarget}]$$

Inserting or deleting lines above an existing defect does **not** invalidate its baseline match. Baselined defects are tagged with `is_baselined: true` (**Radical Unawareness**), allowing reports to display existing debt transparently while failing CI builds if a new defect is introduced or if the Document Quality Score (DQS) regresses below the baseline threshold.

---

## 3. Semantic Linting & Readability Metrics (`Z5xx`)

Zenzic evaluates prose quality without probabilistic models, heuristics, or LLM sampling:

- **Z510 (`HEADING_HIERARCHY`)**: Detects illegal skips in heading levels (e.g. H1 followed immediately by H3).
- **Z511 (`EXCESSIVE_SENTENCE_LENGTH`)**: Enforces maximum sentence length (`max_sentence_length = 40` words) using RE2-compliant sentence boundary splitting.
- **Z512 (`EMPTY_SECTION`)**: Flags heading sections that contain zero prose or content before the next heading or end-of-file.

---

## 4. Configuration Validation Engine (`Z110`, `Z111`)

`.zenzic.toml` and `.zenzic.local.toml` are now validated against formal schemas before Markdown scanning begins:

- **Z110 (`CONFIG_SYNTAX_ERROR`)**: Captures TOML decode errors with exact line-number extraction.
- **Z111 (`CONFIG_SCHEMA_ERROR`)**: Captures schema type mismatches and unsupported configuration properties.

When a fatal configuration error occurs, the engine emits `Z110`/`Z111` attached to the configuration file URI and halts Markdown scanning to prevent false-positive cascades and preserve Language Server Protocol (LSP) stability. Fatal configuration errors collapse the Documentation Quality Score (DQS) to `0.0` with `security_override = True`.

---

## Summary of New Diagnostic Codes

| Code | Name | Severity | Penalty | Suppressible | Quick Fix |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Z410** | `UNREACHABLE_GRAPH_NODE` | `error` | 5.0 | Yes | No |
| **Z411** | `DEAD_END_NODE` | `warning` | 2.0 | Yes | No |
| **Z510** | `HEADING_HIERARCHY` | `warning` | 3.0 | Yes | No |
| **Z511** | `EXCESSIVE_SENTENCE_LENGTH` | `warning` | 2.0 | Yes | No |
| **Z512** | `EMPTY_SECTION` | `warning` | 2.0 | Yes | No |
| **Z110** | `CONFIG_SYNTAX_ERROR` | `error` | 0.0 | No | No |
| **Z111** | `CONFIG_SCHEMA_ERROR` | `error` | 0.0 | No | No |

---

## Getting Started with v0.27.0

Update Zenzic via `uv`:

```bash
uv tool update zenzic
```

Run a full audit with baseline tracking on your repository:

```bash
zenzic check all --update-baseline
```
