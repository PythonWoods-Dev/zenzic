---
title: Z123 Non-HTTP Scheme
description: "Z123 fires when an HTML anchor uses a non-HTTP scheme like mailto: or tel:."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Z123 Non-HTTP Scheme

**Severity:** `note` | **Category:** `informational` | **Penalty:** `0.0 pts`

`Z123` is triggered when an `<a>` tag uses a non-standard protocol scheme (e.g., `mailto:`, `tel:`, `ftp:`).

---

## Why it matters

While valid, these links cannot be verified for integrity by Zenzic's static analyzer. They are flagged as notes so reviewers are aware of unverified external dependencies.

---

## Remediation

This is an informational finding and carries no DQS penalty. No immediate action is required unless the scheme is unintentional.

```html
<!-- Info: triggers Z123 -->
<a href="mailto:support@example.com">Contact Us</a>
```
