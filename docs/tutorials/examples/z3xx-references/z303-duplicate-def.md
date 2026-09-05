---
description: "Analysis of the z303-duplicate-def fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z303 — Duplicate Def

**Z-Code:** `Z303 DUPLICATE_DEF` · **Engine:** `standalone` · **Exit:** `0`

---

## The Fixture

The fixture lives in `examples/z303-duplicate-def/` in the Zenzic repository.
It contains documents demonstrating the `Z303` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z303-duplicate-def
uvx zenzic check all
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 65 files/s

docs/index.md:15  !  [Z303]  Reference ID '[api]' is defined more than once.
First definition wins (CommonMark §4.7).

    13  │  The new [API][api] includes a breaking change in `/v2/auth`.
    14  │
    15  ❱  [api]: https://api-v1.example.com
    16  │  [api]: https://api-v2.example.com
    17  │  <!-- The `api` reference ID is defined twice above — once for v1,
once for v2.

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 1 warning  i 0 info  - 1 file with findings

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 1/30 (inline: 0, per-file: 1) [MANAGED DEBT]
```

Exit code: `0`

---

## Interpreting the Output

The `Z303` finding indicates a **DUPLICATE_DEF** issue.

This error or warning is raised by Zenzic when a reference identifier is defined more than once in the same file. According to the CommonMark Spec (§4.7), only the first definition wins and subsequent duplicates are ignored. In this specific example:

- **Scan Type:** `Reference Scanner`
- **Severity:** `Warning`
- **Impact:** Duplicate definitions indicate configuration inconsistencies and result in a DQS deduction of 3.0 points.

---

## Resolve the Issue

Exit code 1. Consolidate the duplicate definitions by removing the redundant reference blocks and ensuring each identifier is declared only once.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
