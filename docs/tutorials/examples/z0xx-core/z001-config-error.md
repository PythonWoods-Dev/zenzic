---
description: "Analysis of the z001-config-error scenario: how a configuration value of the wrong type aborts the scan before any Markdown is read, exiting 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z001 — Configuration Structure Error

**Z-Code:** `Z001 CORE_CONFIG_STRUCTURE` · **Engine:** `standalone` · **Exit:** `1`

---

## Overview

The configuration file `.zenzic.toml` (or `pyproject.toml`) defines the constitution of the scan: its rules, scoring parameters, and exclusion zones. When a value in it cannot be validated, Zenzic cannot safely execute the check suite, and it stops before reading any Markdown.

---

## The Scenario

Consider a project whose `.zenzic.toml` gives a setting a value of the wrong type:

```toml
# .zenzic.toml
docs_dir = "docs"

[governance]
suppression_cap = "high"
```

`suppression_cap` must be an integer, so the configuration fails validation.

An unknown key is a different case and does not stop the scan: Zenzic prints a warning naming the key, ignores it, and runs.

---

## Running the Check

When running Zenzic on a project with this configuration:

```bash
zenzic check all
```

Zenzic prints a *Zenzic Error* panel whose message names the setting and the problem:

```text
Configuration validation failed in .zenzic.toml:
  - suppression_cap: Input should be a valid integer, unable to parse string as an integer
```

Exit code: `1`

---

## Interpreting the Output

The `Z001` finding indicates a **CORE_CONFIG_STRUCTURE** issue.

- **Scan Tier:** Core / Bootstrap
- **Severity:** `Error` (Fatal)
- **Impact:** Immediate termination. The scan aborts before any Markdown or link analysis begins.

---

## Resolve the Issue

1. Open `.zenzic.toml` or `pyproject.toml`.
2. Find the setting the message names (here, `suppression_cap`).
3. Give it a value of the expected type, or remove it to use the default.

---

## See Also

- [Checks Reference](../../../../reference/checks/) — full rule specification.
