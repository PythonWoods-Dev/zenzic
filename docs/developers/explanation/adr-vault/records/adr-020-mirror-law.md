---
description: "Architectural Decision Record on total synchronization between code, filesystem, and bilingual documentation (EN/IT)."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 020: Mirror Law

---

## Context

Discrepancies between the codebase, the filesystem state, and the documentation lead to architectural rot and a breakdown of trust in the system's "memory".

---

## Decision

Total synchronization between code, filesystem, and documentation, enforced across 10 mandatory targets (`codes.py`, `scorer.py`, `scoring-algorithm.md`, `scoring-system.md`, `finding-codes.md`, rule cards, `mkdocs.yml` nav, `examples/`/`_lab.py`, `templates.py`, and the `zenzic-vscode` JSON Schema).

> **Amendment — ADR-022 (English-Only Governance):** this decision originally mandated bilingual EN/IT documentation parity as part of the mirror. That requirement was formally dropped by [ADR 022](adr-022-english-only-governance.md); Zenzic is English-only today, and no `i18n/` mirror exists or is expected. The synchronization requirement below applies to the 10 targets, not to a second language.

---

## Rationale

Ensuring a 1:1 reflection guarantees that the documentation is always a reliable mirror of the system's exact capabilities, avoiding out-of-sync or fragmented knowledge.

---

## Invariants

- Code features must be documented.
- Documentation must exactly reflect the filesystem and code state across all 10 Mirror Law targets.

---

## Consequences

- Increased overhead for adding new features.
- Zero drift between system behavior and documentation.
