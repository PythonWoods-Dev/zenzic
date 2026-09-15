---
description: "Analysis of the z112-stale-allowlist scenario: an unused entry in absolute_path_allowlist triggers Z112 STALE_ALLOWLIST_ENTRY."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z112 — Stale Allowlist Entry

**Z-Code:** `Z112 STALE_ALLOWLIST_ENTRY` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## Overview

The `absolute_path_allowlist` configuration option in `.zenzic.toml` (or `pyproject.toml`) allows authors to bypass `Z105` (ABSOLUTE_PATH) checks for specific absolute URL paths. However, leaving unused or stale entries in the allowlist degrades configuration hygiene and increases security/maintenance debt. Zenzic alerts you when a declared prefix is never matched.

---

## The Scenario

Consider a project with the following configuration:

```toml
# .zenzic.toml
absolute_path_allowlist = ["/legacy/unused/path/"]
```

If none of the Markdown files in the project contain a link starting with `/legacy/unused/path/`, this entry is stale.

---

## Running the Check

The scenario ships as a fixture at `examples/z112-stale-allowlist/`:

```bash
# Clone the Zenzic repository — no install required
cd examples/z112-stale-allowlist
uvx zenzic check links --strict
```

Expected output:

```text
standalone • 2 files (2 pages, 0 assets) • 0.0s • 81 files/s

.zenzic.toml:1  ⚠  [Z112]  Stale absolute_path_allowlist entry
'/legacy/unused/path/': no link matched this prefix across all scanned files

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 0 errors  ⚠ 1 warning  💡 0 info  • 1 file with findings

✔ No broken links found.
Try 'zenzic check links --help' for options.
```

Exit code: `1` — `--strict` promotes the warning to an error; without it the run exits `0`.

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
3. Remove the unused entry (e.g. `"/legacy/unused/path/"`) from the list.

---

## See Also

- [z105 — Absolute Path](../z105-absolute-path/) — the link rule bypassed by this allowlist.
- [Checks Reference](../../../../reference/checks/) — full rule specification.
