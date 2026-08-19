---
title: Z121 Missing or Empty Href
description: "Z121 fires when an HTML anchor tag lacks an href attribute or has an empty href/src attribute."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Z121 Missing or Empty Href

**Severity:** `error` | **Category:** `structural` | **Penalty:** `-1.0 pts`

`Z121` is triggered when an `<a>` tag has no `href` attribute (or an empty one), or when an `<img>` tag lacks a `src` attribute.

---

## Why it matters

An anchor without an `href` or an image without a `src` is structurally invalid or relies on undocumented client-side scripting to function, breaking standard link-integrity checks.

---

## Remediation

- Provide a valid `href` or `src` attribute.
- If the tag is intended as a client-side hook (e.g., `<a id="top"></a>`), consider using standard Markdown header anchors.

```html
<!-- Bad: triggers Z121 -->
<a>Click here</a>
<img alt="Missing source">

<!-- Good: standard attributes -->
<a href="/destination">Click here</a>
<img src="/image.png" alt="Valid image">
```
