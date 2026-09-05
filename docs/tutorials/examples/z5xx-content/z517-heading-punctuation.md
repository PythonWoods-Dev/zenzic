---
description: "Walk through the z517-heading-punctuation fixture: a heading ending in a period, triggering the auto-fixable Z517 HEADING_PUNCTUATION."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z517 — Heading Punctuation

**Z-Code:** `Z517 HEADING_PUNCTUATION` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A heading punctuated like a sentence.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | An H1 ending in a period |

```markdown
# Heading Punctuation Example.
```

A heading is a label, not a sentence, and labels do not take terminal
punctuation. Beyond style, the trailing character travels: it appears in the
generated anchor, in the table of contents, in a search result title, and in the
browser tab.

Trailing periods, colons and semicolons are all flagged. Question marks and
exclamation marks are not — a heading phrased as a question is a legitimate
choice, common in FAQs.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z517-heading-punctuation
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 20 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ⚠  [Z517]  Heading 'Heading Punctuation Example.' ends with
invalid trailing punctuation '.'. Headings should not end with periods, colons,
or semicolons.
    1  ❱  # Heading Punctuation Example.
       │  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** **Yes** — `zenzic fix` strips the character.

This is one of the few findings where the correct fix is unambiguous, which is
exactly why it is automatable: there is one right answer, and it is *remove the
last character*.

---

## Resolve the Issue

```bash
zenzic fix --dry-run   # preview
zenzic fix --apply
```

The mutation removes the trailing punctuation and nothing else. The heading's
anchor changes as a result — from `#heading-punctuation-example` with a trailing
hyphen artefact to the clean form — so re-run `zenzic check all` afterwards to
catch any inbound link that pointed at the old anchor (`Z102`).

---

## See Also

- [Z515 — Bare URL Used](z515-bare-url) — another auto-fixable content code.
- [Z520 — Malformed List](z520-malformed-list) — the third in this batch.
- [Checks Reference](../../../reference/checks) — full rule specification.
