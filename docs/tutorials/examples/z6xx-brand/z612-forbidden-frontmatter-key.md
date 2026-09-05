---
description: "Walk through the z612-forbidden-frontmatter-key fixture: a page carrying a frontmatter key listed in [policies].forbidden_frontmatter_keys, triggering Z612 FORBIDDEN_FRONTMATTER_KEY."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z612 — Forbidden Frontmatter Key

**Z-Code:** `Z612 FORBIDDEN_FRONTMATTER_KEY` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A page carrying metadata that was meant to be temporary.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Lists keys no published page may carry |
| `docs/index.md` | Carries `draft: true` |

The policy names them:

```toml
[policies]
forbidden_frontmatter_keys = ["draft", "internal_notes"]
```

The page still declares itself a draft:

```yaml
---
title: "Forbidden Key Demonstration"
draft: true
---
```

Both example keys share a failure mode: they are added during authoring and are
supposed to be removed before publication. `draft: true` on a live page either
hides it from the build or does nothing, and either outcome is a surprise.
`internal_notes` is worse — it publishes commentary that was never meant to
leave the team.

Nothing in the file marks these as leftovers. Only the project's own policy can
say which keys have an expiry.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z612-forbidden-frontmatter-key
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 22 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ⚠  [Z612]  Forbidden frontmatter key 'draft' is present. Remove
'draft' from the YAML frontmatter block. Declared in
[policies].forbidden_frontmatter_keys.
    1  ❱  ---
    2  │  title: "Forbidden Key Demonstration"
    3  │  draft: true

Summary:  ✘ 0 errors  ⚠ 2 warnings  💡 0 info  • 1 file with findings
```

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand category).
- **Auto-Fixable:** No. Deleting a key is a content decision, and a `draft: true`
  that is genuinely current should stay.
- **Opt-In:** Yes — silent until `forbidden_frontmatter_keys` is declared.

The finding reports at line 1, the frontmatter delimiter, with the offending key
named in the message and visible in the excerpt.

---

## Resolve the Issue

Remove the key:

```yaml
---
title: "Forbidden Key Demonstration"
---
```

If the page really is a draft, the fix is to keep it out of the published set
rather than to allow the key — otherwise the policy stops meaning anything.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z610 — Required Frontmatter Missing](z610-required-frontmatter) — the
  inverse: a key that must be present.
- [Z613 — Frontmatter Schema Mismatch](z613-frontmatter-schema-mismatch) — the
  key is allowed, its value is not.
- [Checks Reference](../../../reference/checks) — full rule specification.
