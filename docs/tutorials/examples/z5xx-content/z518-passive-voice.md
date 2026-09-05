---
description: "Walk through the z518-passive-voice fixture: an opt-in RE2 heuristic flagging a passive construction, triggering Z518 PASSIVE_VOICE_DETECTED."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z518 — Passive Voice Detected

**Z-Code:** `Z518 PASSIVE_VOICE_DETECTED` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A sentence that hides who acts.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Enables the opt-in check |
| `docs/index.md` | Contains a passive construction |

The check is off unless asked for:

```toml
[policies]
enable_passive_voice_check = true
```

The fixture sentence is *"The system is configured by the operator."* The active
form — *"The operator configures the system"* — is shorter and names the actor
first. In technical documentation that matters more than style: passive voice
routinely drops the actor entirely (*"the system is configured"*), leaving the
reader unsure whether that is their job or something that already happened.

**This is a pattern heuristic, not grammar analysis.** It matches shapes like
*is configured*, *was reviewed by*, *has been deprecated* using RE2 patterns. It
flags likely candidates for a human to confirm, and it will miss constructions
and occasionally flag correct ones.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z518-passive-voice
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 21 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z518]  Passive voice construct 'is configured' detected.
Consider using active voice for clearer technical writing.
    1  │  # Passive Voice Example
    2  │
    3  ❱  The system is configured by the operator. Technical writing guides
       │  ^^^^^^^^^^^^^
```

Note the wording: *Consider using*. The finding is advisory by design.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (content category).
- **Auto-Fixable:** No. Rewriting to active voice requires knowing the actor,
  which the sentence may not supply.
- **Opt-In:** Yes — silent unless `enable_passive_voice_check` is set.

Passive voice is sometimes correct: when the actor is genuinely unknown, or when
the object is the subject of the paragraph. Suppress those individually rather
than turning the check off:

```markdown
The database is replicated across three regions. <!-- zenzic:ignore Z518 -->
```

---

## Resolve the Issue

Rewrite with the actor first:

```markdown
The operator configures the system.
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z519 — Weasel Words](z519-weasel-words) — the other opt-in prose heuristic.
- [Z511 — Excessive Sentence Length](z511-excessive-sentence-length) — sentence
  length rather than construction.
- [Checks Reference](../../../reference/checks) — full rule specification.
