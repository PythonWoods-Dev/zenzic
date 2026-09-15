---
title: Z124 Opaque HTML Context
description: "Z124 fires when an HTML tag contains attributes that obfuscate link targets or behaviors."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Z124 Opaque HTML Context

**Severity:** `error` | **Category:** `hygiene` | **Penalty:** `-1.0 pts`

`Z124` is triggered when an `<a>` or `<img>` tag uses blacklisted attributes like `onclick` or `onmouseover`.

---

## Why it matters

Inline event handlers obscure the actual behavior of the link or image, bypassing standard static analysis and posing a potential security risk in documentation context.

---

## Remediation

- Remove inline JavaScript event handlers.
- Use standard links, or bind events externally in a dedicated `.js` file if necessary.

```html
<!-- Bad: triggers Z124 -->
<a href="/link" onclick="trackClick()">Link</a>

<!-- Good: standard behavior -->
<a href="/link" class="trackable">Link</a>
```
