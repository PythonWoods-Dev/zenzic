---
description: "Architectural Decision Record mandating immutable 40-character commit SHA pinning for GitHub Action `uses:` references and pre-commit `rev:` keys across all three Zenzic ecosystem repositories."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 089: Ecosystem-Wide Immutable SHA Pinning

This document details the architectural specification and contract for ADR 089: Ecosystem-Wide Immutable SHA Pinning within the Zenzic ecosystem.

---

## Context

Local development drift and unpinned network dependencies compromise software supply chain security. When a CI/CD workflow references a GitHub Action or a pre-commit hook by a mutable tag (`@v4`, `@main`, `@just`) rather than an immutable identifier, the exact code that executes on a given run is not guaranteed to match what was reviewed. A tag can be repointed at different content after review, with no change visible in the consuming repository's own diff.

The original phrasing of this invariant ("all GitHub Action workflows and submodules") was ambiguous about whether it covered only the core `zenzic` repository or the full ecosystem, including the satellite repositories `zenzic-action` and `zenzic-vscode`.

---

## Decision

1. **Immutable SHA Pinning Mandate**:
   All GitHub Action `uses:` references and pre-commit `rev:` keys within this ecosystem's own internal `.pre-commit-config.yaml` and `.github/workflows/*.yml` files must be pinned to immutable 40-character git commit SHA digests. Mutable tags (`@v4`, `@main`, `@just`) are prohibited in these files.

2. **Ecosystem-Wide Scope**:
   This mandate applies by name to all three ecosystem repositories: `zenzic`, `zenzic-action`, and `zenzic-vscode`. `zenzic-action` was already compliant via voluntary adoption (self-enforced by its own `check-pinning` recipe) prior to this amendment; `zenzic-vscode` was brought into compliance as of the 2026-08-22 amendment (V031).

3. **Consumer-Facing Scope Clarification**:
   This mandate governs only this project's own internal dependency references — the `uses:` steps in this ecosystem's own CI workflows, and the `rev:` keys in this ecosystem's own `.pre-commit-config.yaml` files. It does **not** extend to how external users are instructed to consume Zenzic's published hooks in their own repositories: documentation, articles, and the `.pre-commit-hooks.yaml` distribution examples correctly show `rev: vX.Y.Z` release-tag pinning for `zenzic-guard`/`zenzic-verify`, matching standard ecosystem convention (`ruff-pre-commit`, `black`, and similar tools). Consumer-facing tag pinning is a deliberate design decision, not a violation of this invariant.

4. **Dependency Asymmetry (CI vs. Developer Tooling)**:
   CI/CD integrations (`zenzic-action`) must use strict pinning (`==`) for the Core engine dependency to guarantee immutable, reproducible builds. Developer tooling (`zenzic-vscode`) uses minimum versioning (`>=`) for the Core engine dependency instead, to avoid forcing strict version locks on the user's local environment. This is a separate, narrower dependency-versioning rule from the SHA-pinning mandate above, not a conflicting one.

---

## Rationale

A tag reference is a mutable pointer — the content it resolves to can change after a workflow file is reviewed and merged, without any visible change in the consuming repository's own diff. An immutable 40-character commit SHA digest cannot be silently repointed: the exact reviewed code is what executes, every time. This is a standard supply-chain-security hardening pattern, applied consistently across the ecosystem's own internal workflows rather than left to per-repository discretion.

---

## Invariants

- No `.github/workflows/*.yml` or `.pre-commit-config.yaml` file in `zenzic`, `zenzic-action`, or `zenzic-vscode` may reference a GitHub Action `uses:` step or pre-commit `rev:` key by mutable tag (`@v4`, `@main`, `@just`) — only a 40-character commit SHA is permitted.
- This mandate does not apply to consumer-facing documentation or distribution examples showing external users how to pin `zenzic-guard`/`zenzic-verify` by release tag in their own repositories.
- `zenzic-action`'s Core engine dependency uses strict `==` pinning; `zenzic-vscode`'s uses `>=` minimum versioning — both are compliant, serving different operational needs (reproducible CI builds vs. flexible developer tooling).

---

## Consequences

- The exact code executing in any ecosystem CI workflow or pre-commit hook is guaranteed to match what was reviewed at merge time — no silent drift from a repointed tag.
- Consumer-facing hook distribution remains ergonomic (`rev: vX.Y.Z`), unaffected by this internal-only hardening.
- Enforcement requires an explicit `check-pinning`-style recipe (as already adopted by `zenzic-action`) or an equivalent CI check in each repository to catch a mutable-tag regression before merge — this ADR does not itself specify that mechanism's implementation.

For the current status of the Sovereign Verification Model this invariant is part of, see [Sovereign Verification Model & Zero-Network Parity](../../sovereign-verification-model.md).
