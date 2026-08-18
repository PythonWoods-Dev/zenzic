---
description: "Analysis of the z001-config-error scenario: how syntax errors or unknown keys in configuration TOML trigger analysis abort, exiting 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z001 — Configuration Structure Error

**Z-Code:** `Z001 CORE_CONFIG_STRUCTURE` · **Engine:** `standalone` · **Exit:** `1`

<Z001ConfigError />

## Overview

The configuration file `.zenzic.toml` (or `pyproject.toml`) defines the constitution of the scan: its rules, scoring parameters, and exclusion zones. When the parser encounters structural or semantic issues, it cannot safely execute the check suite. Zenzic aborts the scan immediately to prevent non-deterministic behavior.

## The Scenario

Consider a project with a `.zenzic.toml` containing a misspelled key or a key declared outside of any valid section table:

```toml
# .zenzic.toml
swallowed_key = true

[project]
name = "My Project"
```

Because `swallowed_key` is not a valid root-level configuration option under the `ZenzicConfig` schema, Pydantic's validation fails.

## Running the Check

When running Zenzic on a project with this configuration:

```bash
zenzic check all
```

Expected output:

```text
Error: Configuration validation failed.
Detailed errors in .zenzic.toml:
  - line 1: Extra input or unknown configuration option 'swallowed_key' was not expected.
```

Exit code: `1`

## Interpreting the Output

The `Z001` finding indicates a **CORE_CONFIG_STRUCTURE** issue.

- **Scan Tier:** Core / Bootstrap
- **Severity:** `Error` (Fatal)
- **Impact:** Immediate termination. The scan aborts before any Markdown or link analysis begins.

## Resolve the Issue

1. Open `.zenzic.toml` or `pyproject.toml`.
2. Locate the unrecognized or malformed configuration key (e.g. `swallowed_key`).
3. Correct the key's spelling, place it inside the appropriate table/section, or remove it entirely.

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
