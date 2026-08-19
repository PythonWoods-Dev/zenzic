---
title: "The Namespace Contract"
date: 2026-05-24
authors:
  - pythonwoods
description: "The Namespace Contract"
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

The system is built on a contract: explicit tier boundaries, frozen security guarantees,
and a machine-consumable route surface for external tools.

<!-- more -->

Italian version available in the Italian locale mirror of this article.

---

## Source Integrity Before Build Integrity

Build engines and static analyzers solve different phases of the problem:

- Build engines validate renderability after full site compilation.
- Zenzic validates source integrity before compilation.

### Four hard facts

| Topic | Typical SSG Build Flow | Zenzic |
|:--|:--|:--|
| Shift-Left and speed | Full compile loop (Node.js/Go/Python stack), usually CI-bound and minute-scale feedback. | Pre-commit local analysis on source text and metadata, millisecond-scale feedback for targeted checks. |
| Security | A build can succeed while secrets remain committed in source files. | Security Core enforces security-tier findings (`Z2xx`) and stops the pipeline on security exits. |
| Governance | No native concept of brand obsolescence or translation parity drift. | Governance codes enforce policy explicitly (`Z601` brand obsolescence, `Z602` i18n parity). |
| Actionable diagnostics | Generated-route failures often surface as generic 404/build errors. | VSM reverse mapping links the failing virtual route to concrete source files/frontmatter context. |

### Execution-time characteristics (architectural)

Zenzic's analysis complexity is $O(N)$ in the number of files and links scanned.
All pattern matching runs on the RE2 DFA engine, which guarantees linear time and
is immune to catastrophic backtracking (ReDoS). There is no Node.js build-pipeline
startup overhead for this pre-build analysis, but Python runtime dependencies must
be installed (including RE2 bindings) and execution runs in the current Python process.

The phase difference relative to a full SSG build (which compiles, bundles, and
emits routes) does not vary by environment — Zenzic always runs before the build
engine is available.

---

## The Namespace Contract

Zenzic introduces an explicit tier model for findings and ownership.

| Tier | Ownership | Purpose |
|:--|:--|:--|
| Core | Engine invariants | Structural and safety-critical contracts required by the core runtime. |
| Governance | Project policy | Cross-repository quality contracts such as naming, parity, and lifecycle policy. |
| Plugin | Extension packages | Third-party rule surfaces loaded via plugin entry points. |
| Custom | Local rules | Team-specific constraints declared in project configuration. |

### Why frozen codes exist

Security is not a style preference. It is a non-negotiable contract.

Zenzic formalizes frozen security semantics through immutable code surfaces such as:

- `FROZEN_CODES`
- `NON_SUPPRESSIBLE_CODES`
- `PLUGIN_FORBIDDEN_EXITS`

The practical implication is simple:

- Security findings like `Z201` or `Z204` are not optional suggestions.
- They cannot be downgraded into decorative warnings by local convenience flags.
- CI and local gates converge on the same enforcement semantics.

---

## Open Ecosystem: JSON API Integration

Zenzic exposes route truth as a machine interface:

```bash
zenzic inspect routes --json
```

This output is not presentation text. It is deterministic route metadata for automation.

External tools can consume this JSON directly:

- Independent structural analysis systems.
- Automation tools that need architectural context.
- CI orchestrators that require stable, typed diagnostics.

This removes fragile text scraping from the workflow. Tools consume contracts, not prose.

---

## Bottom line

The system closes a long-standing gap in documentation QA:

- Build validity is no longer mistaken for source integrity.
- Security is enforced as contract, not convention.
- Governance is explicit and testable.
- Virtual-route failures are traced to physical origin, not buried in generic 404 output.

That is the end of the SSG illusion.

---

## Publication Decree: Sovereign Transition

The Sovereign Transition is now formally declared as:

> "The Sovereign Transition. Introducing Suppression CAP, Local Sanctuary, and Avion-Grade Governance."

The system is operational as fleet standard. The initial rollout dashboard can now be archived,
and repository tagging proceeds under the new protocol.
