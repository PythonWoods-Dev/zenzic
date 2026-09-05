---
description: "Walk through the z519-weasel-words fixture: vague qualifiers from a configured word list, triggering Z519 WEASEL_WORDS."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z519 — Weasel Words

**Z-Code:** `Z519 WEASEL_WORDS` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

Qualifiers that make a claim sound settled without supporting it.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the word list |
| `docs/index.md` | Uses two of the listed words |

The list is the project's own:

```toml
[policies]
weasel_words = ["clearly", "simply", "obviously"]
```

The fixture sentence is *"Clearly, you simply configure the gateway."*

These three share a failure mode particular to documentation: they assert that
something is easy. When it then isn't, the reader concludes the fault is theirs.
*"Simply configure the gateway"* tells a reader who is stuck that they have
failed at something simple — which is both untrue and discouraging. Deleting the
word usually improves the sentence and never costs information.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z519-weasel-words
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.1s • 15 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z519]  Weasel word 'Clearly' detected. Consider using
direct, precise language instead.
    1  │  # Weasel Words Example
    2  │
    3  ❱  Clearly, you simply configure the gateway. Vague qualifiers like these
```

Matching is case-insensitive — the list holds `clearly`, the prose has
`Clearly`, and it is found.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** No. Deleting a word can leave a sentence ungrammatical.
- **Opt-In:** Yes — the list is empty by default, so nothing is flagged until
  the project declares its own.

The list is entirely project-controlled. There is no built-in vocabulary, which
means the check enforces *your* style guide rather than an opinion shipped with
the tool.

---

## Resolve the Issue

Delete the qualifier, and repair the sentence if needed:

```markdown
Configure the gateway.
```

If a word on the list has a legitimate technical use — *"the signal is clearly
separable"* — suppress that instance rather than removing the word from the
list.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z518 — Passive Voice](z518-passive-voice) — the other opt-in prose heuristic.
- [Z617 — Forbidden Content Pattern](../z6xx-brand/z617-forbidden-content) — the
  same idea with arbitrary RE2 patterns instead of a word list.
- [Checks Reference](../../../reference/checks) — full rule specification.
