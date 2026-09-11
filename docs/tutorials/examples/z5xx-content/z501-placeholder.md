---
description: "Analysis of the z501-placeholder fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z501 — Placeholder

**Z-Code:** `Z501 PLACEHOLDER` · **Engine:** `standalone` · **Exit:** `0`

---

## The Fixture

The fixture lives in `examples/z501-placeholder/` in the Zenzic repository.
It contains documents demonstrating the `Z501` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z501-placeholder
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'

docs/index.md:10  ⚠  [Z501]  Found placeholder text matching pattern:
'(?i)\btodo\b'

     8  │  ## Installation
     9  │
    10  ❱  TODO: content goes here
        │  ^^^^
    11  │
    12  │  ## Advanced Usage

docs/index.md:14  ⚠  [Z501]  Found placeholder text matching pattern:
'(?i)\btodo\b'

    12  │  ## Advanced Usage
    13  │
    14  ❱  TODO: Add advanced usage examples once the feature is complete.
        │  ^^^^
    15  │
    16  │  Coming soon!

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 0 errors  ⚠ 3 warnings  💡 0 info  • 1 file with findings

✨ Analysis complete: Links, credentials, semantic structure, and policies
verified.
DQS Final Score: 91/100 (Gate Passed)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 0/30 (inline: 0, per-file: 0)
```text
    21  ❱  docs/index.md:10:  Z501  PLACEHOLDER  placeholder pattern 'TODO:'
matched
        │                                                             ^^^^
    22  │  docs/index.md:16:  Z501  PLACEHOLDER  placeholder pattern 'Coming
soon!' matched
    23  │  ```

docs/index.md:21:25  !  [Z501]  Found placeholder text matching pattern:
'(?i)placeholder'

    19  │
    20  │  ```text
    21  ❱  docs/index.md:10:  Z501  PLACEHOLDER  placeholder pattern 'TODO:'
matched
        │                           ^^^^^^^^^^^
    22  │  docs/index.md:16:  Z501  PLACEHOLDER  placeholder pattern 'Coming
soon!' matched
    23  │  ```

docs/index.md:22:59  !  [Z501]  Found placeholder text matching pattern:
'(?i)coming\ soon'

    20  │  ```text
    21  │  docs/index.md:10:  Z501  PLACEHOLDER  placeholder pattern 'TODO:'
matched
    22  ❱  docs/index.md:16:  Z501  PLACEHOLDER  placeholder pattern 'Coming
soon!' matched
        │
^^^^^^^^^^^
    23  │  ```
    24  │

docs/index.md:22:25  !  [Z501]  Found placeholder text matching pattern:
'(?i)placeholder'

    20  │  ```text
    21  │  docs/index.md:10:  Z501  PLACEHOLDER  placeholder pattern 'TODO:'
matched
    22  ❱  docs/index.md:16:  Z501  PLACEHOLDER  placeholder pattern 'Coming
soon!' matched
        │                           ^^^^^^^^^^^
    23  │  ```
    24  │

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 9 warnings  i 0 info  - 1 file with findings

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `0`

---

## Interpreting the Output

The `Z501` finding indicates a **PLACEHOLDER** issue.

This error or warning is raised by Zenzic when the document contains placeholder patterns like:

```text
TODO
FIXME
LOREM IPSUM
```

or generic boilerplate strings. This checks if draft text leaked into production docs. By default, Zenzic is ultra-conservative: it uses explicit word boundaries to prevent the Scunthorpe Problem.

In this specific example:

- **Scan Type:** `Content Guard`
- **Severity:** `Warning`
- **Impact:** Placeholder text indicates incomplete documentation and results in a DQS deduction of 2.0 points.

---

## Resolve the Issue

Exit code 1. Complete the placeholder section with concrete technical content and remove the placeholder markers.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
