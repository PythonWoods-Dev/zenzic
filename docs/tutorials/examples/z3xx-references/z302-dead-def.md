---
description: "Analysis of the z302-dead-def fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z302 — Dead Def

**Z-Code:** `Z302 DEAD_DEF` · **Engine:** `standalone` · **Exit:** `0`

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
standalone • 1 file (1 pages, 0 assets) • 0.0s • 36 files/s

docs/index.md:22  ⚠  [Z302]  Reference '[setup]: https://example.com/setup' is
defined but never used.

    20  │  for the formal reference-definition syntax.
    21  │
    22  ❱  [setup]: https://example.com/setup
    23  │
    24  │  <!-- The "setup" reference definition above is never used by any lin…

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 0 errors  ⚠ 1 warning  💡 0 info  • 1 file with findings

✨ Analysis complete: Links, credentials, semantic structure, and policies
verified.
DQS Final Score: 99/100 (Gate Passed)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 0/30 (inline: 0, per-file: 0, directory: 0)
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

- [Checks Reference](../../../../reference/checks/) — full rule specification.
