---
title: "Zenzic v0.31.0: Specification-Driven Development & AI Knowledge Graph Integrity"
slug: zenzic-v0310-specification-driven-development
date: 2026-08-22
authors:
  - pythonwoods
description: >
  Zenzic v0.31.0 introduces Specification-Driven Development (SDD): native Table AST parsing,
  declarative table column enforcement (Z521), cell value enums (Z522), heading sequence validation (Z523),
  and multi-namespace graph traceability (Z412) to protect knowledge graphs from AI hallucinations.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

AI coding agents — regardless of which one you use — are remarkably good at writing Markdown that *looks* correct. The prose reads well. The headings are grammatically sound. The tables render cleanly in your editor preview. And yet, somewhere in that confident output, a required column silently disappeared.

Here's a real shape of the problem: an agent is asked to add a new endpoint to an API reference table. It does. But the table it regenerates looks like this:

```markdown
| Endpoint | Method |
| :--- | :--- |
| /v1/users | GET |
| /v1/sessions | POST |
```

Looks fine, right? Except the original contract for that table required an `Auth` column — every endpoint needs to document whether it's public, requires a bearer token, or needs an admin scope. The agent generated a plausible, well-formatted table. It just didn't know, and had no way of enforcing, that `Auth` was a mandatory field in *this specific table*, in *this specific document*. Nothing in Markdown syntax says a table must have a given column. Nothing in prose grammar catches it either. The PR looks clean, CI is green, and the missing column ships straight into your architecture docs — where a downstream engineer, or another agent, reads the table, assumes it's complete, and builds against an endpoint they think is public.

This is not a hypothetical edge case. It's a direct consequence of how these tools work: an AI agent generates output based on local context and pattern-matching against nearby examples, not against a formally declared schema for your repository's documentation. Multiply this across dozens of tables, hundreds of headings, and a growing set of specification documents that are supposed to stay traceable to your architecture records, and you get a slow, silent erosion of your knowledge graph's integrity — one plausible-looking PR at a time. This is **the knowledge graph integrity gap**, and it is the engineering bottleneck Zenzic v0.31.0 is built to close.

Zenzic v0.31.0 delivers **Specification-Driven Development (SDD)** — turning your Markdown documentation into a strictly typed, topologically verified data model.

<!-- more -->

---

## Why Deterministic Static Analysis, Not LLMs

A common modern instinct is to prompt an LLM to "review documentation quality" on every pull request. In production engineering, this approach fails on three fundamental axes:

1. **Latency & Execution Speed**: Zenzic compiles and validates hundreds of Markdown files in under 15 milliseconds via a single-pass $O(N)$ AST and Virtual Site Map (VSM) topology. An LLM review takes 5 to 15 seconds per file, creating unacceptable CI pipeline bottlenecks.
2. **Zero Inference Cost**: Zenzic runs locally, in pre-commit hooks, and in CI/CD with zero API keys, zero token fees, and zero external network calls.
3. **Deterministic CI Contracts**: Static analysis produces reproducible, bit-exact exit codes (`0` for clean, `1` for quality, `2` for security leaks, `3` for traversal incidents) and a mathematically verified Document Quality Score (DQS). LLM evaluations are stochastic, non-reproducible, and prone to the very hallucinations they are tasked to detect.

---

## The Modern Documentation Stack

Zenzic fits alongside your existing formatting and prose tooling without overlap:

| Capability / Layer | Syntax Formatters | Prose Linters | Zenzic (DQP / SDD Engine) |
| :--- | :---: | :---: | :---: |
| **Markdown Syntax & Whitespace** | :material-check-circle:{ .zenzic-score-100 } Native | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Delegated to Formatters |
| **Spelling & Natural Language Grammar** | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native | :material-minus-circle-outline: Complementary / Compatible |
| **Lightweight Editorial Policy**¹ | :material-minus-circle-outline: Out of Scope | :material-alert-circle-outline: Requires External Rules | :material-check-circle:{ .zenzic-score-100 } Built-in Opt-In (`[policies]`) |
| **AST Table Contract Enforcement (Columns/Enums)** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native SDD Engine (`Z521`, `Z522`) |
| **Heading Structure & Sequential Templates** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native SDD Engine (`Z523`) |
| **Multi-Namespace Graph Traceability** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native VSM Topology (`Z412`) |
| **Zero-Leak Secret & Privacy Gate (Exit 2/3)** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native Security Engine (`Z201`–`Z205`) |
| **Deterministic DQS Mathematical Score (0–100)** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native Algorithmic Ledger |

¹ *Note: Zenzic's editorial policy checks (such as passive voice `Z518` and weasel words `Z519`) are lightweight RE2-based regex heuristics designed for fast CI guardrails, not full natural language grammar parsing.*

---

## The SDD Architecture: Beyond Syntax and Grammar

Traditional documentation linters operate on isolated source files, checking whitespace or dictionary spelling. Zenzic treats documentation as a compiled, interconnected graph.

```text
  AI Agents / Engineers ───> Markdown Specs ───> [ ZENZIC COMPILER ] ───> Verified Knowledge Graph
                                                   │
                                                   ├── O(N) AST Table & Semantic Validation
                                                   ├── Virtual Site Map (VSM) Topo-Routing
                                                   ├── Multi-Namespace Graph Traceability
                                                   └── Zero-Tolerance Security Gates (Exit 2/3)
```

With v0.31.0, the core parser expands with a first-class **Table Abstract Syntax Tree (AST)** that represents GitHub Flavored Markdown (GFM) tables with zero subprocess overhead, byte-for-byte lossless round-tripping, and strict RE2 non-backtracking safety.

---

## The Four New SDD Integrity Rules

To enforce rigorous data contracts across Markdown knowledge bases, Zenzic v0.31.0 adds four purpose-built diagnostic rules spanning AST content semantics and global graph topology:

### 1. Mandatory Table Columns ([`Z521`](../../rules/Z521.md))

In technical specifications, Markdown tables often represent formal contracts: API endpoints, database schemas, or test matrices. Missing required headers breaks automated scrapers and human workflows.

[`Z521`](../../rules/Z521.md) enforces required column headers across all tables or scoped under specific heading contexts:

```toml
[policies.required_table_columns]
"*" = ["Status", "Description"]
"^API Reference$" = ["Method", "Endpoint", "Auth"]
```

```markdown
<!-- Emits Z521: missing required 'Status' column -->
| Endpoint | Method |
| :--- | :--- |
| /v1/users | GET |
```

---

### 2. Table Cell Enum Whitelisting ([`Z522`](../../rules/Z522.md))

When tables document lifecycle stages, severity levels, or protocol states, informal strings like `unverified`, `unknown_status`, or `in-progress` degrade data fidelity.

[`Z522`](../../rules/Z522.md) validates that cells under designated columns contain only approved enumerated values:

```toml
[policies.table_cell_enums]
"Status" = ["draft", "review", "stable", "deprecated"]
```

```markdown
<!-- Emits Z522: 'unknown_status' is not in ['draft', 'review', 'stable', 'deprecated'] -->
| Feature | Status |
| :--- | :--- |
| AST Engine | unknown_status |
```

---

### 3. Strict Heading Sequence Order ([`Z523`](../../rules/Z523.md))

Consistent cognitive structure is vital across large documentation repositories. When AI models generate documentation, they often reorder foundational sections, placing technical references before overviews or prerequisites.

[`Z523`](../../rules/Z523.md) enforces that headings appear in strictly ascending sequential order:

```toml
[policies]
required_heading_order = [
    "^Overview$",
    "^Prerequisites$",
    "^Installation$",
    "^Usage$",
    "^API Reference$"
]
```

```markdown
<!-- Emits Z523: 'Overview' appears after 'API Reference' -->
# API Reference
...
# Overview
...
```

---

### 4. Cross-Namespace Graph Traceability ([`Z412`](../../rules/Z412.md))

In complex engineering projects, specifications and Architectural Decision Records (ADRs) must be bidirectionally traceable to system architecture documents. An untraceable specification is an isolated orphan disconnected from the system's living graph.

[`Z412`](../../rules/Z412.md) cross-validates the Virtual Site Map (VSM) incoming link graph, ensuring that all target specification documents receive at least one incoming reference from approved source namespaces:

```toml
[policies.traceability_targets]
"specs/**" = ["architecture/**", "epics/**"]
"adrs/**" = ["rfcs/**"]
```

If a document matching `docs/specs/auth-sdd.md` lacks inbound links from `docs/architecture/**` or `docs/epics/**`, Zenzic emits `Z412 TRACEABILITY_BROKEN`.

---

## Ecosystem-Wide Parity & The 10-Target Mirror Law

Like all Zenzic capabilities, Specification-Driven Development is governed by the **Mirror Law (ADR-020)** — ensuring 100% synchronous parity across all 10 mandatory targets (Core codes, Scorer, Scoring documentation, Finding Codes catalog, Rule Specification Cards, MkDocs navigation, Lab scenarios, `zenzic init` templates, VS Code IntelliSense schemas, and Test suites):

1. **Zenzic CLI**: Fast terminal execution (`zenzic check all`) with rich terminal diagnostics, SARIF v2.1.0 output, and DQS scoring.
2. **VS Code Extension (LSP)**: Instant real-time diagnostic squiggles inside VS Code as you edit Markdown tables or reorder headings, backed by the updated `zenzic.schema.json`.
3. **GitHub Actions (`zenzic-action`)**: Zero-config CI/CD quality gate (`v2`) stopping untraceable or malformed specifications on pull requests.

---

## Try It in 30 Seconds

The fastest way to see this on your own repository is the pre-commit hook — no global install, no environment pollution, just an isolated, pinned check on your staged files:

<!-- Publication gate: do not publish before the v0.31.0 tag exists on GitHub. -->

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      - id: zenzic-guard
```

(`rev:` should track the latest tagged release rather than being copy-pasted indefinitely — check the repository's release tags before pinning.)

If you just want to point Zenzic at a repository for a one-off local test without adding it to your workflow yet, you can run it ephemerally with `uvx`, pinned to a specific version:

```bash
# One-off local test only — not the recommended default workflow
uvx zenzic@0.30.0 check all
```

Add your project's SDD policies to `.zenzic.toml`:

```toml
[policies]
required_heading_order = ["^Overview$", "^API Reference$"]

[policies.required_table_columns]
"*" = ["Status", "Description"]

[policies.table_cell_enums]
"Status" = ["draft", "review", "stable"]

[policies.traceability_targets]
"specs/**" = ["architecture/**"]
```

Run `zenzic check all` to verify your documentation graph. See [Deterministic Tooling & The Pre-Commit Distribution Model](2026-08-23-deterministic-tooling-and-pre-commit.md) for the full three-track distribution hierarchy, including project-dependency and pre-push tiers.
