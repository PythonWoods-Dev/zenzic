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

The directive silences nothing. It is **Phantom Debt**: it consumes part of
the 30-point governance budget without justification.

---

## The Fixture

This page intentionally contained a dead suppression directive as a fixture.
It has been converted to a code block to achieve a perfect 100/100 DQS.

```markdown
[Zenzic Documentation](./z601-brand-obsolescence.md) <!-- zenzic:ignore: Z101 - this link is fine, suppression is dead -->
```

Zenzic will report Z603 on the line above because the `zenzic:ignore: Z101` directive
never matched an active Z101 (LINK_BROKEN) finding.

---

## Running the Example

```bash
# From the zenzic-doc root
uvx zenzic check references
```

Expected output (simplified):

```text
docs/tutorials/examples/z6xx-brand/z603-dead-suppression.md:22  !  [Z603]
Inline suppression directive does not suppress any active finding.
Remove the dead comment.

    20  │  The link is valid, so no Z101 finding is produced — the directive
         is never consumed.
    21  │
    22  ❱  [Zenzic Docs](./z601-brand-obsolescence.md) <!-- zenzic:ignore:
         Z101 - this link is fine, suppression is dead -->
       │                                               ^^^^^^^^^^^^^^^^^^^^
    23  │
```

Exit code: `0` (warning-only; use `--strict` to promote to Exit 1)

---

## The Three Z603 Scenarios

### Scenario A — Dead Directive (this page)

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

- [Z603 Finding Code Reference](../../../reference/finding-codes#z603)
- [Suppression Policy](../../../reference/suppression-policy.md)
- [Z601 Brand Obsolescence Example](./z601-brand-obsolescence.md)
