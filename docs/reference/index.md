---
sidebar_label: Overview
description: "Checks, configuration fields, Policy-as-Code, custom rules DSL, audit mode, and discovery logic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration & Reference Overview

Zenzic reads a single `.zenzic.toml` file at the repository root. All fields are optional — Zenzic works out of the box with zero configuration file.

!!! tip "Zero configuration"

    Most projects need no `.zenzic.toml` at all. Run `uv run zenzic check all` — if it passes,
    you are done. Only add configuration when you need to customize specific behavior or enforce organizational policies.

---

## Reference Sections

This reference collection is organized into focused, authoritative specifications:

| Reference Page | Scope & Contents |
| :--- | :--- |
| **[Configuration Reference](./configuration-reference.md)** | `docs_dir`, exclusion lists, threshold rules, `[policies]` settings, `[governance]` blocks |
| **[Finding Codes Catalog](./finding-codes.md)** | Complete encyclopedia of all 36+ `Zxxx` diagnostic codes, Opt-In policies, and remediation steps |
| **[Scoring Algorithm](./scoring-algorithm.md)** | 5-stage DQS computation, weight matrix, 36-code penalty reference table, and Governance Escalation |
| **[Suppression Policy](./suppression-policy.md)** | Managed Technical Debt framework, 4 suppression levels, Technical Debt Ledger, and `zenzic audit` |
| **[CLI Command Reference](./cli.md)** | Complete guide to `zenzic check`, `zenzic score`, `zenzic audit`, `zenzic lab`, and `zenzic diff` |
| **[Advanced Features](./advanced-features.md)** | Policy-as-Code Engine, Custom Rule SDK v3, Three-Pass Pipeline, and programmatic Python API |
| **[Brand System](./brand-system.md)** | Brand kit, palette tokens (`--zz-*`), and Surface Discipline guidelines |
| **[Glossary](./glossary.md)** | Rigorous definitions for domain terms (VSM, DQS, Policy-as-Code, Audit Mode, Enterprise SARIF) |

---

## Full `.zenzic.toml` Example

A representative `.zenzic.toml` demonstrating core features, Policy-as-Code settings, and governance controls:

```toml
docs_dir = "docs"
excluded_dirs = ["includes", "assets", "stylesheets", "overrides"]
excluded_file_patterns = ["temp_*.md"]
placeholder_max_words = 50
validate_same_page_anchors = false
fail_under = 80

[policies]
required_frontmatter_keys = ["title", "description"]
forbidden_external_domains = ["untrusted-domain.com"]

[governance]
suppression_cap = 30
suppression_cap_fail_hard = true
per_file_ignores = { "docs/archive/*.md" = ["Z101", "Z601"] }

[[custom_rules]]
class_name = "my_rules.ModernRule"

[build_context]
engine = "mkdocs"
default_locale = "en"
locales = ["it"]
```
