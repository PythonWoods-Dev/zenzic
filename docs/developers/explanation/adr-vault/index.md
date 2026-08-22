---

description: "The complete index of Zenzic Architectural Decision Records — every major technical choice, its context, and its permanent consequences."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR Vault

> *"A tool that works for mysterious reasons is not a tool — it is a ritual.
> Zenzic works for documented reasons. This vault is the proof."*

This page is the complete index of **Architectural Decision Records (ADRs)** for
the Zenzic project. Each ADR documents a major technical decision: its context
(why the problem existed), its decision (what was chosen), and its invariants
(what must never change as a consequence).

For day-to-day contribution flow, release checks, and governance enforcement,
follow the operational runbook instead:

- [Developer Release and Governance Protocol](../../how-to/release-governance-protocol.md)

ADRs are the **immutable memory** of the project. They explain not only what
Zenzic does, but why. Operational behavior at commit and push time is governed
by the Developer Release and Governance Protocol.

---

## Genesis Decisions

These ADRs define the philosophical and technical foundations on which all
subsequent decisions rest.

| ADR | Title |
|-----|-------|
| [ADR 001](./records/adr-lint-source.md) | Lint the Source, Not the Build |
| [ADR 002](./records/adr-002-zero-subprocesses.md) | Zero Subprocesses Policy *(Maintainer Only)* |

---

## Core Architecture Decisions

These ADRs document the structural decisions for the current architecture.

| ADR | Title |
|-----|-------|
| [ADR 003](./records/adr-discovery.md) | Root Discovery Protocol |
| [ADR 004](./records/adr-decentralized-cli.md) | Decentralized CLI Package |
| [ADR 005](./records/adr-agnostic-universalism.md) | Z404 Agnostic Universalism |
| [ADR 007](./records/adr-007-sovereign-sandbox.md) | Sovereign Sandbox *(Maintainer Only)* |
| [ADR 008](./records/adr-bilingual-structural.md) | Bilingual Structural Invariant *(Deprecated)* |
| [ADR 009](./records/adr-path-sovereignty.md) | Path Sovereignty |
| [ADR 013](./records/adr-regex-acl.md) | The Regex Anti-Corruption Layer (ReDoS Protection) |
| [ADR 015](./records/adr-native-telemetry.md) | Native Telemetry Validation |
| [ADR 020](./records/adr-020-mirror-law.md) | Mirror Law |
| [ADR 021](./records/adr-021-parallel-audit.md) | Parallel Audit Completeness vs. Fail-Fast |
| [ADR 022](./records/adr-022-english-only-governance.md) | English-Only Governance & Deprecation of Bilingual Invariant |
| [ADR 075](./records/adr-075-radical-unawareness.md) | Radical Unawareness |
| [ADR 090](./records/adr-090-silent-on-success-unix-philosophy.md) | Silent-on-Success Unix Philosophy & Pipeline Signal Protocol |
| [ADR 091](./records/adr-091-single-pass-ast-and-cqs.md) | Single-Pass AST Compilation & Command-Query Segregation (CQS) |
| [ADR 092](./records/adr-092-comprehensive-bump-coverage.md) | Comprehensive Release Bump Coverage |
| [ADR 093](./records/adr-093-topological-suppression-non-inline.md) | Topological Suppression Non-Inline Invariant & LSP UX Determinism |

---

## Documentation Site Decisions

These ADRs document architectural decisions specific to this documentation site
(`zenzic.dev`) — choices about how the Docusaurus site is built, localized, and
maintained.

| ADR | Title |
|-----|-------|
| [ADR 006](./records/adr-unified-perimeter.md) | Unified Scan Scope (Storage + Blog) |

---

## Reading Guide

Each ADR follows a consistent structure:

- **Context** — the problem that existed before the decision was made. Reading

  the Context of an ADR tells you what pain the decision was eliminating.

- **Decision** — the choice that was made, stated precisely and without

  ambiguity. If you ever wonder "why does Zenzic do X?", the Decision section
  of the relevant ADR is the answer.

- **Rationale** — the engineering reasoning behind the decision. This section

  is the "why not the alternative?" — it records the rejected approaches and
  explains why they were insufficient.

- **Invariants** — the constraints that must never be violated as a consequence

  of the decision. These are permanent. They do not expire with version
  increments. A PR that violates an invariant listed in an ADR is an automatic
  revert candidate, regardless of its other merits.

- **Consequences** — the known trade-offs and capabilities that the decision

  enables or forecloses. Reading Consequences helps contributors understand the
  boundaries of what Zenzic can and cannot do by design.

---

## Adding a New ADR

For the step-by-step procedure on how to propose and record a new Architectural Decision Record, see the [ADR contribution guide](../../how-to/release-governance-protocol.md#8-adding-a-new-adr).
