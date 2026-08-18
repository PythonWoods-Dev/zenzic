---
title: "Auto-Fix Philosophy & Controlled Degradation"
description: "The architectural principles governing deterministic auto-remediation, structural healing, and controlled semantic degradation in Zenzic."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Auto-Fix Philosophy and Controlled Degradation

Zenzic approaches automated remediation through the principle of **Controlled Degradation**. Automated code and prose fixes must never rely on probabilistic inference, guess author intent, or silently introduce hidden assumptions into production documentation.

Instead, Zenzic separates **structural correctness** from **semantic meaning**, using atomic transformations to heal document syntax while forcing human-in-the-loop triage for editorial decisions.

---

## The Controlled Degradation Lifecycle

The remediation lifecycle transitions defects from invisible structural failures into visible, trackable semantic debt:

```text
┌──────────────────────────────────────────────┐
│  Empty Link: [](https://...)                 │
│  [Z108] Invisible Structural Error           │
│  (Inaccessible, unclickable in HTML)         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼  zenzic fix --apply (Atomic Mutator)
┌──────────────────────────────────────────────┐
│  Beacon Link: [TODO](https://...)            │
│  [Z108 Fixed] -> HTML AST Structure Restored │
│  [Z501 / Z617] Visible Semantic Debt         │
│  (Intentional CI block before merge)         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼  Human-in-the-Loop Triage
┌──────────────────────────────────────────────┐
│  Final Link: [Official Guide](https://...)   │
│  Total Integrity (DQS 100/100)               │
└──────────────────────────────────────────────┘
```

---

## Core Pillars of the Remediation Contract

The Zenzic remediation engine operates across three fundamental architectural pillars to balance automated productivity with strict content governance:

### 1. Structural Blindness Resolution

An empty Markdown link `[](https://example.com)` is an invisible defect. In rendered HTML, browsers may collapse the link entirely or render an unclickable zero-width bounding box. More critically, screen readers cannot announce an empty link, breaking the Accessibility Object Model (AOM).

The Atomic Mutator (`zenzic.core.mutator`) resolves structural blindness by inserting a valid text node, restoring the integrity of the document Abstract Syntax Tree (AST).

### 2. The Visual Beacon

Zenzic is built on deterministic static analysis (**ADR-002 Zero Subprocesses** and zero runtime inference dependencies). The engine does not guess what the author meant to write.

By inserting a standardized, prominent placeholder token, the Mutator establishes a visual beacon. The defect is elevated from an invisible parsing flaw into an explicit, visible item requiring author review.

### 3. Intentional Fail-Fast under Strict Governance

When organizations configure strict Policy-as-Code rules—such as [`Z501` (Placeholder Content)](../rules/Z501.md) or [`Z617` (Forbidden Content Patterns)](../rules/Z617.md) configured with `forbidden_content_patterns = ["(?i)\\btodo\\b"]`—the CI/CD pipeline intentionally halts on the generated beacon.

This controlled cascade is an architectural feature:

- The structural error ([`Z108`](../rules/Z108.md)) is healed automatically.
- The pipeline prevents unreviewed placeholder text from reaching production.
- The human author is guided directly to the exact file and line to supply authoritative copy.

---

## Idempotence and Lossless Invariants

All transformations applied by `zenzic fix` adhere to strict mathematical invariants:

1. **Lossless Round-Trip**: Unmodified sections, custom HTML comments, and fence formatting remain identical byte-for-byte.
2. **Strict Idempotence**: Running `zenzic fix --apply` multiple times produces the exact same AST state as running it once:
   $$\text{mutate}(\text{mutate}(\text{AST})) = \text{mutate}(\text{AST})$$
3. **Parity Between CLI and IDE**: The exact same `Mutator` routines power both the CLI automated fixer and the VS Code LSP Quick Fixes (`WorkspaceEdit`).
