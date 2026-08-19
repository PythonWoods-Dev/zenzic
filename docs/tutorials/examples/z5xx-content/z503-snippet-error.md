---
description: "Analysis of the z503-snippet-error fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z503 — Snippet Error

**Z-Code:** `Z503 SNIPPET_ERROR` · **Engine:** `standalone` · **Exit:** `1`

<Z503SnippetError />

---

## The Fixture

The fixture lives in `examples/z503-snippet-error/` in the Zenzic repository.
It contains documents demonstrating the `Z503` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z503-snippet-error
uvx zenzic check all
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 60 files/s

docs/index.md:14  x  [Z503]  SyntaxError in Python snippet — '(' was never
closed

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 0 warnings  i 0 info  - 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

---

## Interpreting the Output

The `Z503` finding indicates a **SNIPPET_ERROR** issue.

This error or warning is raised by Zenzic when a fenced code block has syntax errors relative to its declared language specifier (e.g. invalid JSON, syntax-broken Python, or incorrect bash commands). Zenzic compiles code snippets to validate syntax correctness. In this specific example:

- **Scan Type:** `Content Guard`
- **Severity:** `Warning`
- **Impact:** Syntax errors in code snippets confuse developers and incur a massive DQS deduction penalty of 10.0 points.

---

## Resolve the Issue

Exit code 1. Fix the syntax error in the Python code block to ensure it is valid Python code.

---

## Custom YAML Tags Support

The YAML validator used by Zenzic's Snippet Guard natively registers and supports standard PyYAML custom tags (such as `!!python/name:` or `!!python/object/apply:`) as well as unregistered custom tags (such as `!ENV` or `!file`) commonly used in MkDocs configuration files. This ensures that valid YAML files incorporating these structures are parsed successfully without throwing false-positive `Z503` exceptions.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
