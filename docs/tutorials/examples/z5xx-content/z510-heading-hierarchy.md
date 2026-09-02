---
description: "Walk through the z510-heading-hierarchy fixture: an H3 following an H1 with no H2 between them, triggering Z510 HEADING_HIERARCHY."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z510 — Heading Hierarchy

**Z-Code:** `Z510 HEADING_HIERARCHY` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A document that skips a heading level.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | An H1 followed directly by an H3 |

```markdown
# Heading Hierarchy Example

### Skipped Subheading
```

There is no H2 between them. Visually the page looks fine — H3 is simply
smaller — which is why this survives review. Structurally the document claims a
subsection of a section that was never opened.

Headings are the document's outline, and assistive technology reads that outline
literally. A screen-reader user navigating by heading level hears a jump from
level 1 to level 3 and has no way to know whether a section was missed. The same
gap breaks generated tables of contents, which nest by level.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z510-heading-hierarchy
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 20 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z510]  Heading level H3 skips previous level H1 (expected
H2 or lower).
    1  │  # Heading Hierarchy Example
    2  │
    3  ❱  ### Skipped Subheading
```

The message names both levels and what was expected. The `Z411` above it is
incidental — this one-page fixture has no outgoing links.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** No. Promoting the H3 to an H2 is usually right, but the
  alternative — that an H2 was deleted by accident and should come back — is
  equally plausible, and Zenzic cannot tell which.

Only *descending* jumps are flagged. Returning from an H3 to an H2 closes a
subsection and is normal.

---

## Resolve the Issue

Promote the heading:

```markdown
# Heading Hierarchy Example

## Skipped Subheading
```

Or restore the missing intermediate section, if that is what went missing.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z516 — Multiple H1 Headings](z516-multiple-h1) — the other half of document
  outline structure.
- [Z523 — Heading Order Violation](z523-heading-order) — required headings in
  the wrong sequence.
- [Checks Reference](../../../reference/checks) — full rule specification.
