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

## Treat your Markdown documentation like production code.

Zenzic detects broken links, orphaned pages, credential leaks, and structural integrity issues before they reach production. Every run is bit-for-bit deterministic, zero-LLM, and backed by a non-backtracking RE2 regex engine.

---

## ⚡ Unified Ecosystem Platform

Zenzic is structured into three dedicated delivery mechanisms to support your entire development workflow:

- **[Core Engine (CLI)](https://zenzic.dev/)**: Python CLI, AST rule engine, and Virtual Site Map (VSM) topology analyzer.
- **[VS Code Extension](https://github.com/PythonWoods/zenzic-vscode)**: Real-time LSP client providing sub-50ms inline diagnostics, automated Quick Fixes, and DQS status bar streaming.
- **[GitHub Action](https://github.com/PythonWoods/zenzic-action)**: Zero-config CI/CD quality gate with SARIF upload directly to GitHub Code Scanning and PR annotations.


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

### 100% Determinism
Every Zenzic run is a pure function of its inputs. Given the same repository state and `.zenzic.toml`, the output — finding codes, severity levels, exit code, SARIF structure — is **bit-for-bit identical** across machines, platforms, and time. No probabilistic guessing, no LLM sampling, no network dependencies.

### Documentation Security (SAST)
Zenzic treats documentation as a **security surface**. The tiered code model enforces a hard boundary between quality findings (suppressible, exit 1) and security findings (non-suppressible, exit 2/3):
- **Z201 — Credential Scanner:** Hardcoded tokens, API keys, and secret patterns detected before reaching PRs.
- **Z202 / Z203 — Path Traversal Guard:** Filesystem boundary security violations caught at scan boundaries.
- **Suppression CAP:** Configurable ceiling on total active `zenzic:ignore` suppressions.

### Zero Hallucinations
Zenzic reports only what is **statically verifiable** in the repository at scan time. Every finding is a falsifiable, reproducible fact — suitable as audit evidence for security reviewers and compliance teams.
