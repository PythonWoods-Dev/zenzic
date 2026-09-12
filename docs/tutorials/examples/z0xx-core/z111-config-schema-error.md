---
description: "Walk through the z111-config-schema-error fixture: a .zenzic.toml that parses as valid TOML but assigns a string where an integer is required, triggering Z111 CONFIG_SCHEMA_ERROR."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z111 — Config Schema Error

**Z-Code:** `Z111 CONFIG_SCHEMA_ERROR` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

A configuration file that is valid TOML and still unusable.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Assigns a string to an integer-typed key |
| `docs/index.md` | Never read — the run stops first |

Two lines again:

```toml
# Invalid schema type example
placeholder_max_words = "invalid_type_string"
```

Every TOML parser accepts this: it is a well-formed key-value pair with a string
value. The failure is one level up. `placeholder_max_words` is a word count, and
a word count is an integer — `"invalid_type_string"` cannot be compared against
a document's length.

This is the distinction between `Z110` and `Z111`. `Z110` is *"this file is not
TOML"*. `Z111` is *"this file is TOML, and it does not describe a valid Zenzic
configuration"*. Both stop the run before any document is scanned, for the same
reason: the alternative is reporting findings computed under settings the author
did not write.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z111-config-schema-error
uvx zenzic check all
```

Expected output:

```text
Configuration validation failed in .zenzic.toml:
  - placeholder_max_words: Input should be a valid integer, unable to parse
string as an integer
```

The message names the offending key and states the expected type, so the fix
does not require consulting the schema.

---

## Interpreting the Output

- **Severity:** `Error`
- **Impact:** No DQS penalty — as with `Z110`, no score is computed, so `0.0`
  means "not applicable" rather than "minor".
- **Suppressible:** No.
- **Auto-Fixable:** No. Zenzic knows the type is wrong; the intended value is
  the author's to supply.

Validation reports **every** offending key in one pass, not just the first. A
config with three type errors produces three lines here, so one run is enough to
fix them all.

---

## Resolve the Issue

Supply a value of the declared type:

```toml
placeholder_max_words = 150
```

Re-run `zenzic check all`. The configuration validates and the scan proceeds.

---

## See Also

- [Z110 — Config Syntax Error](z110-config-syntax-error) — the file is not
  parseable TOML at all.
- [Z001 — Config Error](z001-config-error) — the broader configuration failure
  class.
- [Configuration Reference](../../../reference/configuration-reference) — every
  key and its accepted type.
