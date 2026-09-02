---
description: "Walk through the z516-multiple-h1 fixture: a page with two H1 headings, breaking the one-title-per-document rule and triggering Z516 MULTIPLE_H1_HEADINGS."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z516 — Multiple H1 Headings

**Z-Code:** `Z516 MULTIPLE_H1_HEADINGS` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

One page, two top-level titles.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | Declares a second `#` heading partway down the page |

The document opens with its real title, then introduces another at line 5:

```markdown
# Welcome

Introduction content.

# Second Title
```

Both render. Markdown does not object, and neither does a syntax linter — this
is valid Markdown that produces an invalid document.

The problem is semantic. An H1 is the document's title, and a document has one
title. Two H1s leave every consumer that reads structure — screen readers, the
site's table of contents, search indexers building result snippets — with no
answer to "what is this page called". It is also the usual signature of two pages
concatenated into one, which is worth catching for its own sake.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z516-multiple-h1
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.1s • 19 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:5  ✘  [Z516]  Multiple H1 headings detected in document ('Second
Title'). Documents must have exactly one H1 title.
    3  │  Introduction content.
    4  │
    5  ❱  # Second Title
       │  ^^^^^^^^^^^^

Summary:  ✘ 1 error  ⚠ 1 warning  💡 0 info  • 1 file with findings
```

The finding points at line 5 — the *second* H1, not the first. The first one is
correct; the second is the defect.

---

## Interpreting the Output

- **Severity:** `Error`
- **Impact:** Deducts **5.0 DQS points** (content category).
- **Auto-Fixable:** No. Demoting the second H1 to an H2 is usually right, but
  "usually" is not a guarantee, and the alternative — splitting the page in two —
  changes the site's structure. Zenzic will not guess between them.

---

## Resolve the Issue

Two fixes, depending on what the second title actually is:

**If it is a section of this page**, demote it:

```markdown
# Welcome

Introduction content.

## Second Title
```

**If it is a separate page** that was concatenated by accident, split it into its
own file and add it to the navigation.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z503 — Snippet Error](z503-snippet-error) — another content-category error
  that a syntax linter also passes over.
- [Rule card: Z516](../../../rules/Z516) — the code's full specification.
- [Checks Reference](../../../reference/checks) — where Z516 sits among the
  structural checks.
