---
description: "Walk through the z521-required-table-column fixture: a table missing a column declared in [policies].required_table_columns, triggering Z521 REQUIRED_TABLE_COLUMN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z521 — Required Table Column

**Z-Code:** `Z521 REQUIRED_TABLE_COLUMN` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A table that renders correctly and omits a column the project requires.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the required columns |
| `docs/index.md` | A table with `Feature` and `Version` only |

The contract:

```toml
[policies]
required_table_columns = {"*" = ["Status", "Description"]}
```

The `"*"` context applies it to every table in the documentation set. The
fixture's table has neither required column.

This is the check the phrase *specification-driven documentation* points at. A
table is often a contract — a compatibility matrix, an API surface, a feature
list — and a missing column means every row silently lost a field. Markdown has
no schema, so nothing else notices: the table parses, renders, and looks
deliberate.

Zenzic parses tables into an AST rather than matching pipes with a regex, so
alignment rows, escaped pipes and inline code inside cells do not confuse it.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z521-required-table-column
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 21 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z521]  Table missing required column 'Status' (declared in
[policies].required_table_columns under context '*').
    1  │  # Table Column Example
    2  │
    3  ❱  | Feature | Version |
```

One finding per missing column, so a table missing both required columns reports
twice.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (content category).
- **Auto-Fixable:** No. Zenzic could add a header cell; it could not fill the
  rows, and a column of blanks is worse than an absent one.
- **Opt-In:** Yes — silent until `required_table_columns` is declared.
- **Suppressible:** Not by inline comment. The finding concerns a table as a
  whole, so use a directory policy where a section legitimately differs.

---

## Resolve the Issue

Add the column and populate every row:

```markdown
| Feature | Version | Status | Description |
| :--- | :--- | :--- | :--- |
| AST | 0.31 | stable | Lossless Markdown parse tree |
```

If only some tables carry the contract, scope the context to a path prefix
rather than `"*"` — a broad rule that everyone suppresses enforces nothing.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z522 — Table Cell Enum](z522-table-cell-enum) — the column exists, a value in
  it is not permitted.
- [Z523 — Heading Order Violation](z523-heading-order) — the same
  contract-enforcement idea applied to headings.
- [Checks Reference](../../../reference/checks) — full rule specification.
