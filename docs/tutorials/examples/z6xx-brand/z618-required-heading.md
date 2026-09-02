---
description: "Walk through the z618-required-heading fixture: a page lacking any heading that matches the RE2 pattern in [policies].required_heading_patterns, triggering Z618 REQUIRED_HEADING_PATTERN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z618 — Required Heading Pattern

**Z-Code:** `Z618 REQUIRED_HEADING_PATTERN` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A page missing a section the project requires every page to have.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the required heading pattern |
| `docs/index.md` | Has headings, none matching |

The policy is a list of RE2 patterns, each of which some heading must satisfy:

```toml
[policies]
required_heading_patterns = ["^Overview$"]
```

This enforces a document template. Where every reference page is expected to
open with an `Overview`, or every runbook to contain a `Rollback`, the
requirement is real but invisible to any per-file check — the file is
well-formed, it simply lacks a section.

The pattern is anchored (`^...$`), so it matches the heading text exactly.
Dropping the anchors would let `Overview of the API` satisfy it too, which may
or may not be what the project wants.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z618-required-heading
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 22 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ⚠  [Z618]  Document does not contain any heading matching
required pattern '^Overview$'. Declared in
[policies].required_heading_patterns.

Summary:  ✘ 0 errors  ⚠ 2 warnings  💡 0 info  • 1 file with findings
DQS Final Score: 92/100 (Gate Passed)
```

The finding reports at line 1 rather than at a specific heading, because the
defect is an absence — there is no line to point at.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand category).
- **Auto-Fixable:** No. Zenzic could insert the heading; it could not write the
  section beneath it, and an empty one would trigger `Z512`.
- **Opt-In:** Yes — silent until `required_heading_patterns` is declared.

Patterns compile with RE2, so lookahead and backreferences are unavailable and a
pathological pattern cannot hang the scan.

---

## Resolve the Issue

Add the section, with real content:

```markdown
## Overview

What this page covers and who it is for.
```

If the requirement should not apply to every page — a changelog has no
`Overview` — scope it rather than dropping it:

```toml
[governance.directory_policies]
"docs/changelog.md" = ["Z618"]
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z619 — Max Document Complexity](z619-max-complexity) — the other structural
  policy in this family, bounding size rather than requiring a section.
- [Checks Reference](../../../reference/checks) — full rule specification.
