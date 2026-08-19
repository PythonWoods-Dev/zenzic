---
description: "Analysis of the z403-missing-alt fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z403 — Missing Alt

**Z-Code:** `Z403 MISSING_ALT` · **Engine:** `standalone` · **Exit:** `0`

<Z403MissingAlt />

---

## The Fixture

The fixture lives in `examples/z403-missing-alt/` in the Zenzic repository.
It contains documents demonstrating the `Z403` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z403-missing-alt
uvx zenzic check all
```

Expected output:

```text
standalone - 2 files (1 docs, 1 assets) - 0.0s - 123 files/s

docs/index.md:14  !  [Z403]  Image 'diagram.png' has no alt text.

    12  │  The following diagram shows the system components:
    13  │
    14  ❱  ![TODO: ADD LABEL](diagram.png)
    15  │
    16  │  The `![](diagram.png)` syntax above has an empty alt attribute →
**Z403**.

docs/index.md:16  !  [Z403]  Image 'diagram.png' has no alt text.

    14  │  ![TODO: ADD LABEL](diagram.png)
    15  │
    16  ❱  The `![](diagram.png)` syntax above has an empty alt attribute →
**Z403**.
    17  │
    18  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 2 warnings  i 0 info  - 1 file with findings

* Analysis complete: All statically-detectable links, credentials, and
references verified.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `0`

---

## Interpreting the Output

The `Z403` finding indicates a **MISSING_ALT** issue.

This error or warning is raised by Zenzic when an inline markdown image `![](url)` or an HTML `<img>` tag has no alt text. Alt text is essential for web accessibility (a11y) and SEO indexability. In this specific example:

- **Scan Type:** `Structure Guard`
- **Severity:** `Warning`
- **Impact:** Missing alt text violates accessibility policies, resulting in a DQS deduction of 1.0 point.

---

## Resolve the Issue

Exit code 1. Provide clear, descriptive text within the brackets of the image definition or the `alt` parameter of the HTML tag.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
