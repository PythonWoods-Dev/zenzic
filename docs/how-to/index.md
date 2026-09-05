---
title: How-To Guides
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# How-To Guides

Task-oriented, step-by-step instructions for installing, configuring, automating, and extending Zenzic across your documentation projects.

---

## Getting Started & Core Setup

<div class="grid cards" markdown>

- :material-rocket-launch:{ .lg .middle style="color: #6366f1;" } **[Installation & Environment](install.md)**

    ---

    Install Zenzic globally via `uv tool`, ephemerally via `uvx`, or locally with `pip`.

    [:material-arrow-right: Read Guide](install.md)

- :material-tune:{ .lg .middle style="color: #6366f1;" } **[Initialize Configuration](initialize-configuration.md)**

    ---

    Scaffold and fine-tune your project's `.zenzic.toml` policy file with `zenzic init`.

    [:material-arrow-right: Read Guide](initialize-configuration.md)

- :material-microsoft-visual-studio-code:{ .lg .middle style="color: #6366f1;" } **[Editor & VS Code Setup](editor-integrations.md)**

    ---

    Configure real-time in-editor diagnostics, LSP auto-provisioning, and code actions.

    [:material-arrow-right: Read Guide](editor-integrations.md)

</div>

---

## Pipelines & Automation

<div class="grid cards" markdown>

- :material-pipe:{ .lg .middle style="color: #0284c7;" } **[CI/CD Quality Gates](configure-ci-cd.md)**

    ---

    Enforce zero-regression gates in GitHub Actions, GitLab CI, and custom CI pipelines.

    [:material-arrow-right: Read Guide](configure-ci-cd.md)

- :material-shield-badge-outline:{ .lg .middle style="color: #0284c7;" } **[DQS Status Badges](add-badges.md)**

    ---

    Generate and stamp live Document Quality Score shields directly into your `README.md`.

    [:material-arrow-right: Read Guide](add-badges.md)

</div>

---

## Governance & Quality Management

<div class="grid cards" markdown>

- :material-scale-balance:{ .lg .middle style="color: #10b981;" } **[Managing Technical Debt](handle-technical-debt.md)**

    ---

    Audit suppressions, enforce directory policies, and manage the strict `suppression_cap`.

    [:material-arrow-right: Read Guide](handle-technical-debt.md)

- :material-shield-key-outline:{ .lg .middle style="color: #10b981;" } **[Zero-Network Privacy Gate](configure-privacy-gate.md)**

    ---

    Protect private repositories with offline verification and polyglot secret scanning.

    [:material-arrow-right: Read Guide](configure-privacy-gate.md)

- :material-format-letter-case:{ .lg .middle style="color: #10b981;" } **[Integrate Vale and Zenzic](integrate-vale-and-zenzic.md)**

    ---

    Run prose-style and structural-integrity checks in the same pre-commit pass.

    [:material-arrow-right: Read Guide](integrate-vale-and-zenzic.md)

- :material-link-variant:{ .lg .middle style="color: #10b981;" } **[Cross-Site & Remote Links](manage-cross-site-links.md)**

    ---

    Manage external HTTP link timeouts, domain exclusion lists, and offline builds.

    [:material-arrow-right: Read Guide](manage-cross-site-links.md)

- :material-share-variant-outline:{ .lg .middle style="color: #10b981;" } **[Social Metadata & SEO](configure-social-metadata.md)**

    ---

    How Zenzic's asset checker recognizes social card images — setup itself is your build engine's job.

    [:material-arrow-right: Read Guide](configure-social-metadata.md)

</div>

---

## Extensibility & Migration

<div class="grid cards" markdown>

- :material-puzzle-outline:{ .lg .middle style="color: #f59e0b;" } **[Custom Rule Plugins](add-custom-rules.md)**

    ---

    Author deterministic custom rules using the Python Custom Rule SDK v3.

    [:material-arrow-right: Read Guide](add-custom-rules.md)

- :material-swap-horizontal:{ .lg .middle style="color: #f59e0b;" } **[Engine Migration Guide](migrate-engines.md)**

    ---

    Migrate documentation seamlessly between MkDocs and Zensical.

    [:material-arrow-right: Read Guide](migrate-engines.md)

- :material-lifebuoy:{ .lg .middle style="color: #f59e0b;" } **[Diagnostic Troubleshooting](troubleshooting.md)**

    ---

    Comprehensive runbook for diagnosing CI timeouts, cache invalidation, and rule alerts.

    [:material-arrow-right: Read Guide](troubleshooting.md)

</div>
