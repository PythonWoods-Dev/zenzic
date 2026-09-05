---
description: "Walk through the z610-required-frontmatter fixture: a page missing a frontmatter key listed in [policies].required_frontmatter_keys, triggering Z610 REQUIRED_FRONTMATTER_MISSING."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z610 — Required Frontmatter Missing

**Z-Code:** `Z610 REQUIRED_FRONTMATTER_MISSING` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A page whose frontmatter is valid and incomplete.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Lists the keys every page must carry |
| `docs/index.md` | Supplies `title`, omits `author` |

The policy names the required keys:

```toml
[policies]
required_frontmatter_keys = ["title", "author"]
```

The page provides one of the two. Nothing about the file is malformed — the
YAML parses, the page renders, and a syntax linter passes it. The finding is
about a project convention that cannot be inferred from the file itself.

Metadata is what downstream tooling consumes: author attribution, ownership
routing, generated index pages. A key that is merely *usually* present is one
that consuming code has to defend against every time it reads it.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z610-required-frontmatter
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 23 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ⚠  [Z610]  Required frontmatter key 'author' is absent. Add
'author: <value>' to the YAML frontmatter block. Declared in
[policies].required_frontmatter_keys.

Summary:  ✘ 0 errors  ⚠ 2 warnings  💡 0 info  • 1 file with findings
DQS Final Score: 92/100 (Gate Passed)
```

The `Z411` above it is incidental — this single-page fixture has no outgoing
links, so it is also a dead end.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand category).
- **Auto-Fixable:** No. Zenzic knows the key is missing; only an author knows
  its value.
- **Opt-In:** Yes — silent until `required_frontmatter_keys` is declared.

One finding is reported per missing key, so a page omitting three required keys
produces three findings rather than one summary line.

---

## Resolve the Issue

Add the key:

```yaml
---
title: "Required Frontmatter Demonstration"
author: "PythonWoods"
---
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z612 — Forbidden Frontmatter Key](z612-forbidden-frontmatter-key) — the
  inverse: a key that must *not* be present.
- [Z613 — Frontmatter Schema Mismatch](z613-frontmatter-schema-mismatch) — the
  key is present but its value does not match the required pattern.
- [Checks Reference](../../../reference/checks) — full rule specification.
