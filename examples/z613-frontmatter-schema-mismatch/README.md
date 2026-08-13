<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z613 FRONTMATTER_SCHEMA_MISMATCH — Gallery Example

**Category:** Z6xx Governance
**Expected exit:** 1 (errors)

## What this demonstrates

`.zenzic.toml` declares `[policies.frontmatter_schema_match]` with `version = "^v\\d+\\.\\d+\\.\\d+$"`.
`docs/index.md` specifies `version: 1.0` (missing leading `v` and patch digit).
Zenzic flags the pattern mismatch as **Z613 FRONTMATTER_SCHEMA_MISMATCH**.

## Run it

```bash
zenzic lab z613
```

## Expected output

```text
docs/index.md:1  [Z613]  Frontmatter key 'version' value '1.0' does not match required RE2 pattern '^v\d+\.\d+\.\d+$'
```

## Real-world fix

Update the version string to conform to the required SemVer format:

```markdown
---
title: Document Title
version: v1.0.0
---
```
