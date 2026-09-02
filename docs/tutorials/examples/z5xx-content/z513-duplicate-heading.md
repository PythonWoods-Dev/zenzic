---
description: "Walk through the z513-duplicate-heading fixture: two headings with identical text in one document, colliding on the same anchor and triggering Z513 DUPLICATE_HEADING."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z513 — Duplicate Heading

**Z-Code:** `Z513 DUPLICATE_HEADING` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

The same heading text, twice in one document.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | Two `## Configuration` headings |

Headings become anchors, and anchors are derived from heading text. Two
identical headings ask for the same anchor, and only one can have it — the
site generator disambiguates the second by appending a suffix, typically
`#configuration_1`.

That suffix is where the damage is. It is generated, not authored, so it is
invisible in the Markdown and unstable: insert a third `## Configuration` above
the second and every existing link to `#configuration_1` now lands somewhere
else. Nothing breaks loudly — links keep resolving, just to the wrong section.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z513-duplicate-heading
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 20 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:7  ⚠  [Z513]  Duplicate heading 'Configuration' found (first
occurrence at line 3).
    5  │  Section about configuration.
    6  │
    7  ❱  ## Configuration
```

The finding reports at the *second* occurrence and names the line of the first,
so both are in front of you at once.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (content category).
- **Auto-Fixable:** No. Renaming a heading changes its anchor, which may break
  inbound links — the fix has consequences Zenzic cannot evaluate.

Detection is per document. The same heading in two different files is normal and
not reported.

---

## Resolve the Issue

**Make the headings distinct**, which usually means saying what each configures:

```markdown
## Server Configuration
...
## Client Configuration
```

**Or merge the sections**, if the duplication means the same topic was
documented twice.

After renaming, check for inbound links to the old anchor —
`zenzic check all` reports them as `Z102`.

---

## See Also

- [Z102 — Anchor Missing](../z1xx-links/z102-anchor-missing) — links to an
  anchor that does not exist, which is what a rename can cause.
- [Z516 — Multiple H1 Headings](z516-multiple-h1) — duplicate headings at the
  title level.
- [Checks Reference](../../../reference/checks) — full rule specification.
