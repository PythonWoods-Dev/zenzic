---
description: "Analysis of the z402-orphan-page fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z402 — Orphan Page

**Z-Code:** `Z402 ORPHAN_PAGE` · **Engine:** `zensical` · **Exit:** `0`

<Z402OrphanPage />

---

## The Fixture

The fixture lives in `examples/z402-orphan-page/` in the Zenzic repository.
It contains documents demonstrating the `Z402` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z402-orphan-page
uvx zenzic check all
```

Expected output:

```text
zensical - 3 files (3 docs, 0 assets) - 0.0s - 155 files/s

docs/secret.md  !  [Z402]  Physical file not listed in navigation.

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

The `Z402` finding indicates a **ORPHAN_PAGE** issue.

This error or warning is raised by Zenzic when a markdown file exists in the directory structure but is not registered in the site navigation sidebar or navigation contract. This prevents users from discovering the page through standard navigation links. In this specific example:

- **Scan Type:** `Structure Guard`
- **Severity:** `Warning`
- **Impact:** Orphan pages reduce discoverability and result in a DQS deduction of 4.0 points.

---

## Resolve the Issue

Exit code 1. Add the orphaned file path to the navigation configuration file or link to it from an active page in the documentation structure.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
