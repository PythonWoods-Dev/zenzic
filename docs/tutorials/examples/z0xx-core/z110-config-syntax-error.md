---
description: "Walk through the z110-config-syntax-error fixture: a .zenzic.toml with malformed TOML that cannot be parsed, triggering Z110 CONFIG_SYNTAX_ERROR before any document is scanned."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z110 — Config Syntax Error

**Z-Code:** `Z110 CONFIG_SYNTAX_ERROR` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

A configuration file that is not valid TOML.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Contains an unterminated array |
| `docs/index.md` | Never read — the run stops first |

The whole fixture is two lines:

```text title=".zenzic.toml"
# Malformed TOML syntax example
placeholder_max_words = [ unclosed_array
```

The array opens and never closes. No TOML parser can recover a value from this,
so there is no configuration to run with.

`Z110` belongs to the `Z0xx`/`Z1xx` pre-analysis class: it fires *before* any
document is parsed. Zenzic will not scan a repository under a configuration it
could not read, because every result would be conditional on defaults the author
did not choose.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z110-config-syntax-error
uvx zenzic check all
```

Expected output:

```text
.zenzic.toml contains a syntax error and cannot be loaded.
  /path/to/examples/z110-config-syntax-error/.zenzic.toml

  Invalid value (at line 2, column 27)

Fix the TOML syntax error and re-run Zenzic.
```

Note what is absent: no file count, no findings table, no DQS score. The scan
never started.

---

## Interpreting the Output

- **Severity:** `Error`
- **Impact:** No DQS penalty — the score is not computed at all, so there is
  nothing to deduct from. A penalty of `0.0` here means "not applicable", not
  "harmless".
- **Suppressible:** No. A configuration that cannot be parsed cannot declare its
  own exemption.
- **Auto-Fixable:** No.

The error carries the parser's own line and column — `line 2, column 27`, the
point where the unterminated array runs out of file.

---

## Resolve the Issue

Close the array:

```toml
placeholder_max_words = 150
```

Re-run `zenzic check all`. The configuration loads and the scan proceeds
normally.

---

## See Also

- [Z111 — Config Schema Error](z111-config-schema-error) — the config parses as
  TOML but a value has the wrong type.
- [Z001 — Config Error](z001-config-error) — the broader configuration failure
  class.
- [Configuration Reference](../../../reference/configuration-reference) — every
  key and its accepted type.
