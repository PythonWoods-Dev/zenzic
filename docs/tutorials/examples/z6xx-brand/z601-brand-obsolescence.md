---
description: "Analysis of the z601-brand-obsolescence fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z601 — Brand Obsolescence

**Z-Code:** `Z601 BRAND_OBSOLESCENCE` · **Engine:** `standalone` · **Exit:** `0`

<Z601BrandObsolescence />

## The Fixture

The fixture lives in `examples/z601-brand-obsolescence/` in the Zenzic repository.
It contains documents demonstrating the `Z601` violation.

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z601-brand-obsolescence
uvx zenzic check all
```

Expected output:

```text
standalone - 2 files (2 docs, 0 assets) - 0.0s - 121 files/s

docs/index.md:6:33  !  [Z601]  [Z601] Obsolete or unauthorized brand term
'OldPlatform' detected. Use semantic versioning (e.g., 'vX.Y.Z') in active
prose, or suppress if this is a historical ledger.

    4  │  # Welcome to the Documentation Platform
    5  │
    6  ❱  This project was migrated from **OldPlatform** in Q1 2026.
       │                                   ^^^^^^^^^^^
    7  │
    8  │  All content has been ported to the new documentation engine.

docs/index.md:9:4  !  [Z601]  [Z601] Obsolete or unauthorized brand term
'OldPlatform' detected. Use semantic versioning (e.g., 'vX.Y.Z') in active
prose, or suppress if this is a historical ledger.

     7  │
     8  │  All content has been ported to the new documentation engine.
     9  ❱  The OldPlatform export scripts are archived for reference.
        │      ^^^^^^^^^^^
    10  │
    11  │  ## Getting Started

docs/index.md:17:19  !  [Z601]  [Z601] Obsolete or unauthorized brand term
'OldPlatform' detected. Use semantic versioning (e.g., 'vX.Y.Z') in active
prose, or suppress if this is a historical ledger.

    15  │  ## About the Migration
    16  │
    17  ❱  The migration from OldPlatform improved build times by 60% and added
        │                     ^^^^^^^^^^^
    18  │  native i18n support. Contact the platform team for migration
assistance.

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 3 warnings  i 0 info  - 1 file with findings

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `0`

## Interpreting the Output

The `Z601` finding indicates a **BRAND_OBSOLESCENCE** issue.

This error or warning is raised by Zenzic when a deprecated, obsolete, or unauthorized brand name (e.g., 'OldPlatform') is found in the documentation content, which violates corporate style guides. In this specific example:

- **Scan Type:** `Brand Integrity Guard`
- **Severity:** `Warning`
- **Impact:** Brand obsolescence violations incur a DQS deduction of 2.0 points, which can scale exponentially if repeated.

## Resolve the Issue

Exit code 1. Replace the obsolete brand terms in your text with the current product or release terminology.

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
