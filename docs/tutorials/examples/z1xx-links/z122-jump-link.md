---
title: Z122 Jump Link In HTML
description: "Z122 fires when an HTML anchor tag uses a jump link (javascript:void(0) or #)."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Z122 Jump Link In HTML

**Severity:** `warning` | **Category:** `hygiene` | **Penalty:** `-1.0 pts`

`Z122` is triggered when an `<a>` tag specifies `href="#"` or `href="javascript:void(0)"`.

---

## Why it matters

Jump links are an anti-pattern in modern documentation. They usually indicate a button posing as a link, which creates accessibility issues and breaks standard navigation flow.

---

## Remediation

- Use a `<button>` element if the element triggers a script action.
- If it must be an anchor, point to a real anchor ID (e.g., `href="#top"`).

```html
<!-- Bad: triggers Z122 -->
<a href="#">Top</a>
<a href="javascript:void(0)">Action</a>

<!-- Good: standard anchor or button -->
<a href="#top">Top</a>
<button>Action</button>
```
