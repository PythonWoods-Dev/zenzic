---
description: "Walk through the z619-max-complexity fixture: a document whose complexity score exceeds [policies].max_document_complexity, triggering Z619 MAX_DOCUMENT_COMPLEXITY."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z619 — Max Document Complexity

**Z-Code:** `Z619 MAX_DOCUMENT_COMPLEXITY` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A document that has outgrown a deliberately low ceiling.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Sets the maximum complexity score |
| `docs/index.md` | Scores 35 against a limit of 5 |

The policy is a single number:

```toml
[policies]
max_document_complexity = 5
```

The fixture sets it far below any realistic threshold so a small page trips it —
a real project would set something like `50`.

The check exists because a page that keeps accreting sections eventually stops
being one document. Splitting it is a judgement call that nobody makes
spontaneously, since each individual addition is small. A ceiling turns that
gradual drift into a visible event.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z619-max-complexity
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.1s • 20 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ⚠  [Z619]  Document complexity score (35) exceeds the
configured maximum (5). Declared in [policies].max_document_complexity.

Summary:  ✘ 0 errors  ⚠ 2 warnings  💡 0 info  • 1 file with findings
DQS Final Score: 92/100 (Gate Passed)
```

Both the measured score and the configured limit appear in the message, so you
can judge whether the document is too large or the limit is too tight without
re-running anything.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand category).
- **Auto-Fixable:** No. Splitting a document is an authoring decision with
  consequences for navigation and inbound links.
- **Opt-In:** Yes — silent until `max_document_complexity` is declared.

The finding is reported once per document, at line 1, because the subject is the
document as a whole.

---

## Resolve the Issue

**Split the document** along its natural seams — usually its top-level sections —
and link the parts from an index page. Check inbound links afterwards: moving
content is exactly the situation `Z101` and `Z102` exist to catch, and
`zenzic fix --rename OLD NEW` repairs relative links across the tree.

**Or raise the limit**, if the document is genuinely cohesive at its current
size. A threshold nobody agrees with gets suppressed everywhere, which is worse
than a higher one that holds.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z618 — Required Heading Pattern](z618-required-heading) — the other
  structural policy in this family.
- [Z502 — Short Content](../z5xx-content/z502-short-content) — the opposite
  bound: a page with too little.
- [Checks Reference](../../../reference/checks) — full rule specification.
