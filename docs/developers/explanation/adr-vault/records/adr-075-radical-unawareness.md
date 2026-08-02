---
description: "Architectural Decision Record explaining why the Zenzic Core is decoupled from specific CI runner environments."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 075: Radical Unawareness

This section details the specifications and guidelines for ADR 075: Radical Unawareness within the Zenzic ecosystem.


## Context

Tight coupling between the Core logic and specific Continuous Integration (CI) consumers creates fragile architectures and vendor lock-in.

## Decision

The Core completely ignores CI consumers.

## Rationale

By maintaining "radical unawareness" of the execution environment (e.g., GitHub Actions, GitLab CI), the Core remains portable, pure, and easy to run locally or anywhere else.

## Invariants

- Core must not contain any CI-specific logic or checks.
- Core must rely entirely on standard interfaces (CLI, API) irrespective of the consumer.

## Consequences

- Total portability of the Core analyzer.
- CI environments must adapt to the Core's standard interface, not the other way around.
