---
description: "Walk through the z102-anchor-missing fixture: a fragment link targeting a heading that does not exist, triggering Z102 ANCHOR_MISSING."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z102 — Anchor Missing

**Z-Code:** `Z102 ANCHOR_MISSING` · **Engine:** `standalone` · **Exit:** `1`

<Z102AnchorMissing />

## The Fixture

The fixture lives at `examples/z102-anchor-missing/` in the Zenzic repository.
It contains two documents:

| File | Role |
| :--- | :--- |
| `docs/index.md` | Source — contains the broken fragment link at line 11 |
| `docs/guide.md` | Target — exists on disk but lacks the referenced heading |

`docs/index.md` line 11 links to `guide.md#nonexistent-section`. The target file
`guide.md` exists and contains one valid heading — `## Overview` (anchor `#overview`) —
but has no `#nonexistent-section` heading. Zenzic resolves the file, scans its headings,
finds the dead fragment, and fires Z102.

```toml title="examples/z102-anchor-missing/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
```

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z102-anchor-missing
uvx zenzic check links
```

Expected output:

```text
standalone - 2 files (2 docs, 0 assets) - 0.0s - 107 files/s

docs/guide.md:4  !  [Z502]  Page has only 37 words (minimum 50).

    2  │  <!-- SPDX-License-Identifier: Apache-2.0 -->
    3  │
    4  ❱  # Guide
    5  │
    6  │  ## Overview

docs/index.md:11:2  x  [Z102]  anchor '#nonexistent-section' not found in
'guide.md'

     9  │  ## Broken Anchor Reference
    10  │
    11  ❱  - [Nonexistent Section](guide.md#nonexistent-section) — the fragment
`#nonexistent-section` is not defined i…
        │    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    12  │
    13  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 1 warning  i 0 info  - 2 files with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

Anchor context (documentation note, not CLI output):

- Present in `guide.md`: `#guide`, `#overview`
- Missing in `guide.md`: `#nonexistent-section`

## Interpreting the Output

The `Z102` finding indicates a **ANCHOR_MISSING** issue.

This error or warning is raised by Zenzic when a markdown link contains a fragment/hash (e.g., `#section-title`) but that specific anchor is missing or undefined in the target file. Zenzic automatically compiles all headers and HTML anchor tags of the target file to verify if the requested anchor exists. In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Missing anchors lead to broken navigation within pages, resulting in a DQS deduction penalty of 5.0 points.

## Resolve the Issue

Exit code 1 halts the CI/CD pipeline. Resolve the issue by adding the missing header to the target document, ensuring its slugified name matches the fragment, or updating the link to target a valid header.

## Explicit Anchors & Attribute Lists

Zenzic natively supports explicit block-level anchors (such as `{#id}`) and handles markdown attribute lists (e.g., `{ data-toc-label="Overview" }`) attached to headings. When compiling the header registry, Zenzic strips these attribute lists before slugifying heading text, preventing false-positive `Z102` errors.

## See Also

- [z101 — Broken Links](z101-broken-links) — the file-level variant: the target file itself does not exist.
- [z103 — Orphan Link](z103-orphan-link) — link targets that exist on disk but are absent from the site navigation.
- [Checks Reference](../../../reference/checks) — full rule specification.
