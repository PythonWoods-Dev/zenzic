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
 Z506 MALFORMED_FRONTMATTER
 docs/tutorials/examples/z5xx-content/z506-malformed-frontmatter.md:1

  1 │ --
    │ ^^
    Malformed frontmatter delimiter on line 1: '--' is not a valid YAML
    frontmatter boundary. Use exactly '---' (three dashes) on its own line
    to open the frontmatter block; 'template:', 'title:', and all metadata
    directives will be ignored by most engines otherwise.

 Severity  error · Penalty  −5.0 pts (Content)
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
