---
title: "Zenzic v0.28.0: Policy-as-Code Engine"
slug: zenzic-v0280-policy-as-code
date: 2026-08-06
authors:
  - pythonwoods
description: >
  Zenzic v0.28.0 introduces the Policy-as-Code Engine, enabling maintainers to define declarative, deterministic governance policies in .zenzic.toml for required frontmatter keys (Z610) and forbidden external domains (Z611).
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic v0.28.0 introduces the **Policy-as-Code Engine**, allowing maintainers to declare deterministic governance rules directly within `.zenzic.toml`.

<!-- more -->

## Declarative Governance Architecture

Prior releases enforced core structural integrity and static content rules. Project-specific metadata constraints and domain restrictions required manual code reviews or custom hooks.

Zenzic v0.28.0 transitions governance from implicit convention to explicit configuration. The new `[policies]` configuration table establishes a declarative contract for documentation repositories.

All policy evaluations execute in-memory with pure-function determinism (**ADR-075 Radical Unawareness**). The engine performs zero external I/O or network requests during policy verification.

---

## The `[policies]` Configuration Table

Maintainers configure policies within `.zenzic.toml` under the `[policies]` section. The policies section is opt-in and backward-compatible.

```toml
[policies]
# Enforce mandatory YAML frontmatter keys across all Markdown files.
required_frontmatter_keys = ["title", "author", "description"]

# Restrict references to deprecated or forbidden external domains.
forbidden_external_domains = ["baddomain.com", "legacy.corp"]
```

When the `[policies]` section is omitted or empty, policy evaluations are bypassed without computational overhead.

---

## New Governance Diagnostic Codes (`Z610`, `Z611`)

Zenzic v0.28.0 introduces two new diagnostic codes within the governance domain.

### Z610: `REQUIRED_FRONTMATTER_MISSING`

Z610 flags Markdown documents missing top-level YAML frontmatter keys declared in `required_frontmatter_keys`.

- **Severity**: `warning`
- **Penalty**: 3.0 points (Governance)
- **Granularity**: Emitted once per missing key per file to enable targeted remediation.

```text
docs/index.md:1  !  [Z610]  Required frontmatter key 'author' is absent.
```

### Z611: `FORBIDDEN_DOMAIN_REFERENCE`

Z611 detects links pointing to domains specified in `forbidden_external_domains`. Evaluation covers native Markdown links (`[text](url)`) and raw HTML anchor tags (`<a href="url">`).

- **Severity**: `warning`
- **Penalty**: 3.0 points (Governance)
- **Domain Matching**: Case-insensitive matching covering exact domain matches and all subdomains.

```text
docs/index.md:8  !  [Z611]  Link to 'https://baddomain.com/api' references forbidden domain 'baddomain.com'.
```

---

## Universal Engine Integration

The Policy-as-Code Engine integrates uniformly across the Zenzic ecosystem:

- **CLI Batch & Interactive Lab**: `zenzic check` and `zenzic lab` evaluate policies alongside structural and content rules.
- **Language Server Protocol**: The VS Code extension surfaces `Z610` and `Z611` inline diagnostics in real-time as maintainers edit documents or configuration files.

---

## Diagnostic Summary

| Code | Name | Severity | Category | Penalty | Opt-in |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Z610** | `REQUIRED_FRONTMATTER_MISSING` | `warning` | `governance` | 3.0 | Yes |
| **Z611** | `FORBIDDEN_DOMAIN_REFERENCE` | `warning` | `governance` | 3.0 | Yes |

---

## Getting Started

Update Zenzic to version 0.28.0 using `uv`:

```bash
uv tool update zenzic
```

Add a `[policies]` section to `.zenzic.toml` to begin enforcing repository governance.
