<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

<p align="center">
  <a href="https://github.com/PythonWoods/zenzic">
    <img src="https://raw.githubusercontent.com/PythonWoods/zenzic/main/docs/assets/brand/svg/zenzic-logo.svg" alt="Zenzic Document Integrity Engine" width="480">
  </a>
</p>

<p align="center">
  <a href="https://github.com/PythonWoods/zenzic/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/PythonWoods/zenzic/ci.yml?branch=main&label=ci&style=flat-square" alt="ci-status">
  </a>
  <!-- zenzic:audit-badge -->
  <img src="https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F_zenzic--audit-passing-22c55e?style=flat-square" alt="zenzic-audit">
  <!-- zenzic:score-badge -->
  <img src="https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F_zenzic--score-98_%2F_100-f59e0b?style=flat-square" alt="zenzic-score">
  <a href="https://reuse.software/">
    <img src="https://img.shields.io/badge/REUSE-3.x%20compliant-0d9488?style=flat-square" alt="REUSE 3.x compliant">
  </a>
  <a href="https://pypi.org/project/zenzic/">
    <img src="https://img.shields.io/pypi/v/zenzic?label=PyPI&color=38bdf8&style=flat-square" alt="PyPI Version">
  </a>
  <a href="https://pepy.tech/project/zenzic">
    <img src="https://img.shields.io/pepy/dt/zenzic?color=4f46e5&label=downloads&style=flat-square" alt="Downloads">
  </a>
  <a href="https://pypi.org/project/zenzic/">
    <img src="https://img.shields.io/pypi/pyversions/zenzic?color=10b981&style=flat-square" alt="Python Versions">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-Apache--2.0-0d9488?style=flat-square" alt="License">
  </a>
</p>

<p align="center">
  <strong>Deterministic Document Integrity & Quality Engine for Markdown/MDX graphs.</strong><br>
  <em>Stop broken links, leaked secrets, accessibility defects, and semantic bugs before they reach production.</em>
</p>

---

## Markdown is Production Code

Documentation is software. Broken links, orphaned pages, leaked API keys, and invalid HTML structures degrade developer trust, damage SEO, and cause critical security incidents.

Most documentation tools tell you what's wrong. Zenzic fixes it. By treating Markdown with the same rigor as compiled code, Zenzic ensures your documentation is secure, accessible, and mathematically sound. Sleep soundly knowing your docs are perfect.

**Zenzic** is a fast, deterministic static analyzer and automated remediation engine for Markdown and MDX repositories. It evaluates your entire documentation graph in milliseconds—verifying cross-file links, scanning for credentials, enforcing semantic accessibility, and applying atomic fixes directly to your files.

---

## ⚡ Quick Start (< 60 Seconds)

### 1. Install Zenzic

Get started in 2 seconds with uv:

```bash
# Recommended: isolated tool install via uv
uv tool install zenzic

# Or run ephemerally without installing
uvx zenzic@0.30.0 check all

# Or via standard pip
pip install --upgrade zenzic
```

### 2. Initialize and Verify Your Repository

```bash
# Scaffold initial configuration
zenzic init

# Run full documentation graph analysis
zenzic check all
```

### 3. Automatically Fix Issues

```bash
# Preview automated fixes without touching files
zenzic fix --dry-run

# Atomically apply fixes across all Markdown documents
zenzic fix --apply
```

### 4. Git Pre-Commit Hook (Optional)

Catch broken links and leaked secrets before `git commit`:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      - id: zenzic-guard   # Fast staged-file credential scan
      - id: zenzic-verify  # Documentation integrity gate
```

---

## 🎯 What Zenzic Solves

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             ZENZIC CORE ENGINE                              │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│  🔗 Broken Links &   │  🔐 Leaked Secrets   │  ♿ Semantic Accessibility    │
│     Orphan Pages     │     & Credentials    │     & Editorial Governance    │
│  ──────────────────  │  ──────────────────  │  ───────────────────────────  │
│  • Cross-file links  │  • API tokens / keys │  • Duplicate headings (Z513)  │
│  • Anchor validation │  • AWS / Stripe keys │  • Generic image alt (Z514)   │
│  • Missing assets    │  • Path traversal    │  • Malformed lists (Z520)     │
│  • Unused images     │  • Non-suppressible  │  • Policy-as-Code (Z610–Z619) │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
```

---

## 🛡️ Core Capabilities

### 1. High-Speed Graph Topology (VSM)

Zenzic's in-memory **Virtual Site Map (VSM)** indexes thousands of Markdown pages, anchors, and media assets in seconds. Renaming a document or moving a heading immediately flags all broken cross-references across the repository.

### 2. Zero Subprocesses & Deterministic Safety

- **Zero Subprocesses (ADR-002)**: Analysis executes in-process without spawning external shell processes, guaranteeing maximum security and predictable sub-50ms execution.
- **Google RE2 Regular Expressions**: All pattern matching is protected against catastrophic backtracking (ReDoS) and unbounded execution loops.

### 3. Atomic Mutator (`zenzic fix`)

Remediation must be lossless and idempotent:

- Wraps bare URLs in standard `<url>` notation (`Z515`).
- Strips trailing punctuation from headings (`Z517`).
- Transforms fake paragraph lists into valid Markdown bullet lists (`Z520`).
- Injects missing language tags on code blocks (`Z505`).
- Cleans up dead inline suppressions (`Z603`).

### 4. Deterministic Quality Score (DQS)

Zenzic calculates a mathematical health score (0–100) based on active findings, severities, and technical debt. Enforce strict team standards in CI (`fail_under = 90`) and track improvements over time with status badges.

```text
$ zenzic score

✨ Quality Score: 94/100

╭─ Quality Breakdown ──────────────────────────────────────╮
│   Category     Issues  Weight  Raw Pts  Applied Pts      │
├──────────────────────────────────────────────────────────┤
│ ✓ structural      0      30%      0           0          │
│ ✓ navigation      0      25%      0           0          │
│ ✗ content         2      20%     -4          -4          │
│ ✓ brand           0      25%      0           0          │
├──────────────────────────────────────────────────────────┤
│   Σ Subtotal                                96           │
╰──────────────────────────────────────────────────────────╯
  ! Technical Debt (2 suppressions)          -2 pts
  = Final Quality Score                      94 / 100
```

### 5. Policy-as-Code Governance

Define organizational conventions directly in `.zenzic.toml`:

```toml
[policies]
required_frontmatter_keys = ["title", "description"]
allowed_external_domains = ["github.com", "zenzic.dev"]
enable_passive_voice_check = true
weasel_words = ["clearly", "simply", "obviously"]
forbidden_content_patterns = ["(?i)\\bconfidential\\b"]
max_document_complexity = 45
```

### 6. Custom Rule SDK v3

Extend Zenzic with organization-specific invariants. The **[Custom Rule SDK v3](https://zenzic.dev/docs/developers/how-to/write-ast-rule/)** (`zenzic.sdk`) lets you author typed, deterministic AST visitor plugins in Python with guaranteed $O(N)$ execution and full SARIF integration.

---

## 🏗️ Architecture & Engine Deep Dive

Zenzic is engineered from the ground up as a **deterministic compiler** rather than a loose collection of linters. It delivers **$O(N)$ execution speed**, scanning thousands of Markdown documents in milliseconds through pure-function compilation and zero-subprocess architecture.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ZENZIC COMPILATION PIPELINE                        │
├─────────────────┬─────────────────┬───────────────────┬─────────────────────┤
│  1. AST Parser  │  2. VSM Builder │  3. Rule Engine   │  4. Atomic Mutator  │
│  ────────────── │  ────────────── │  ──────────────── │  ────────────────── │
│  • Token stream │  • Global graph │  • Pure functions │  • AST patcher      │
│  • Heading tree │  • Route index  │  • RE2 regex ACL  │  • Idempotent fix   │
│  • Lossless map │  • Ghost routes │  • DQS evaluation │  • Zero formatting  │
│                 │                 │  • SARIF reporter │    corruption       │
└─────────────────┴─────────────────┴───────────────────┴─────────────────────┘
```

### 1. Lossless AST & Atomic Mutator (`zenzic.core.mutator`)

Unlike regex-based search-and-replace tools that corrupt code fences, frontmatter, and inline math, Zenzic parses Markdown into a structured Abstract Syntax Tree (AST).

Mutations are executed directly on AST nodes and serialized back through a lossless emitter, guaranteeing:

- **Zero Syntax Corruption**: Comments, indentation, code fences, and blank lines remain byte-for-byte identical outside the target node.
- **Strict Idempotence**: Running `zenzic fix --apply` multiple times produces the exact same AST state without duplicate edits:
  $$\text{mutate}(\text{mutate}(\text{AST})) = \text{mutate}(\text{AST})$$

### 2. Virtual Site Map (VSM) & Topological Graph (`zenzic.core.vsm`)

Zenzic builds an in-memory topological routing graph (the **Virtual Site Map**) across all documents and static assets in your workspace.

The VSM maintains:

- **Exact Slug Parity**: Heading anchors are slugified according to the active build adapter (MkDocs Material, Zensical, or Standalone) without running the generator itself.
- **Cross-File Resolution**: Validates relative paths, root-relative links, anchor fragments (`#section-id`), and media assets.
- **Ghost Route Registry**: Recognizes virtual and dynamically generated routes to eliminate false positives in complex documentation graphs.

### 3. Deterministic Quality Score (DQS) Mathematical Model

Zenzic computes an objective, reproducible 0–100 documentation quality score using a weighted deduction model:

$$\text{DQS} = \max\left(0, 100 - \sum \text{Penalties} - \text{Suppression Debt}\right)$$

| Category | Severity Range | Description |
| :--- | :--- | :--- |
| **Security** (`Z2xx`) | 10.0 pts (Fatal) | Leaked credentials, secret tokens, path traversal |
| **Structure** (`Z1xx`, `Z516`) | 3.0–5.0 pts | Broken links, missing files, multiple H1 headers |
| **References** (`Z3xx`) | 2.0–3.0 pts | Dead definitions, duplicate reference labels |
| **Assets** (`Z4xx`) | 1.0–2.0 pts | Missing images, orphan assets, missing indexes |
| **Content & A11y** (`Z5xx`) | 1.0–2.0 pts | Duplicate headings, generic alt text, malformed lists |
| **Governance** (`Z6xx`) | 1.0–4.0 pts | Policy violations, forbidden terms, complexity caps |

Under Zenzic's **Flat-Cost Model**, every inline suppression comment (`<!-- zenzic:ignore ZXXX -->`) costs exactly 1.0 DQS point, ensuring technical debt is visible, quantified, and capped (`suppression_cap = 30`).

### 4. RE2 Discipline & Sovereign Runtime (ADR-002, ADR-075)

- **$O(N)$ Execution Performance**: Scans thousands of Markdown files in milliseconds with linear time complexity and minimal memory overhead.
- **Zero Subprocesses (ADR-002)**: Zenzic executes 100% in-process with zero `subprocess.Popen` invocations, ensuring safe, lightweight execution across sandbox environments.
- **Google RE2 Non-Backtracking Engine**: All regex operations are backed by Google RE2 via an Access Control Layer (`zenzic.core.regex`), guaranteeing $O(N)$ execution time and mathematical immunity to Regular Expression Denial of Service (ReDoS).
- **Pure-Function Determinism**: Analysis has zero global state and zero network dependencies, guaranteeing bit-for-bit identical results on every machine and operating system.

---

## 🛠️ CLI Commands & Tooling Capabilities

The `zenzic` CLI provides a complete suite of developer commands for local workflows, batch remediation, and CI/CD automation:

| Command | Primary Use Case | Key Options |
| :--- | :--- | :--- |
| `zenzic check` | Run graph integrity, security, and quality analysis | `all`, `--strict`, `--fail-under <N>`, `--format sarif` |
| `zenzic fix` | Automatically apply idempotent AST mutations | `--dry-run`, `--apply` |
| `zenzic score` | Calculate DQS metrics and update status badges | `--stamp`, `--check-stamp`, `--badge-json` |
| `zenzic audit` | Generate formal compliance and technical debt reports | `--format markdown`, `--output <file>` |
| `zenzic lab` | Interactive finding lab and scenario runner | `list`, `run <act-id>`, `inspect <act-id>` |
| `zenzic init` | Scaffold `.zenzic.toml` configuration or plugin template | `--pyproject`, `--local`, `--engine <name>`, `--plugin` |
| `zenzic config explain` | Introspect active policies, discovery paths, and rules | `--all`, `--json` |

---

## 📊 Headless Data Pipeline (SARIF v2.1.0)

Zenzic functions natively as a headless data compiler. For enterprise security and code scanning pipelines, Zenzic exports industry-standard **SARIF v2.1.0** (Static Analysis Results Interchange Format):

```bash
# Output enriched SARIF for CI/CD ingestion
zenzic check all --format sarif --output results.sarif
```

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "zenzic",
          "version": "0.30.0",
          "rules": [
            {
              "id": "Z101",
              "shortDescription": { "text": "BROKEN_LOCAL_LINK" }
            }
          ]
        }
      }
    }
  ]
}
```

Every SARIF diagnostic includes:

- Precise 1-indexed line and column ranges.
- Deductive DQS score penalty and taxonomy category.
- Direct documentation remediation URLs (`helpUri`).
- Full rule descriptions and severity ratings (`error`, `warning`, `note`).

Seamlessly feeds directly into **GitHub Code Scanning**, **SonarQube**, **GitLab SAST**, and **DefectDojo**.

---

## 🔌 Multi-Engine Support & VSM Adapters

Documentation frameworks use varying link slugification, asset pathing, and directory index conventions. Zenzic bridges these differences through its **Virtual Site Map (VSM) Adapter Architecture**:

- **MkDocs & Material for MkDocs**: Parses `mkdocs.yml`, navigation hierarchies, and Material anchor slugification natively without invoking Python subprocesses.
- **Zensical**: Validates multi-language document hierarchies and configuration trees.
- **Standalone / Standard Markdown**: Performs universal link and asset resolution across any arbitrary directory structure.

---

## 🚦 CI/CD Enforcement & Exit Code Contract

Under **ADR-075 (Radical Unawareness)**, Zenzic guarantees a strict exit code contract that CI/CD systems can rely on deterministically:

| Exit Code | Meaning | CI Behavior |
| :--- | :--- | :--- |
| **`0`** | **Success** | All checks passed, or warnings managed within suppression budget. |
| **`1`** | **Quality Gate Failure** | Broken links, structural defects, or DQS score below `fail_under`. |
| **`2`** | **Fatal Credential Leak** | Leaked secrets or API keys. Non-suppressible security block. |
| **`3`** | **Fatal Path Traversal** | Directory traversal sequence detected. Non-suppressible security block. |

---

## 🌐 The Unified Zenzic Ecosystem

Zenzic provides consistent, identical analysis across every development touchpoint:

| Platform | Primary Use Case | Delivery |
| :--- | :--- | :--- |
| **[Zenzic CLI (Core)](https://github.com/PythonWoods/zenzic)** | Local development, batch auto-fixes, and scriptable audits | `uv tool install zenzic` |
| **[VS Code Extension][zenzic-vscode]** | Real-time wavy-line diagnostics, LSP Quick Fixes (`Ctrl+.`), and status telemetry | [VS Code Marketplace][zenzic-vscode] |
| **[GitHub Action][zenzic-action]** | CI/CD pull request gate, SARIF Code Scanning alerts, and merge blocking | [GitHub Marketplace][zenzic-action] |

---

## 📖 Documentation & Guides

- **[Quick Start Tutorial](https://zenzic.dev/tutorials/first-audit/)**: Step-by-step introduction.
- **[Finding Codes Catalog](https://zenzic.dev/docs/reference/finding-codes/)**: Complete reference for all `Z1xx`–`Z6xx` finding codes.
- **[Policy-as-Code Guide](https://zenzic.dev/docs/how-to/configuration-strategy/)**: Enforce repository standards.
- **[Custom Rule SDK v3](https://zenzic.dev/docs/developers/how-to/write-ast-rule/)**: Author deterministic, typed Python linting plugins.
- **[CI/CD Configuration](https://zenzic.dev/docs/how-to/configure-ci-cd/)**: Set up automated GitHub Actions pipelines.

For deep architectural explanations, configuration strategies, and the full finding taxonomy, visit [zenzic.dev](https://zenzic.dev).

---

## 🗺️ Roadmap

Zenzic evolves strictly within its deterministic, AST-driven architecture. Upcoming milestones include:

- **Adapter Ecosystem**: Native Virtual Site Map (VSM) adapters for **Docusaurus**, **Sphinx (MyST)**, and **Hugo** to support cross-engine slugification and taxonomy out of the box.
- **Multi-Repository Documentation Graph**: Cross-repository link resolution and contract validation across polyrepo documentation architectures without network calls.
- **Auto-Fix Expansion**: Extended lossless AST mutations for additional structural codes (`Z1xx`), reference normalization (`Z3xx`), and frontmatter standardization (`Z6xx`).

---

## 📄 License

Licensed under the [Apache License, Version 2.0](LICENSE).
Copyright (c) 2026 PythonWoods `<dev@pythonwoods.dev>`.

<!-- Link Definitions -->
[zenzic-vscode]: https://github.com/PythonWoods/zenzic-vscode
[zenzic-action]: https://github.com/PythonWoods/zenzic-action
