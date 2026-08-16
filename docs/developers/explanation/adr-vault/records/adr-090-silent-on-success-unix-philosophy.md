---
description: "Architectural Decision Record defining the Silent-on-Success Unix Philosophy and headless pipeline signal contract."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 090: Silent-on-Success Unix Philosophy & Pipeline Signal Protocol

This document details the architectural specification and contract for ADR 090: Silent-on-Success Unix Philosophy within the Zenzic ecosystem.

## Context

In continuous integration (CI) runners, pre-commit hooks, and task orchestrators (such as `just verify`), verbose CLI outputs, startup ASCII banners, and success summaries create visual noise, pollute log aggregators, and degrade developer experience during high-frequency inner loops.

## Decision

Zenzic enforces the **Unix Philosophy (Rule of Silence)** across all subcommands (`check`, `guard`, `score`, `diff`, `audit`):

1. **`--quiet` (`-q`) Contract**: When `--quiet` is passed and the command succeeds (Exit Code 0), the CLI must emit **strictly 0 bytes** to `stdout` and `stderr`.
2. **`--no-header` Protocol**: Orchestrators, task runners, and CI pipelines must pass `--no-header` (or `--ci`) to suppress decorative ASCII frames, keeping logs structured and minimalist like modern tools (`cargo`, `ruff`, `pytest`).
3. **Interactive vs. Automated Separation**: Rich visual frames and telemetry panels are reserved for interactive, human-driven terminal sessions.

## Rationale

Silence on success maximizes the signal-to-noise ratio. When an automated quality gate succeeds, no developer time should be spent reading banners. When a check fails, all terminal output must focus exclusively on actionable diagnostics and line-level remediation.

## Invariants

- If `quiet=True` and exit code is `0`, output length is strictly 0 bytes.
- All exported pre-commit hooks in `.pre-commit-hooks.yaml` pass `--quiet --no-header` by default.
- Failures must emit clear, actionable diagnostics regardless of verbosity flags.

## Consequences

- Instant feedback in pre-commit git hooks without terminal clutter.
- Standardized, machine-parsable logs across CI/CD adapters.
- Seamless integration with upstream task orchestrators.

For further context, see the [ADR Vault Records Index](./index.md) and the [CLI Architecture Reference](../../../reference/cli-architecture.md).
