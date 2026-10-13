<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR-031: The Gate Paradox

Before v0.8.0, Zenzic maintained two separate tables:

- `CODE_SARIF_LEVELS` — used by the CI gate (exit code)
- a penalty table — used by the DQS scorer

Three codes were registered as `error` level (CI-blocking) but had 0.0 pts in
the penalty table:

| Code | Name | SARIF | Penalty pre-v0.8 | Penalty v0.8+ |
| :--- | :--- | :---: | ---: | ---: |
| Z103 | ORPHAN_LINK | error | 0.0 pts | **2.0 pts** |
| Z111 | VIRTUAL_ROUTE_BROKEN | error | 0.0 pts | **8.0 pts** |
| Z113 | AUTHOR_KEY_COLLISION | error | 0.0 pts | **2.0 pts** |

*Historical snapshot as of v0.8.0 — `Z111` has since been reassigned to a different meaning, and `Z113` has been removed entirely. Codes referenced in this historical example may since have been renamed or removed.*

**The paradox**: a repo with 50 Z103 findings would block CI (exit 1) yet
report DQS = 100/100, because the scorer saw no penalty for Z103.

ADR-031 resolved this by introducing `CodeDefinition` as a Single Source of
Truth: one record per code stores severity, DQS penalty, and category bucket.

```python
CODES = {
    "Z103": CodeDefinition(severity="error", penalty=2.0, category="structural"),
}
```

A single Z103 finding now reduces the DQS by 2.0 pts: **DQS = 98/100**.
