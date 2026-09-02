---
description: "Walk through the z511-excessive-sentence-length fixture: a 45-word sentence against a 40-word limit, triggering Z511 EXCESSIVE_SENTENCE_LENGTH."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z511 — Excessive Sentence Length

**Z-Code:** `Z511 EXCESSIVE_SENTENCE_LENGTH` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

One sentence that runs past the configured limit.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | Contains a 45-word sentence |

The check counts words between sentence boundaries and compares against a
threshold. Nothing about the sentence is ungrammatical — it is simply long
enough that a reader has to hold too much in mind before reaching the verb that
resolves it.

This is a heuristic, not a grammar rule. A long sentence is sometimes the right
one, and the threshold is a prompt to re-read rather than a verdict.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z511-excessive-sentence-length
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 22 files/s

docs/index.md:3  ⚠  [Z511]  Sentence of 45 words exceeds maximum limit of 40
words.

Summary:  ✘ 0 errors  ⚠ 1 warning  💡 1 info  • 1 file with findings
DQS Final Score: 99/100 (Gate Passed)
```

Both the measured count and the limit appear, so you can see how far over the
sentence runs without counting it yourself.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** No. Splitting a sentence changes its meaning, and only an
  author can decide where the seam is.

Sentence boundaries are detected with RE2 patterns, so abbreviations and
decimals occasionally split a sentence in an unexpected place. Treat an
implausible word count as a boundary-detection artefact rather than a real
finding.

---

## Resolve the Issue

Split the sentence at its natural join — usually a conjunction or a semicolon
that is already doing the work of a full stop.

To adjust the threshold for a project whose register genuinely runs longer:

```toml
[policies]
max_sentence_words = 50
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z518 — Passive Voice](z518-passive-voice) — another prose
  heuristic in the same family.
- [Z519 — Weasel Words](z519-weasel-words) — vague qualifiers.
- [Checks Reference](../../../reference/checks) — full rule specification.
