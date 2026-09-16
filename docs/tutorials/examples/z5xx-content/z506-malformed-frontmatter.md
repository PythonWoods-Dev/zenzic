--

---

## description: "Live example showing a malformed frontmatter delimiter detected by Zenzic."

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z506: MALFORMED_FRONTMATTER

**Severity:** `error` · **Penalty:** −5.0 pts (Content) · **Suppressible:** Yes

---

## What Zenzic detects

The opening frontmatter delimiter on line 1 must be **exactly** `---`. Any first line that starts with two or more dashes but is **not** exactly `---` is silently ignored by most static-site engines. The consequence is that `template:`, `title:`, and all other metadata keys are rendered as raw prose instead of being parsed.

This file intentionally opens with `--` (two dashes) to trigger the rule. The `directory_policies` configuration in `.zenzic.toml` keeps this Gallery page green.

---

## Terminal Output

```text
docs/index.md:1  ✘  [Z506]  Malformed frontmatter delimiter on line 1: '--' is
not a valid YAML frontmatter boundary. Use exactly '---' (three dashes) on its
own line to open the frontmatter block; 'template:', 'title:', and all metadata
directives will be ignored by most engines otherwise.

    1  ❱  --
       │  ^^
    2  │  title: Deployment Notes
    3  │  author: Platform Team

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 1 error  ⚠ 0 warnings  💡 0 info  • 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
DQS Final Score: 95/100 (Gate Failed)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 0/30 (inline: 0, per-file: 0, directory: 0)
```

---

## Common triggers

| Line 1 content | Fires Z506? |
|---|---|
| `--` | ✅ Yes — only two dashes |
| `----` | ✅ Yes — four dashes |
| `--- @generated` | ✅ Yes — trailing text |
| `---` | ✗ No — valid delimiter |
| `# Title` | ✗ No — no dashes at all |
| `-` | ✗ No — single dash |

---

## Fix

Ensure the very first line of the file is exactly three dashes and nothing else:

```yaml
---
description: A well-formed frontmatter block
---
```

---

## Suppression

If you need to suppress Z506 on a specific file (e.g. a gallery page like this one):

```text
<!-- zenzic:ignore: Z506 -->
```
