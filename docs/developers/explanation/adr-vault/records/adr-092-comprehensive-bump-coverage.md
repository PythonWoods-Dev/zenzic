---
description: "Architectural Decision Record mandating comprehensive release bump coverage across all documentation and configuration files."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 092: Comprehensive Release Bump Coverage

This document details the architectural specification and contract for ADR 092: Comprehensive Release Bump Coverage within the Zenzic ecosystem.

---

## Context

Hardcoded version declarations across user documentation (`README.md`, `docs/editor/vscode.md`, `docs/how-to/configure-ci-cd.md`), issue templates, and pre-commit examples were subject to drift during release cycles if relied upon through manual edits.

---

## Decision

Every non-historical hardcoded version declaration across the entire repository and its ecosystem companions (`zenzic`, `zenzic-vscode`, `zenzic-action`) MUST be tracked and governed in `.bumpversion.toml`:

1. **Automated Search & Replace**: Each file containing a live version reference must define an explicit `[[tool.bumpversion.files]]` entry.
2. **Zero Manual Version Edits**: Version numbers in code, schemas, manifests, documentation, and workflow examples are updated strictly via `just release <part>`.
3. **Exclusion of Historical Data**: Only historical changelog archives (`changelogs/vX.Y.x.md`) and dated blog posts are exempt from bump automation.

---

## Rationale

Manual version editing is error-prone, produces undocumented release debt, and breaks consumer documentation (e.g., outdated minimum Core version requirements in VS Code guides). Centralized, automated bump coverage guarantees that releases are atomic, immutable, and 100% reproducible.

---

## Invariants

- No non-historical version string may exist in the repository without a corresponding `.bumpversion.toml` pattern.
- Releases must fail the pre-release audit if any version pattern fails to match.

---

## Consequences

- Atomic, zero-debt version bumps across all documentation and configuration files.
- Elimination of stale version references in developer onboarding guides.
- Full compliance with the [Mirror Law (ADR-020)](./adr-020-mirror-law.md).

For operational protocols, see the [Release Governance Protocol](../../../how-to/release-governance-protocol.md) and the [ADR Vault](../index.md).
