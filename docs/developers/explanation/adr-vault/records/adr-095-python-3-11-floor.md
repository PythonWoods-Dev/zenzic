---
description: "Architectural Decision Record raising Zenzic's interpreter floor to Python 3.11, after the end of life of Python 3.10 and three advisories that no Python 3.10 release of a dependency fixes."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 095: Python 3.11 Is the Interpreter Floor

This document records why Zenzic requires Python 3.11 or later, what it costs the users still on Python 3.10, and how
the floor is kept from drifting back.

**Status:** Accepted
**Decider:** The project owner
**Date:** 2026-11-04

---

## Context

Python 3.10 reached its end of life on 2026-10-01: python.org's release cycle (the data behind
`devguide.python.org/versions`, read on 2026-11-04) gives the 3.10 branch the status `end-of-life` with that date,
under PEP 619. It receives no further security fixes.

The dependency review of the pull requests then reported three advisories against `filelock` 4.1.0, which `uv.lock`
resolved for Python 3.10: GHSA-v4x8-3wr5-3wq8 (high), GHSA-6627-m3xw-93mp and GHSA-9c4x-gm8v-wgc4 (moderate). All
three are fixed in `filelock` 4.2.1, and every release from 4.2.0 on requires Python 3.11. On Python 3.10 there was
no version to move to: the lock could not be made clean while 3.10 stayed supported.

---

## Decision

`requires-python` is `>=3.11`. The CI matrix pairs Python 3.11 with 3.14 on Ubuntu and runs 3.11 on Windows; ruff
targets `py311` and mypy `3.11`; the `tomli` backport is no longer a dependency, since `tomllib` is in the standard
library from 3.11. No exception is declared for the three advisories: the lock no longer resolves `filelock` 4.1.0.

---

## Rationale

An exception for the advisories would have kept a dependency set that its own maintainers no longer fix, on an
interpreter that its own maintainers no longer fix. Restricting only the development tools to 3.11 would have left
the package declaring support for an interpreter at its end of life. Raising the floor removes both, at the cost
described below.

---

## Invariants

- No public file declares or documents Python 3.10 as supported: `tests/test_no_public_file_declares_python_3_10.py`
  searches every tracked file for the forms that do (the metadata, a tool's target, the CI matrix, a page naming the
  floor), with the changelogs exempt as history, and carries its positive control.
- The lock resolves no `filelock` older than 4.2.1.

---

## Consequences

- **Users on Python 3.10**: `pip` and `uv` no longer install releases from this one on; they keep the previous
  release, which receives no fixes, or move to Python 3.11 or later. Nothing else changes for them: the
  configuration, the findings and the output are the same on 3.11.
- **Contributors**: the floor leg of the CI and of `nox` is 3.11, and the interpreter-determinism comparison pairs 3.11
  with 3.14.
- **Branch protection**: required status checks named after the 3.10 leg must be renamed after the 3.11 one on the
  platform, or pull requests wait for checks that no longer run.
