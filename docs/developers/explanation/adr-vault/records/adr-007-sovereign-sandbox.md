---
description: "Architectural Decision Record on isolating the Zenzic analysis runtime to prevent privilege escalation."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 007: Sovereign Sandbox

This section details the specifications and guidelines for ADR 007: Sovereign Sandbox within the Zenzic ecosystem.


## Context

When analyzing and parsing external data or configuration, the system must prevent unexpected privilege escalation or side effects.

## Decision

Isolate the analysis runtime to prevent privilege escalation.

## Rationale

Restricting the analysis to a sovereign sandbox guarantees that external inputs cannot alter the host system state or access unauthorized resources.

## Invariants

- Analysis runtime must be fully isolated.
- Zero capability for privilege escalation during execution.

## Consequences

- Tighter security envelope around the analyzer.
- Increased complexity in bridging data across the sandbox boundary.
