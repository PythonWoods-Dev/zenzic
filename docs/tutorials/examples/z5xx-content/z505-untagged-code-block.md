---
description: "Analysis of the z505-untagged-code-block fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z505 — Untagged Code Block

**Z-Code:** `Z505 UNTAGGED_CODE_BLOCK` · **Engine:** `standalone` · **Exit:** `0`

---

## The Fixture

The fixture lives in `examples/z505-untagged-code-block/` in the Zenzic repository.
It contains documents demonstrating the `Z505` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z505-untagged-code-block
uvx zenzic check all
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 61 files/s

docs/index.md:13  !  [Z505]  Fenced code block has no language specifier. Add a
language tag (e.g. ```python, ```bash, ```toml) to enable syntax highlighting
and snippet validation.

    11  │  Run the following command to get started:
    12  │
    13  ❱  ```
        │  ^^^
    14  │  zenzic check all --fail-under 0
    15  │  ```

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 1 warning  i 0 info  - 1 file with findings

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `0`

---

## Interpreting the Output

The `Z505` finding indicates a **UNTAGGED_CODE_BLOCK** issue.

This error or warning is raised by Zenzic when a fenced code block (using ` ``` ` or ` ~~~ `) has no language specifier. This prevents code syntax highlighting engines from applying the correct styles. In this specific example:

- **Scan Type:** `Code Block Scanner`
- **Severity:** `Warning`
- **Impact:** Untagged code blocks degrade formatting quality and incur a DQS deduction of 1.0 point.

---

## Resolve the Issue

Exit code 1. Append a valid language tag (e.g., ` ```python ` or ` ```bash `) immediately after the opening backticks of the fenced code block.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
