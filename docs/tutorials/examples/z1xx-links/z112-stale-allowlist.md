---
description: "Analysis of the z112-stale-allowlist scenario: an unused entry in absolute_path_allowlist triggers Z112 STALE_ALLOWLIST_ENTRY."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z112 — Stale Allowlist Entry

**Z-Code:** `Z112 STALE_ALLOWLIST_ENTRY` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

<Z112StaleAllowlist />

---

## Overview

The `absolute_path_allowlist` configuration option in `.zenzic.toml` (or `pyproject.toml`) allows authors to bypass `Z105` (ABSOLUTE_PATH) checks for specific absolute URL paths. However, leaving unused or stale entries in the allowlist degrades configuration hygiene and increases security/maintenance debt. Zenzic alerts you when a declared prefix is never matched.

---

## The Scenario

Consider a project with the following configuration:

```toml
# .zenzic.toml
absolute_path_allowlist = ["/legacy/path/"]
```

If none of the Markdown files in the project contain a link starting with `/legacy/path/`, this entry is stale.

---

## Running the Check

When running Zenzic on a project with this configuration:

```bash
zenzic check links --strict
```

Expected output:

```text
.zenzic.toml:1:1  x  [Z112]  Stale absolute_path_allowlist entry: '/legacy/path/' is never referenced in links.
```

Exit code: `1` (if run with `--strict` or if `strict = true` is set in config; otherwise exits with `0` as a warning).

---

## Interpreting the Output

The `Z112` finding indicates a **STALE_ALLOWLIST_ENTRY** issue.

- **Scan Tier:** Link Validator / Configuration Hygiene
- **Severity:** `Warning`
- **Impact:** DQS deduction of 1.0 point. Indicates dead configuration debt that should be removed.

---

## Resolve the Issue

1. Open `.zenzic.toml` (or `pyproject.toml`).
2. Locate the `absolute_path_allowlist` field.
3. Remove the unused entry (e.g. `"/legacy/path/"`) from the list.

---

## See Also

- [z105 — Absolute Path](z105-absolute-path) — the link rule bypassed by this allowlist.
- [Checks Reference](../../../reference/checks) — full rule specification.
