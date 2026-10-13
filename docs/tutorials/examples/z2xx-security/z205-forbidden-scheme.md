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

!!! warning "Keep these examples inside the fence"

    This page documents `Z205` by showing the payload it forbids, and it passes
    Zenzic's own gate for a specific reason: the security tier masks **closed,
    well-formed code fences** and nothing else. Move either example out of the
    fence and the page becomes an unsuppressible build failure — `Z205` exits
    `2` and `data-zenzic-ignore` does not apply to it, which is exactly what the
    second example above demonstrates. See
    [Two Masks, Two Questions](../../../explanation/discovery.md#two-masks).
