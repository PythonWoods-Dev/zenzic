---
description: "Analysis of the z603-dead-suppression fixture. Demonstrates how Zenzic detects inline zenzic:ignore directives that suppress no active finding (Phantom Debt)."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z603 — Dead Suppression

**Z-Code:** `Z603 DEAD_SUPPRESSION` · **Engine:** `standalone` · **Exit:** `0` · **Severity:** `warning`

---

## What Is Z603?

Z603 fires when a `<!-- zenzic:ignore: Zxxx -->` directive exists on a line
but no active finding of code `Zxxx` is produced for that line.

The directive silences nothing, so it costs no debt point — only suppressions in
use are charged. It is still dead weight: if a finding of that code ever appears
on the line, the directive silences it without anyone having decided to.

---

## The Fixture

The fixture lives at `examples/z603-dead-suppression/`. Its `docs/index.md` carries a
broken link with an inline directive, and its `.zenzic.toml` already exempts the same
code for the whole tree:

```markdown title="examples/z603-dead-suppression/docs/index.md"
This is a broken link: [Bad Link](broken.md) <!-- zenzic:ignore: Z101 -->
```

```toml title="examples/z603-dead-suppression/.zenzic.toml"
[governance.directory_policies]
"docs/**" = ["Z101"]
```

The directory policy is applied first and silences the `Z101`, so the inline directive
never has a finding to consume: Zenzic reports it as `Z603`. The footer counts one
suppression in use — the policy pair — and none inline. Remove the policy and the
directive consumes the finding instead: no `Z603`, one inline suppression.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z603-dead-suppression
uvx zenzic check all
```

Expected output:

```text
docs/index.md:3  ⚠  [Z603]  Inline suppression directive does not suppress any
active finding. Remove the dead comment.

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 0 errors  ⚠ 1 warning  💡 0 info  • 1 file with findings

✨ Analysis complete: Links, credentials, semantic structure, and policies
verified.
DQS Final Score: 98/100 (Gate Passed)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 1/30 [MANAGED DEBT] (inline: 0, per-file: 0, directory: 1)
   1 directory policy removed findings from this report — run with --audit to
see them.
```

Exit code: `0` (warning-only; use `--strict` to promote to Exit 1)

---

## The Three Z603 Scenarios

### Scenario A — Dead Directive

A valid link has a `zenzic:ignore: Z101` directive that is never consumed.

```markdown
[Real Page](./real-page.md) <!-- zenzic:ignore: Z101 - precaution -->
```

→ Z603 fires. The suppression comment must be removed.

### Scenario B — Consumed Directive (no Z603)

A broken link has a `zenzic:ignore: Z101` directive that IS consumed.

```markdown
[Broken](./missing.md) <!-- zenzic:ignore: Z101 - known broken, tracked in issue #42 -->
```

→ Z603 does **not** fire. The directive is legitimate.

### Scenario C — Inviolability Law (Z201 + Z603)

Attempting to suppress a security code is always dead:

```text
aws_key = AKIA••••••••••••EXAMPLE <!-- zenzic:ignore: Z201 - expected key -->
```

→ **Z201 fires** (credential scanner is non-suppressible).
→ **Z603 also fires** (the Z201 directive was never consumed).

---

## Policy Isolation

The fixture directories carry directory policies in `.zenzic.toml` so that
intentional demonstration content does not fail the Quality Gate:

```toml
[governance.directory_policies]
"docs/tutorials/examples/**" = ["Z410", "Z411"]
"docs/tutorials/examples/z5xx-content/**" = ["Z506"]
```

`Z603` is not among them, and does not need to be: the dead suppression above
sits inside a fenced example block, so the engine never reads it as a live
directive. Verified with `zenzic check all --audit`, which bypasses every
suppression and still reports no `Z603` against this page.

---

## Resolve the Issue

1. **Remove the dead comment.** If the link was recently fixed, clean up the suppression.
2. **Never add speculative suppressions.** Add `zenzic:ignore` only after confirming an active finding on that line.
3. **Security codes are non-suppressible.** Z201/Z202/Z203/Z204 directives are always dead — fix the underlying secret instead.

---

## See Also

- [Z603 Finding Code Reference](../../../../reference/finding-codes/#z603)
- [Suppression Policy](../../../reference/suppression-policy.md)
- [Z601 Brand Obsolescence Example](./z601-brand-obsolescence.md)
