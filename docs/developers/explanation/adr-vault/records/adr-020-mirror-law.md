---
description: "Architectural Decision Record on total synchronization between code, filesystem, and bilingual documentation (EN/IT)."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 020: Mirror Law

This section details the specifications and guidelines for ADR 020: Mirror Law within the Zenzic ecosystem.

## Context

Discrepancies between the codebase, the filesystem state, and the documentation lead to architectural rot and a breakdown of trust in the system's "memory".

## Decision

Total synchronization between code, filesystem, and bilingual documentation (EN/IT).

## Rationale

Ensuring a 1:1 reflection guarantees that the documentation is always a reliable mirror of the system's exact capabilities, avoiding out-of-sync or fragmented knowledge.

## Invariants

- Code features must be documented.
- Documentation must exactly reflect the filesystem and code state in both English and Italian.

## Consequences

- Increased overhead for adding new features.
- Zero drift between system behavior and documentation.
