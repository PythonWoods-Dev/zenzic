---
title: "Zenzic v0.29.0: Policy-as-Code Expansion"
slug: zenzic-v0290-policy-as-code-expansion
date: 2026-08-13
authors:
  - pythonwoods
description: >
  Zenzic v0.29.0 expands the Policy-as-Code engine with advanced metadata governance, Zero-Trust external linking, and VSM-powered cross-namespace boundary enforcement.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

![Zenzic v0.29.0 Policy-as-Code Expansion](../../assets/images/blog/launch_v0290.webp)

Zenzic v0.29.0 delivers the **Policy-as-Code Expansion** milestone. This release transforms the governance engine into a comprehensive compliance tool, introducing strict metadata validation, Zero-Trust link policies, and topological boundary enforcement.

<!-- more -->

## The Evolution of Documentation Governance

In previous releases, Zenzic focused on structural integrity: ensuring links resolve, images exist, and credentials are not leaked. However, as organizations scale, structural integrity is no longer sufficient. Documentation repositories suffer from "governance drift"—inconsistent metadata, unauthorized external dependencies, and broken internal boundaries.

Zenzic v0.29.0 addresses this by expanding the `[policies]` configuration table. We are moving from implicit conventions to explicit, deterministic contracts enforced directly in CI/CD and the IDE.

All policy evaluations execute in-memory with pure-function determinism (**ADR-075 Radical Unawareness**). The engine performs zero external I/O or network requests during policy verification, ensuring that the Language Server Protocol (LSP) latency remains strictly under 50ms.

---

## Advanced Metadata Governance

While v0.28.0 enforced the *presence* of required frontmatter, v0.29.0 introduces strict validation of frontmatter *content* and *schema*.

### Z612: Forbidden Frontmatter Keys

Legacy documentation often accumulates deprecated metadata (e.g., `draft: true` in production folders, or old taxonomy tags). [`Z612`](../../rules/Z612.md) prevents the use of restricted YAML frontmatter keys. If a key listed in `forbidden_frontmatter_keys` is detected, the engine emits a warning, ensuring legacy metadata is systematically eradicated from the repository.

### Z613: Frontmatter Schema Mismatch

Data integrity requires strict typing. [`Z613`](../../rules/Z613.md) enforces value validation using RE2 regular expressions. Maintainers can define `frontmatter_schema_match` to guarantee that specific keys conform to exact patterns (e.g., ensuring an `author` field contains a valid corporate email). 

To maintain fail-fast determinism, invalid regex patterns in your `.zenzic.toml` are caught during configuration loading, triggering a fatal schema error (`Z111`) before the scan even begins.

---

## Zero-Trust Link Governance

Link rot and insecure protocols are critical documentation defects. Zenzic v0.29.0 introduces a Zero-Trust model for external references.

### Z614: Unapproved Domain Reference

Shadow IT often bleeds into documentation when authors link to unvetted external tools, personal repositories, or deprecated corporate domains. [`Z614`](../../rules/Z614.md) implements a strict whitelist for external links. When `allowed_external_domains` is configured, any link pointing to an unlisted domain triggers a fatal error. 

### Z615: Forbidden URL Scheme

[`Z615`](../../rules/Z615.md) restricts URL protocols to an explicit whitelist defined in `required_url_schemes`. This ensures all external references use secure protocols (e.g., forcing `https://` and blocking `http://`), flagging outdated or insecure schemes before they reach production.

---

## Topological Boundary Enforcement

The most significant architectural addition in v0.29.0 leverages the Virtual Site Map (VSM) to enforce internal repository boundaries.

### Z616: Cross-Namespace Link Forbidden

Large monorepos often contain distinct documentation zones with strict isolation requirements. A common failure mode occurs when a public-facing documentation page inadvertently links to an internal engineering spec. When the public site is built, the link is broken, or worse, it exposes the existence of confidential internal architecture.

[`Z616`](../../rules/Z616.md) prevents internal links from crossing forbidden namespace boundaries.

**Under the Hood:** The engine uses the `InMemoryPathResolver` to compute the canonical target path of every internal link. It does this without executing filesystem I/O. If a link originates in a restricted source namespace (e.g., `docs/public`) and targets a forbidden destination (e.g., `docs/internal`), the build fails deterministically.

---

## Configuration Example

The `[policies]` table in `.zenzic.toml` now supports these advanced constraints:

```toml
[policies]
# Metadata Governance
forbidden_frontmatter_keys = ["draft", "legacy_id"]

[policies.frontmatter_schema_match]
version = "^v\\d+\\.\\d+\\.\\d+$"
author = "^[a-z]+@company\\.com$"

# Link Governance
allowed_external_domains = ["github.com", "zenzic.dev"]
required_url_schemes = ["https", "mailto"]

# Topological Boundaries
[policies.cross_namespace_restrictions]
"docs/public" = ["docs/internal", "docs/drafts"]
```

---

## Diagnostic Summary

| Code | Name | Severity | Category | Penalty | Opt-in |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Z612** | `FORBIDDEN_FRONTMATTER_KEY` | `warning` | `governance` | 3.0 | Yes |
| **Z613** | `FRONTMATTER_SCHEMA_MISMATCH` | `error` | `governance` | 5.0 | Yes |
| **Z614** | `UNAPPROVED_DOMAIN_REFERENCE` | `error` | `governance` | 5.0 | Yes |
| **Z615** | `FORBIDDEN_URL_SCHEME` | `warning` | `governance` | 3.0 | Yes |
| **Z616** | `CROSS_NAMESPACE_LINK_FORBIDDEN` | `error` | `governance` | 8.0 | Yes |

---

## Ecosystem Integration

All new policies are fully integrated across the Zenzic ecosystem. The VS Code extension surfaces these diagnostics in real-time, and the GitHub Action automatically includes them in the Enterprise SARIF output and Audit Mode ledgers.

Update Zenzic to version 0.29.0 using `uv`:

```bash
uv tool update zenzic
```

For detailed remediation steps, consult the [Finding Codes Index](../../reference/finding-codes.md).