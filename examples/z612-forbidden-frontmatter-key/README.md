<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z612 FORBIDDEN_FRONTMATTER_KEY — Gallery Example

**Category:** Z6xx Governance
**Expected exit:** 1 (errors)

## What this demonstrates

`.zenzic.toml` declares `[policies]` with `forbidden_frontmatter_keys = ["draft", "internal_notes"]`.
`docs/index.md` contains `draft: true` in its frontmatter.
Zenzic flags the forbidden key as **Z612 FORBIDDEN_FRONTMATTER_KEY**.

## Run it

```bash
zenzic lab z612
```

## Expected output

```text
docs/index.md:1  [Z612]  Forbidden frontmatter key 'draft' is present
```

## Real-world fix

Remove the forbidden frontmatter key from the document:

```markdown
---
title: Document Title
---
```
