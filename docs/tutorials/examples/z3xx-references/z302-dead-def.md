---
description: "Analysis of the z302-dead-def fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z302 — Dead Def

**Z-Code:** `Z302 DEAD_DEF` · **Engine:** `standalone` · **Exit:** `0`

<Z302DeadDef />

---

## The Fixture

The fixture lives in `examples/z302-dead-def/` in the Zenzic repository.
It contains documents demonstrating the `Z302` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z302-dead-def
uvx zenzic check all
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 68 files/s

────────────────────────────────────────────────────────────────────────────────

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 1/30 (inline: 0, per-file: 1) [MANAGED DEBT]
```

Exit code: `0`

---

## Interpreting the Output

The `Z302` finding indicates a **DEAD_DEF** issue.

This error or warning is raised by Zenzic when a reference definition (e.g. `[ref_id]: http://url`) is declared at the bottom of a file or in the text but is never used by any link in that document. This clutters the document structure. In this specific example:

- **Scan Type:** `Reference Scanner`
- **Severity:** `Warning`
- **Impact:** Dead definitions represent redundant text metadata and result in a DQS deduction of 1.0 point.

---

## Resolve the Issue

Exit code 1. Delete the unused reference definition block from the document, or use the reference in a reference-style link.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
