---
description: "Architectural Decision Record prohibiting subprocesses within the Zenzic Core to ensure security and portability."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 002: Zero Subprocesses Policy

---

## Context

Running arbitrary executables or scripts via subprocesses (e.g., `os.system`, `subprocess`) introduces severe security, portability, and determinism risks into the Core execution environment.

---

## Decision

Absolute prohibition of `os.system` and `subprocess` within the Core.

---

## Rationale

To guarantee a deterministic, safe, and portable execution environment, all logic must run strictly within the Python runtime. This adheres to the strict requirement of zero subprocesses.

---

## Invariants

- Zero subprocesses invoked by the Core.
- Complete reliance on pure Python runtime.

---

## Consequences

- No dependency on external binary tools or OS scripts.
- Improved security boundary and testability.
