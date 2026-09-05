---
description: "Walk through the z515-bare-url fixture: a raw URL pasted into prose without link syntax, triggering the auto-fixable Z515 BARE_URL_USED."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z515 — Bare URL Used

**Z-Code:** `Z515 BARE_URL_USED` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A URL pasted straight into a sentence.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | Contains a bare URL in prose |

```markdown
Visit https://example.com for more information.
```

Most renderers autolink this, so it usually works — which is why it spreads. It
is not reliable: autolinking is a renderer extension rather than part of the
CommonMark core, and a bare URL adjacent to punctuation frequently swallows the
trailing character into the link.

It also reads badly. A URL in running text gives a reader the address instead of
the destination's name.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z515-bare-url
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 24 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z515]  Bare URL 'https://example.com' detected in prose.
Wrap in angle brackets '<https://example.com>' or Markdown link syntax
'[text](https://example.com)'.
```

The message gives both accepted forms.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** **Yes** — one of six codes `zenzic fix` repairs.

URLs already inside link syntax or a code fence are not flagged; the check is
about bare URLs in prose.

---

## Resolve the Issue

Let the tool do it:

```bash
zenzic fix --dry-run   # preview
zenzic fix --apply
```

The fix wraps the URL in angle brackets — `<https://example.com>` — which is the
minimal correct form and preserves the text exactly. It does not invent link
text, because it has no way to know the destination's name.

For prose, the better hand-written form names the destination:

```markdown
Visit [the example site](https://example.com) for more information.
```

Both clear the finding. The AST mutation is lossless and idempotent: running
`zenzic fix` twice never produces a second diff.

---

## See Also

- [Z517 — Heading Punctuation](z517-heading-punctuation) — another auto-fixable
  content code.
- [Z520 — Malformed List](z520-malformed-list) — the third in this batch.
- [Checks Reference](../../../reference/checks) — full rule specification.
