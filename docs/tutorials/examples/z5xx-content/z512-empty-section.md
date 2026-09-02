---
description: "Walk through the z512-empty-section fixture: a heading with no body content before the next heading or EOF, triggering Z512 EMPTY_SECTION."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z512 — Empty Section

**Z-Code:** `Z512 EMPTY_SECTION` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A heading that promises a section and delivers nothing.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | A heading with no body before the next one |

An empty section is usually an intention that was never finished: a heading
written as a placeholder, or a section whose content was moved and whose title
stayed behind. Either way the reader sees a promise the page does not keep.

**One structural exemption matters.** A heading whose next heading is *deeper*
is a grouping label — it introduces its subsections and the content lives one
level down:

```markdown
## Editor Integration

### Zenzic: Not Found
```

That is correct authoring, not an empty section, and `Z512` does not fire on it.
Without the exemption the rule would push authors into writing a sentence that
restates the heading — exactly the filler it exists to discourage. A heading
followed by a *sibling or shallower* heading has no subsection to delegate to,
so it still fires.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z512-empty-section
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.1s • 19 files/s

docs/index.md:1  ⚠  [Z502]  Page has only 17 words (minimum 50).
docs/index.md:3  ⚠  [Z512]  Heading section 'Empty Section' contains no body
content before next section or EOF.

Summary:  ✘ 0 errors  ⚠ 2 warnings  💡 1 info  • 1 file with findings
```

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** No — and deliberately so. Zenzic could delete the heading,
  but a placeholder heading is often a note about work still to do.

Code fences count as body content, so a section containing only a code block is
not empty.

---

## Resolve the Issue

Write the section, or remove the heading. If the heading is a genuine
placeholder for planned work, an issue tracker holds that better than a
published page does.

Where a section is deliberately empty in generated content, declare it:

```toml
[governance.directory_policies]
"docs/generated/**" = ["Z512"]
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z502 — Short Content](z502-short-content) — a page with body content, just
  very little of it.
- [Z510 — Heading Hierarchy](z510-heading-hierarchy) — heading levels that skip
  a rank.
- [Checks Reference](../../../reference/checks) — full rule specification.
