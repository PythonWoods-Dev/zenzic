---
description: "Analysis of the z405-unused-assets fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z405 — Unused Assets

**Z-Code:** `Z405 UNUSED_ASSET` · **Engine:** `standalone` · **Exit:** `0`

<Z405UnusedAssets />

## The Fixture

The fixture lives in `examples/z405-unused-assets/` in the Zenzic repository.
It contains documents demonstrating the `Z405` violation.

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z405-unused-assets
uvx zenzic check all
```

Expected output:

```text
standalone - 2 files (1 docs, 1 assets) - 0.0s - 129 files/s

docs/assets/banner.png  !  [Z405]  File not referenced in any documentation
page.

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 1 warning  i 0 info  - 1 file with findings

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `0`

## Interpreting the Output

The `Z405` finding indicates a **UNUSED_ASSET** issue.

This error or warning is raised by Zenzic when an image or media asset file exists in the filesystem (e.g. under `assets/`) but is never referenced by any documentation page. This bloats the repository size. In this specific example:

- **Scan Type:** `Asset Sentry`
- **Severity:** `Warning`
- **Impact:** Unused assets bloat the project build and result in a DQS deduction of 3.0 points.

## Resolve the Issue

Exit code 1. Delete the unused asset file from the repository, or add it to the `excluded_assets` list in `.zenzic.toml` if it is loaded dynamically by the theme.

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
