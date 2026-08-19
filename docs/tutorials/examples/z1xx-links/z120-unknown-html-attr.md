---
title: Z120 Unknown HTML Attribute
description: "Z120 fires when an HTML tag contains an attribute that is not recognized as part of the Safe-Core set."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Z120 Unknown HTML Attribute

**Severity:** `warning` | **Category:** `hygiene` | **Penalty:** `-1.0 pts`

`Z120` is triggered when the Polyglot Extractor encounters an HTML `<a>` or `<img>` tag containing an attribute that is not in the predefined `Safe-Core` list.

---

## Why it matters

To ensure predictable rendering and avoid XSS vectors or broken scripts, Zenzic restricts HTML usage to a known set of safe attributes (like `class`, `id`, `href`, `src`, `alt`, etc.).

---

## Remediation

- Use standard Markdown if possible.
- If the attribute is required for a specific framework (e.g., `data-custom="1"`), suppress the warning explicitly using `data-zenzic-ignore`.

```html
<!-- Bad: triggers Z120 -->
<a href="/link" onClick="doSomething()">Link</a>

<!-- Good: standard attribute -->
<a href="/link" class="btn">Link</a>

<!-- Acknowledged debt: suppressed -->
<a href="/link" data-custom="value" data-zenzic-ignore>Link</a>
```
