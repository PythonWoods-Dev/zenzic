---
description: "Walk through the z522-table-cell-enum fixture: a table cell holding a value outside its declared enum, triggering Z522 TABLE_CELL_ENUM."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z522 — Table Cell Enum

**Z-Code:** `Z522 TABLE_CELL_ENUM` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A column with a closed set of legal values, and a cell outside it.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the permitted values per column |
| `docs/index.md` | A `Status` cell reading `unknown_status` |

The contract:

```toml
[policies]
table_cell_enums = {"Status" = ["draft", "review", "stable"]}
```

`Z521` asks whether the column exists. `Z522` asks whether what is *in* it is
allowed — the next question, and the one that catches drift. Status columns
accumulate synonyms over time: `stable`, `Stable`, `GA`, `production`, all
meaning the same thing to a human and nothing consistent to a script that reads
the table.

Matching is exact, which is the point. A closed vocabulary that tolerated
near-misses would not be closed.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z522-table-cell-enum
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.1s • 19 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:5  ⚠  [Z522]  Table cell value 'unknown_status' in column 'Status'
is not in allowed enum list ['draft', 'review', 'stable'] (declared in
[policies].table_cell_enums).
    3  │  | Feature | Status |
    4  │  | :--- | :--- |
    5  ❱  | Engine | unknown_status |
```

The message lists the permitted values, so the correction does not require
opening the config.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (content category).
- **Auto-Fixable:** No. Zenzic cannot know which permitted value was meant.
- **Opt-In:** Yes — silent until `table_cell_enums` is declared.
- **Suppressible:** Not by inline comment.

The column is matched by header name, so the same enum applies to every table
carrying a `Status` column anywhere in the documentation set.

---

## Resolve the Issue

Use a permitted value:

```markdown
| Engine | stable |
```

Or widen the enum, if the new value is a legitimate state the vocabulary was
missing:

```toml
table_cell_enums = {"Status" = ["draft", "review", "stable", "deprecated"]}
```

Widening deliberately is fine. Widening once per finding is how a closed
vocabulary stops being one.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z521 — Required Table Column](z521-required-table-column) — the column
  missing entirely.
- [Z613 — Frontmatter Schema Mismatch](../z6xx-brand/z613-frontmatter-schema-mismatch)
  — the same value-shape enforcement applied to frontmatter.
- [Checks Reference](../../../reference/checks) — full rule specification.
