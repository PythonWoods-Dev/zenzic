---
template: home.html
title: "Zenzic — Deterministic Document Integrity Engine & SAST"
hide:
  - navigation
  - toc
  - path
  - feedback
description: "Zenzic is a deterministic document integrity engine and SAST for Markdown/MDX graphs. Detect broken links, credential leaks, and topological defects before merge."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Treat your Markdown documentation like production code

Zenzic detects broken links, orphaned pages, credential leaks, and structural integrity issues before they reach production. Every run is bit-for-bit deterministic, zero-LLM, and backed by a non-backtracking RE2 regex engine.

---

## ⚡ Unified Ecosystem Platform

Zenzic is structured into three dedicated delivery mechanisms to support your entire development workflow:

- **[Core Engine (CLI)](./reference/cli.md)**: Python CLI, AST rule engine, and Virtual Site Map (VSM) topology analyzer.
- **[Getting Started](./tutorials/first-audit.md)**: Step-by-step tutorial to run your first documentation audit in under three minutes.
- **[Configuration Reference](./reference/configuration-reference.md)**: Complete guide to `.zenzic.toml` workspace settings.

---

## 🚀 Deterministic 3-Step Quickstart (< 60 Seconds)

Experience zero-config topological failure detection in under 60 seconds:

```bash
# Step 1: Install Zenzic CLI
uv tool install zenzic

# Step 2: Initialize workspace and create a broken link
zenzic init
mkdir -p docs
echo "[broken](missing.md)" > docs/index.md

# Step 3: Run full documentation graph analysis
zenzic check all
```

**Expected Output:**

```text
docs/index.md:1  [Z104]  'missing.md' resolves to nowhere — the target file does not exist.

FAILED: Hard errors detected. Exit code 1 is mandatory.
```

---

## 🛡️ Why Zenzic?

Zenzic provides a comprehensive, deterministic quality architecture for your documentation suite:

### 100% Determinism & Baseline Tracking

Every Zenzic run is a pure function of its inputs. Given the same repository state and `.zenzic.toml`, the output — finding codes, severity levels, exit code, SARIF structure — is **bit-for-bit identical** across machines, platforms, and time.

With **Baseline & Regression Tracking**, existing technical debt can be recorded into a deterministic snapshot (`.zenzic-baseline.json`) via `--update-baseline`. Subsequent CI runs validate against `--baseline .zenzic-baseline.json` using line-shift invariant SHA-256 signatures, tagging baselined findings without dropping them (**Radical Unawareness**) and enforcing Document Quality Score (DQS) anti-regression rules.

```bash
# Record existing technical debt into baseline snapshot
zenzic check all --update-baseline

# Validate PR against baseline in CI/CD pipeline
zenzic check all --baseline .zenzic-baseline.json
```

### Documentation Security (SAST)

Zenzic treats documentation as a **security surface**. The tiered code model enforces a hard boundary between quality findings (suppressible, exit 1) and security findings (non-suppressible, exit 2/3):

- **Z201 — Credential Scanner:** Hardcoded tokens, API keys, and secret patterns detected before reaching PRs.
- **Z202 / Z203 — Path Traversal Guard:** Filesystem boundary security violations caught at scan boundaries.
- **Suppression CAP:** Configurable ceiling on total active `zenzic:ignore` suppressions.

### Semantic Linting & Readability Metrics

Evaluate content quality without relying on probabilistic models or LLMs:

- **Z510 — Heading Hierarchy:** Detects skipped heading levels (e.g. H3 directly following H1).
- **Z511 — Excessive Sentence Length:** Enforces maximum sentence word count (`max_sentence_length = 40`).
- **Z512 — Empty Section:** Identifies heading sections containing no prose content before the next heading or EOF.

### Topological Graph Analysis (Smart Link Graph)

Beyond static link checks, Zenzic's Smart Link Graph constructs an adjacency matrix over your document network to perform Breadth-First Search (BFS):

- **Z410 — Unreachable Graph Node:** Documents completely isolated or unreachable from navigation entry points.
- **Z411 — Dead-End Node:** Documentation pages containing no outgoing links.

### Configuration Validation Engine

Formal schema validation for `.zenzic.toml` (`Z110` TOML syntax errors, `Z111` schema type mismatches) with exact line-number extraction. Fatal config errors halt document graph scanning to prevent false-positive cascades and protect LSP stability.
