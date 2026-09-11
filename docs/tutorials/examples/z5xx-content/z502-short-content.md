---
description: "Analysis of the z502-short-content fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z502 — Short Content

**Z-Code:** `Z502 SHORT_CONTENT` · **Engine:** `standalone` · **Exit:** `0`

---

## The Fixture

The fixture lives in `examples/z502-short-content/` in the Zenzic repository.
It contains documents demonstrating the `Z502` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z502-short-content
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'

docs/index.md:4  ⚠  [Z502]  Page has only 22 words (minimum 50).

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 0 errors  ⚠ 2 warnings  💡 0 info  • 1 file with findings

✨ Analysis complete: Links, credentials, semantic structure, and policies
verified.
DQS Final Score: 94/100 (Gate Passed)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `0`

---

## Interpreting the Output

The `Z502` finding indicates a **SHORT_CONTENT** issue.

This error or warning is raised by Zenzic when the word count of the page falls below the minimum word count threshold (default is 10 words). This ensures pages contain meaningful information rather than being empty stubs. In this specific example:

- **Scan Type:** `Content Guard`
- **Severity:** `Warning`
- **Impact:** Short content indicates poor content depth and incurs a DQS deduction of 1.0 point.

---

## Resolve the Issue

Exit code 1. Write comprehensive technical documentation to meet the minimum word count, or bypass the file using the `governance.per_file_ignores` configuration.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
