---
description: "Walk through the z520-malformed-list fixture: consecutive semicolon-terminated lines that read as a list but lack list markers, triggering the auto-fixable Z520 MALFORMED_LIST_DETECTED."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z520 — Malformed List

**Z-Code:** `Z520 MALFORMED_LIST_DETECTED` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A list that is not a list.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | Three semicolon-terminated lines with no markers |

```markdown
Here are the components:
Parser module;
Graph builder;
Reporter.
```

The author wrote a list. Markdown sees a paragraph: without `- `, `* ` or `1. `
markers, consecutive lines are joined into flowing prose, so this renders as one
run-on line rather than three items.

This is a rendering defect that is invisible in the source. The Markdown looks
like a list to the person writing it, which is why the mistake survives review —
you have to build the page to see it.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z520-malformed-list
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 22 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:4  ⚠  [Z520]  Malformed list detected at line 4: paragraph
contains 3 consecutive lines formatted as a list with semicolons/commas without
proper Markdown list markers ('- ', '* ', '1. ').
    2  │
    3  │  Here are the components:
    4  ❱  Parser module;
```

The message states how many consecutive lines matched, which is the signal that
distinguishes a real pseudo-list from an ordinary sentence ending in a
semicolon.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (content category).
- **Auto-Fixable:** **Yes** — `zenzic fix` converts the lines into a real list.

Detection needs several consecutive lines with the same terminator, so a single
semicolon mid-paragraph is not flagged.

---

## Resolve the Issue

```bash
zenzic fix --dry-run   # preview
zenzic fix --apply
```

The fix adds `- ` markers and strips the trailing semicolons, producing:

```markdown
Here are the components:

- Parser module
- Graph builder
- Reporter
```

Preview first. The heuristic is deliberately conservative, but prose that
genuinely uses semicolons across several lines would be reshaped, and
`--dry-run` costs nothing.

---

## See Also

- [Z515 — Bare URL Used](z515-bare-url) — another auto-fixable content code.
- [Z517 — Heading Punctuation](z517-heading-punctuation) — the third in this
  batch.
- [Checks Reference](../../../reference/checks) — full rule specification.
