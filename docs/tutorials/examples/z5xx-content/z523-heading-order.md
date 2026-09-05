---
description: "Walk through the z523-heading-order fixture: required headings appearing out of their declared sequence, triggering Z523 HEADING_ORDER_VIOLATION."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z523 — Heading Order Violation

**Z-Code:** `Z523 HEADING_ORDER_VIOLATION` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

The right sections, in the wrong order.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the required heading sequence |
| `docs/index.md` | `API Reference` before `Overview` |

The contract is an ordered list of RE2 patterns:

```toml
[policies]
required_heading_order = ["^Overview$", "^API Reference$"]
```

Position in the list is the requirement: a heading matching `^Overview$` must
appear before one matching `^API Reference$`. The fixture reverses them.

`Z618` asks whether a required heading exists. `Z523` asks whether the required
headings appear *in sequence* — the check for a document template where order
carries meaning. A reference page that opens with the API surface and explains
what it is for afterwards is complete and still hard to read.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z523-heading-order
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 23 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:5  ✘  [Z516]  Multiple H1 headings detected in document
('Overview'). Documents must have exactly one H1 title.
docs/index.md:5  ⚠  [Z523]  Heading 'Overview' matches pattern '^Overview$'
(order position 1) but appears after heading matching '^API Reference$' (order
position 2). Headings must appear in strictly ascending sequential order.

Summary:  ✘ 1 error  ⚠ 2 warnings  💡 0 info  • 1 file with findings
```

**This fixture exits `1`, and not because of `Z523`.** The `Z516` beside it is
error-severity: the fixture writes both required headings as H1s, so the
document has two titles. `Z523` itself is a warning and exits `0` on its own.

The message names both patterns and both order positions, so the violation is
readable without consulting the config.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (content category).
- **Auto-Fixable:** No. Reordering sections moves their content, and Zenzic will
  not rearrange a document.
- **Opt-In:** Yes — silent until `required_heading_order` is declared.
- **Suppressible:** Not by inline comment — the finding concerns a relationship
  between two headings, so no single line owns it.

The order is *strictly ascending*: headings not named in the list may appear
anywhere between them.

---

## Resolve the Issue

Move the sections into the declared order:

```markdown
# API Documentation

## Overview

What this API is for.

## API Reference

Endpoint details.
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z618 — Required Heading Pattern](../z6xx-brand/z618-required-heading) —
  whether a required heading exists at all.
- [Z516 — Multiple H1 Headings](z516-multiple-h1) — the error this fixture also
  raises, and why it exits 1.
- [Checks Reference](../../../reference/checks) — full rule specification.
