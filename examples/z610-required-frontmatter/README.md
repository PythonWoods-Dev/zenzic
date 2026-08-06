<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z610 REQUIRED_FRONTMATTER_MISSING — Gallery Example

**Category:** Z6xx Governance
**Expected exit:** 1 (errors)

## What this demonstrates

`.zenzic.toml` declares `[policies]` with `required_frontmatter_keys = ["title", "author"]`.
`docs/index.md` only declares `title` in its frontmatter, missing `author`.
Zenzic flags the missing key as **Z610 REQUIRED_FRONTMATTER_MISSING**.

## Run it

```bash
zenzic lab z610
```

## Expected output

```text
docs/index.md:1  [Z610]  Required frontmatter key 'author' is absent
```

## Real-world fix

Add the required frontmatter key to the document:

```markdown
---
title: Document Title
author: PythonWoods
---
```
