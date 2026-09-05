---
title: "Zenzic v0.28.0: Governance & Extensibility"
slug: zenzic-v0280-governance-and-extensibility
date: 2026-08-11
authors:
  - pythonwoods
description: >
  Zenzic v0.28.0 introduces the Policy-as-Code Engine, the Custom Rule SDK v3, Enterprise SARIF integration, and the formal Audit Mode for deterministic compliance reporting.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic v0.28.0 finalizes the **Governance & Extensibility** milestone. This release transitions the engine from implicit structural validation to explicit, declarative governance, while providing enterprise-grade compliance artifacts.

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

## New Governance Diagnostic Codes ([`Z610`](../../rules/Z610.md), [`Z611`](../../rules/Z611.md))

Zenzic v0.28.0 introduces two new diagnostic codes within the governance domain.

### Z610: `REQUIRED_FRONTMATTER_MISSING`

[`Z610`](../../rules/Z610.md) flags Markdown documents missing top-level YAML frontmatter keys declared in `required_frontmatter_keys`.

- **Severity**: `warning`
- **Penalty**: 3.0 points (Governance)
- **Granularity**: Emitted once per missing key per file to enable targeted remediation.

```text
docs/index.md:1  !  [Z610]  Required frontmatter key 'author' is absent.
```

### Z611: `FORBIDDEN_DOMAIN_REFERENCE`

[`Z611`](../../rules/Z611.md) detects links pointing to domains specified in `forbidden_external_domains`. Evaluation covers native Markdown links (`[text](url)`) and raw HTML anchor tags (`<a href="url">`).

- **Severity**: `warning`
- **Penalty**: 3.0 points (Governance)
- **Domain Matching**: Case-insensitive matching covering exact domain matches and all subdomains.

```text
docs/index.md:8  !  [Z611]  Link to 'https://baddomain.com/api' references forbidden domain 'baddomain.com'.
```

---

## Custom Rule SDK v3

To enforce strict metadata governance across the ecosystem, Zenzic v0.28.0 introduces the **Custom Rule SDK v3** and hard-deprecates the legacy v2 API.

### Hard Deprecation of v2 API (Breaking Change)

The legacy `BaseASTRule` class has been removed to eliminate undocumented technical debt (Zero-DBT). Instantiating legacy rules now fails fast with a `PluginContractError`. All custom rules must migrate to SDK v3.

### Typed Extension Framework

The new SDK exposes the `ZenzicRuleV3` base class and requires a typed `RuleMetadata` instance. This ensures that every custom rule explicitly declares its severity, taxonomy category, and DQS penalty.

```python
from zenzic.sdk import ZenzicRuleV3, RuleMetadata


class MyCustomRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="ZZ-CUSTOM",
        title="Custom Rule",
        description="Enforces a specific internal standard.",
        severity="error",
        category="governance",
        penalty=5.0,
    )
```

The SDK contract enforces stateless visitation, guaranteeing O(N) execution complexity. For migration instructions, see the [Custom Rules Guide](../../developers/how-to/write-ast-rule.md).

---

## Enterprise Compliance Artifacts

Zenzic v0.28.0 elevates compliance reporting for enterprise environments, providing deterministic artifacts for security dashboards and audit trails.

### Enterprise SARIF Integration

The SARIF v2.1.0 output (`zenzic check all --format sarif`) has been enriched. The `rules` array now includes `helpUri`, `properties.category`, and `properties.penalty`.

This allows platforms like GitHub Code Scanning to classify and weigh findings according to the Zenzic Document Quality Score (DQS) taxonomy. For schema details, see the [JSON & SARIF API Reference](../../reference/api-json.md).

### Zenzic Audit Mode

We introduced the `zenzic audit` CLI command. Unlike the standard `check` command, Audit Mode generates a formal compliance ledger detailing the repository's state.

The report aggregates:

- **Executive Summary**: Workspace coverage and DQS calculation.
- **Governance Policies**: Active `[policies]` and global suppression caps.
- **Technical Debt Ledger**: A breakdown of active suppressions (inline, per-file, directory policies) and top hotspots.
- **Architectural State**: Active engine adapters and loaded custom SDK v3 rules.

Running `zenzic audit --format json` produces a 100% deterministic, machine-readable payload. We explicitly exclude timestamps to guarantee reproducible compliance builds across CI/CD environments.

---

## Universal Engine Integration

The Policy-as-Code Engine and the new compliance features integrate uniformly across the Zenzic ecosystem:

- **CLI Batch & Interactive Lab**: `zenzic check` and `zenzic lab` evaluate policies alongside structural and content rules.
- **Language Server Protocol**: The VS Code extension surfaces `Z610` and `Z611` inline diagnostics in real-time as maintainers edit documents or configuration files.
- **GitHub Action**: The `zenzic-action` wrapper now supports the `generate_audit_report` input to automatically upload the JSON compliance ledger as a workflow artifact.

For complete CLI options and configuration options, see the [CLI Reference](../../reference/cli.md) and the [Release Governance Protocol](../../developers/how-to/release-governance-protocol.md).

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

Add a `[policies]` section to `.zenzic.toml` to begin enforcing repository governance. To integrate the new Audit Mode into your CI pipeline, update the [Zenzic GitHub Action](../../how-to/configure-ci-cd.md) to `v2.12.0`.
