---
description: "ADR 022: English-Only Governance & Deprecation of Bilingual Invariant"
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 022: English-Only Governance & Deprecation of Bilingual Invariant

---

## Context

Following the strategic shift to an "English-Only" governance model, ADR-008 (Bilingual Structural Invariant) is no longer valid. The overhead of maintaining bilingual documentation (EN/IT) across all examples, tutorials, and architectural records slowed down feature velocity and introduced synchronization debt.

---

## Decision

Zenzic is now strictly English-Only. The `i18n/it/` directory is deprecated and removed.

---

## Consequences

ADR-008 is officially superseded. All future documentation, PRs, and commit messages must be in English.
