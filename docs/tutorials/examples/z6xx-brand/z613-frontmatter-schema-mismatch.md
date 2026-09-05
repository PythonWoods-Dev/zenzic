---
description: "Walk through the z613-frontmatter-schema-mismatch fixture: a frontmatter value that fails the RE2 pattern declared in [policies].frontmatter_schema_match, triggering Z613 FRONTMATTER_SCHEMA_MISMATCH."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z613 — Frontmatter Schema Mismatch

**Z-Code:** `Z613 FRONTMATTER_SCHEMA_MISMATCH` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

A frontmatter key that is present, non-empty, and still wrong.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the required pattern per key |
| `docs/index.md` | Frontmatter whose `version` value does not match |

The policy maps a frontmatter key to an RE2 pattern its value must satisfy:

```toml
[policies.frontmatter_schema_match]
version = "^v\\d+\\.\\d+\\.\\d+$"
```

The page supplies a value that is plausible but not conformant:

```yaml
---
title: "Schema Mismatch Demonstration"
version: 1.0
---
```

`1.0` is a version number a human would accept. The pattern requires a leading
`v` and three dot-separated components — `v1.0.0`. This is the distinction the
check exists for: a key being *present* is a weaker guarantee than its value
being *usable*, and only the second one lets downstream tooling parse it.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z613-frontmatter-schema-mismatch
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 23 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ✘  [Z613]  Frontmatter key 'version' value '1.0' does not match
required RE2 pattern '^v\d+\.\d+\.\d+$'. Declared in
[policies].frontmatter_schema_match.
    1  ❱  ---
    2  │  title: "Schema Mismatch Demonstration"
    3  │  version: 1.0

Summary:  ✘ 1 error  ⚠ 1 warning  💡 0 info  • 1 file with findings
FAILED: Hard errors detected. Exit code 1 is mandatory.
DQS Final Score: 90/100 (Gate Failed)
```

---

## Interpreting the Output

- **Severity:** `Error`
- **Impact:** Deducts **5.0 DQS points** (brand category).
- **Auto-Fixable:** No. Zenzic knows the value is wrong; it cannot know what the
  right value is.

The finding is reported at line 1, the frontmatter block's opening delimiter,
rather than at the offending key. The message names the key, the actual value,
and the pattern, so the line number is a pointer to the block rather than to the
character at fault.

Patterns are compiled with RE2, so a pathological pattern cannot hang the scan.
That also means lookahead and backreferences are unavailable — see the
[Custom Rules guide](../../../how-to/add-custom-rules) for what RE2 accepts.

---

## Resolve the Issue

Correct the value to satisfy the declared pattern:

```yaml
---
title: "Schema Mismatch Demonstration"
version: v1.0.0
---
```

If instead the pattern is too strict — say two-component versions are legitimate
in this project — amend it in `.zenzic.toml`. Loosening the pattern is a real
option, but it should be a decision about what the project's version format
actually is, not a way to silence one page.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z614 — Unapproved Domain](z614-unapproved-domain) — another `[policies]`
  governance check in the same brand category.
- [Checks Reference](../../../reference/checks) — full rule specification.
