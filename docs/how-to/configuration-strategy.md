---
sidebar_label: "Configuration Strategy"
description: "Two-file configuration model, precedence rules, and a troubleshooting matrix for common Zenzic configuration problems."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration Strategy

This page is a troubleshooting guide for the most common configuration problems. For the full configuration model — file precedence, field definitions, and defaults — see [Configuration Reference](../reference/configuration-reference.md).

---

> **Two-file model summary:** `.zenzic.toml` holds shared project defaults; `.zenzic.local.toml` holds machine-local overrides and is not committed. Scalar fields follow last-write-wins. List fields (`forbidden_patterns`, `excluded_dirs`) are additive.

---

## Troubleshooting Matrix

> **Having issues?** See the [Troubleshooting Guide](troubleshooting.md#configuration).
