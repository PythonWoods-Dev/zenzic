---
description: "Analysis of the z202-path-traversal fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z202 — Path Traversal

**Z-Code:** `Z202 PATH_TRAVERSAL` · **Engine:** `standalone` · **Exit:** `1`

<Z202PathTraversal />

## The Fixture

The fixture lives in `examples/z202-path-traversal/` in the Zenzic repository.
It contains documents demonstrating the `Z202` violation.

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z202-path-traversal
uvx zenzic check all
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 63 files/s

docs/index.md:11:2  x  [Z202]  '../../private/secret.txt' resolves outside the
docs directory

     9  │  ## Traversal Link
    10  │
    11  ❱  - [Config](../../private/secret.txt) — this link escapes `docs/` via
`../..` → **Z202**
        │    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    12  │
    13  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 0 warnings  i 0 info  - 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

## Interpreting the Output

The `Z202` finding indicates a **PATH_TRAVERSAL** issue.

This error or warning is raised by Zenzic when a link contains directory traversal sequences (like `../`) that escape the boundaries of the designated documentation root directory, potentially exposing internal configuration or private files. In this specific example:

- **Scan Type:** `Path Traversal Guard`
- **Severity:** `Error (Non-suppressible)`
- **Impact:** Path traversal attempts collapse the DQS score to 0.0 and exit with Exit Code 3, representing a severe security boundary violation.

## Resolve the Issue

Exit code 1. Path traversal findings represent security boundaries. Correct the path to point to a valid asset located within the documentation root.

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
