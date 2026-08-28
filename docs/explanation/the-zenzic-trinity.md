---
title: "The Zenzic Trinity: Code, Doc, and Action"
description: "How the three Zenzic repositories form a Trinity of Integrity — a sovereign knowledge system where logic, intent, and enforcement are permanently synchronized."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## The Zenzic Trinity: Code, Doc, and Action

Zenzic is a **Sovereign Knowledge System** — an ecosystem where
logic, intent, and enforcement are permanently synchronized. To deliver a true
[Exclusion Zone](./privacy-gate.md), Zenzic is organized into a Trinity of Integrity: three
repositories that form a closed feedback loop, each reinforcing the others.

---

## 1. The Core — The Body {#core-the-body}

The [`zenzic`](https://github.com/PythonWoods/zenzic) repository is the **tactical execution
layer**. It contains every line of analysis logic that enforces the Three Pillars.

| Component | Role |
|-----------|------|
| **Virtual Site Map (VSM)** | Builds an in-memory projection of the final site from source files alone. No build required. |
| **Credential Scanner** | Scans every line of raw source for credential patterns before any other pass. |
| **Adapter Protocol** | Translates engine-specific configuration (MkDocs, Zensical, Standalone) into a unified analysis model. |
| **Layered Exclusion Manager** | Unifies system guardrails, forced inclusions, CLI overrides, VCS ignores, and user configuration into a single, deterministic pass hierarchy to guarantee a clean scan scope. |

The Core enforces the law. It does not decide the law.

### Why Zenzic if my Static Site Generator (SSG) already checks for broken links?

1. **Speed & Shift-Left:** SSG builds (Node.js, Go, or Python based) require full site compilation and commonly run in slower CI feedback loops. Zenzic runs local static analysis on source text and metadata before build, with pre-commit feedback in milliseconds.
2. **Security:** Native SSG checks do not block credential leaks or path-traversal attempts at commit time. Zenzic enforces security findings in the `Z2xx` tier and blocks on security exits.
3. **Governance:** SSGs do not enforce governance contracts such as brand obsolescence (`Z601`), or orphaned assets (`Z405`). Zenzic exposes these as explicit, auditable contracts.
4. **Actionable Diagnostics:** When generated routes fail, SSG output is typically a generic 404/build failure. Zenzic uses VSM reverse mapping to report the exact source file and frontmatter context that generated the failing virtual route.

---

## 2. The Documentation — The Soul {#documentation-the-soul}

The [`zenzic-doc`](https://github.com/PythonWoods/zenzic-doc) repository is the project's
**Constitutional Layer**. It is not merely a user manual — it is the source of truth that defines
*why* the engine exists and *why* every rule is the way it is.

### The Diátaxis Framework

Content is organized into four strict quadrants: **Tutorials** (learning), **How-to Guides**
(tasks), **Reference** (exhaustive data), and **Explanation** (understanding). This prevents
content drift: every contributor always knows exactly where a new piece of knowledge belongs.

### Architectural Decision Records (ADRs)

Every major technical choice is codified in an ADR stored under
`developers/explanation/`. Each record states the problem, the decision, the
rationale, and the permanent consequences. The ADRs are the project's institutional memory —
the written proof that no decision was made carelessly.

The ADR corpus ensures the Exclusion Zone philosophy remains stable over time, regardless of who
contributes to the project in the future.

---

## 3. The Action — The Arm {#action-the-arm}

The [`zenzic-action`](https://github.com/PythonWoods/zenzic-action) repository is the
**operational layer**. It translates the Core's logic into a validation boundary for real-world
CI/CD pipelines.

```yaml title=".github/workflows/zenzic.yml"

- uses: PythonWoods/zenzic-action@<version>

  with:
    version: "<version>"
    format: sarif
    upload-sarif: true
    fail-on-error: true
```

The Action exposes the Core's [exit code contract](../reference/finding-codes.md) directly to
GitHub Actions runners: quality findings (exit 1) are configurable; security incidents
(exit 2/3) are **never suppressible**. The CI gate is mathematically identical to the local gate.

---

## The Feedback Loop {#feedback-loop}

The Trinity is not a hierarchy — it is a **cycle**. Each repository informs and constrains the
others:

```mermaid
flowchart TD
    Core["<b>Zenzic Core</b><br>Enforces rules defined by the Soul"] -->|"Implementation review"| Soul["<b>The Soul (Documentation & ADRs)</b><br>Records architectural invariants"]
    Soul -->|"Invariants & policies"| Action["<b>Action (Delivery & CI/CD)</b><br>Deploys Core to the ecosystem"]
    Action -->|"Real-world failures & telemetry"| Core

    style Core fill:#4f46e5,stroke:#4338ca,color:#ffffff,stroke-width:2px
    style Soul fill:#0284c7,stroke:#0369a1,color:#ffffff,stroke-width:2px
    style Action fill:#10b981,stroke:#059669,color:#ffffff,stroke-width:2px
```

A change to the Core that is not reflected in the Soul is a **ghost commit**. An Action that
exposes behaviour not documented in the Soul is a **silent contract**. The Trinity is only
complete when all three are in synchronisation — which is enforced by the [Law of Contemporary Testimony](../developers/explanation/governance/evolution_policy.md).

---

## Architectural Awareness {#architectural-awareness}

Zenzic is engineered for **Institutional Memory**. Two properties make this possible:

### Deterministic Rule Surface — The Structural Mirror

The `zenzic` core exposes a deterministic rule surface through its code registry,
finding catalog, and adapter contracts. Structural state is read from explicit
registries and stable command outputs (`inspect capabilities`, `inspect codes`,
`inspect routes`) rather than inferred from runtime heuristics.

### ADR Corpus — The Decision Mirror

Every architectural choice lives in a structured Markdown file. `## Context` and `## Decision`
are universal across the ADR corpus; most records also carry `## Rationale` (or, in a minority,
`## Consequences`) and a `**Status:**`/`**Date:**` metadata line, though the exact metadata
fields aren't fully standardized across every record yet. This makes the decision history
readable and traceable by design, even where the metadata schema is still converging.

Together, the deterministic rule surface and the ADR corpus form a **transparent context layer**:

- **For humans:** a clear, predictable path from philosophy to implementation — no archaeology

  required.

- **For automation systems:** a structured, unambiguous context that keeps generated

  suggestions aligned with the project's fundamental invariants.

!!! info The Exclusion Zone is a Sovereign Knowledge System
    Zenzic is not just a tool you use. It is an ecosystem you can trust — because its rules,
    decisions, and structure are always legible, always synchronized, and always honest.
