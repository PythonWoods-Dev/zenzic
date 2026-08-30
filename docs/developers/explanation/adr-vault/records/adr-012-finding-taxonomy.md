---
description: "Architectural Decision Record for the Z0xx-Z6xx numeric finding-code taxonomy: one category axis per hundred-block, frozen and immutable once assigned."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 012: Finding Taxonomy

This document details the architectural specification and contract for ADR 012: Finding Taxonomy within the Zenzic ecosystem.

---

## Context

Every finding Zenzic emits carries a stable, machine-readable code of the form `Zxxx`. As the number of checks grew, findings needed a categorization scheme that a caller (a CI script filtering by severity class, a custom-rule author picking an unused code, a reader of `docs/reference/finding-codes.md`) could rely on without reading every individual code's description. A code's leading digit alone should tell you what *kind* of problem it represents.

This is a distinct concern from the Namespace Contract's tier-ownership model (Core/Governance/Plugin/Custom — *who* owns a given code), documented separately. This ADR governs the numeric category axis only: *what kind* of finding a code represents, independent of who defined it.

---

## Decision

Finding codes are grouped into fixed hundred-blocks, each one category:

- **Z0xx** — Configuration Guard (pre-analysis structural/schema errors)
- **Z1xx** — Link Integrity (broken links, anchors, HTML link attributes, configuration validation)
- **Z2xx** — Security (credential scanner, path traversal, forbidden schemes/terms)
- **Z3xx** — Reference Integrity (Markdown reference-style link definitions)
- **Z4xx** — Navigation & Structure (orphan pages, nav contracts, topological reachability)
- **Z5xx** — Content Quality & Specification-Driven Development (readability, table/heading contracts, SDD validation)
- **Z6xx** — Governance (Policy-as-Code: brand terms, frontmatter policy, cross-namespace rules)

`src/zenzic/core/codes.py`'s module docstring is this taxonomy's single source of truth and the canonical reference for every currently assigned code — this ADR records the *decision* the registry implements, not a duplicate listing that could drift from it.

A frozen code identity, once assigned, is never reused or semantically reassigned to a different category — a retired code's number is retired with it, not recycled.

---

## Rationale

A caller filtering findings by leading digit (`Z2*` for every security-class finding, regardless of which specific check produced it) needs that grouping to be structural, not incidental — a new check added to the wrong hundred-block would silently break every consumer relying on the category boundary. Fixing the category axis as an explicit, documented decision, with a single canonical registry (`codes.py`) rather than scattered per-check judgment calls, keeps that boundary stable as the check surface grows.

Freezing code identity (no reuse, no reassignment) exists for the same reason `NON_SUPPRESSIBLE_CODES`/`FROZEN_CODES` exist for the security tier specifically: a tool or CI script that hardcodes a check for `Z201` must be able to trust that code has always meant, and will always mean, the same thing.

---

## Invariants

- Every finding code's leading digit places it in exactly one of the seven categories above; no code spans or straddles two categories.
- `src/zenzic/core/codes.py`'s module docstring is the canonical, single source of truth for the current code registry — any other document listing codes (`docs/reference/finding-codes.md`, `.claude/references/03-dqs-and-mirror-law.md`) must match it, not restate an independent copy that could drift.
- A retired or removed finding code's number is never reassigned to a semantically different check.

---

## Consequences

- Any consumer (CI script, custom tooling, a reader of the docs) can reliably filter or reason about findings by leading digit alone, without needing to know which specific check produced a given code.
- Adding a new check requires placing it in the correct existing hundred-block (or, if it belongs to none, an explicit decision to extend this ADR with a new block) rather than an ad hoc number choice.
- This ADR governs the numeric category axis only. The tier-ownership model (which party — Core, Governance, Plugin, or Custom — is responsible for a given code) is a separate, orthogonal concern documented independently; a code's category here does not imply anything about who owns it.
