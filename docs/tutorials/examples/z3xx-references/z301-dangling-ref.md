---
description: "Analysis of the z301-dangling-ref fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z301 — Dangling Ref

**Z-Code:** `Z301 DANGLING_REF` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

The fixture lives in `examples/z301-dangling-ref/` in the Zenzic repository.
It contains documents demonstrating the `Z301` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z301-dangling-ref
uvx zenzic check all
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 65 files/s

docs/index.md:12  x  [Z301]  Reference '[Click here][missing-ref]' uses
undefined ID 'missing-ref'.

    10  │  ## Content With Dangling Reference
    11  │
    12  ❱  To get started, [Click here][missing-ref] for the installation guide.
    13  │
    14  │  Note: `missing-ref` has no corresponding `[missing-ref]: url`
definition

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 0 warnings  i 0 info  - 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

---

## Interpreting the Output

The `Z301` finding indicates a **DANGLING_REF** issue.

This error or warning is raised by Zenzic when a reference-style link (e.g. `[my text][ref_id]`) references an identifier `ref_id` that is not defined anywhere in the document. Zenzic uses a two-pass scanner to compile all definitions before validating references, avoiding issues with forward references. In this specific example:

- **Scan Type:** `Reference Scanner`
- **Severity:** `Warning`
- **Impact:** Dangling references lead to unrendered markdown links, resulting in a DQS deduction of 4.0 points.

---

## Resolve the Issue

Exit code 1. Define the missing reference block at the bottom of the document (e.g. `[ref_id]: https://example.com`) or correct the typo in the link reference.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
