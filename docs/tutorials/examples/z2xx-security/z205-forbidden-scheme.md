---
title: Z205 Forbidden Scheme
description: "Z205 fires when an HTML anchor uses a critical forbidden scheme (data: or javascript:)."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Z205 Forbidden Scheme

**Severity:** `security_breach` | **Exit code:** `2` | **Suppressible:** `False`

`Z205` is triggered when a critical forbidden scheme like `javascript:` or `data:` is detected in an `href` or `src` attribute.

---

## Why it matters

These schemes introduce severe XSS (Cross-Site Scripting) vulnerabilities. Allowing `javascript:` in documentation links can lead to arbitrary code execution when clicked by readers.

**This code is strictly NON-SUPPRESSIBLE.**
Attempting to suppress it using `data-zenzic-ignore` will fail. The security gate evaluates this rule before any suppression context is parsed.

---

## Remediation

- Remove the `javascript:` or `data:` URL entirely.
- Refactor the documentation example to use plain text or safe standard HTTP schemas.

```html
<!-- FATAL: triggers Z205 (Cannot be suppressed) -->
<a href="javascript:alert(1)">Click</a>

<!-- FATAL: triggers Z205 (Cannot be suppressed) -->
<a href="javascript:alert(1)" data-zenzic-ignore>Click</a>
```
