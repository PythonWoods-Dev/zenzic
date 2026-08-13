---
title: "Signal-to-Noise in CI/CD: Managing Diagnostic Severity"
slug: signal-to-noise-in-ci-cd-managing-diagnostic-severity
date: 2026-08-14
authors:
  - pythonwoods
description: >
  How Zenzic manages diagnostic severity (Errors, Warnings, Info) to prevent CI/CD alert fatigue and integrate cleanly with GitHub Code Scanning.
categories:
  - Engineering
  - CI/CD
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

![Signal to Noise Ratio](../../assets/images/blog/signal_to_noise.webp)

A static analyzer is only as useful as its signal-to-noise ratio. If a tool floods your CI/CD pipeline with hundreds of trivial notices, developers will learn to ignore it. When a real security vulnerability or broken link is introduced, it gets buried in the noise.

In Zenzic, we treat documentation as production code. This means our diagnostic engine must respect the same strict severity taxonomy used by enterprise compilers and security scanners.

<!-- more -->

## The Severity Taxonomy

Every finding emitted by Zenzic (a `RuleFinding`) carries an intrinsic severity level. We categorize anomalies into three strict tiers:

### 1. Errors (The Blockers)
Errors represent critical structural failures or security breaches. 
- **Examples**: `Z101` (Broken Link), `Z201` (Credential Leak), `Z616` (Cross-Namespace Link Forbidden).
- **Behavior**: Errors always fail the build, returning a non-zero exit code (Exit 1 for structural, Exit 2 for security). They cannot be ignored without explicit, tracked suppressions.

### 2. Warnings (The Quality Degraders)
Warnings represent governance violations or content quality degradation. The document is structurally sound, but it violates project standards.
- **Examples**: `Z511` (Excessive Sentence Length), `Z610` (Missing Required Frontmatter).
- **Behavior**: By default, warnings do *not* fail the build. Instead, they deduct points from the repository's **Document Quality Score (DQS)**. 

### 3. Info (The Structural Notices)
Info findings (or "Notes") represent valid architectural patterns that the engine observes, but which do not constitute a defect.
- **Examples**: `Z106` (Circular Link), `Z401` (Missing Directory Index).
- **Behavior**: Info findings never fail the build and do not impact the DQS. In the CLI, they are hidden by default to keep the terminal output clean, unless explicitly requested via the `--show-info` flag.

---

## The `--strict` Gate

In a mature CI/CD environment, warnings should eventually be treated as errors to prevent technical debt accumulation. Zenzic provides the `--strict` flag for this exact purpose.

```bash
zenzic check all --strict
```

When `--strict` is active, **all warnings are promoted to errors** and will fail the build. 

However, `--strict` *never* promotes `Info` findings to errors. Why? Because a circular link (`Z106`)—where a Glossary page links to a CLI page, and the CLI page links back to the Glossary—is a legitimate and often desirable pattern in technical documentation. Punishing valid architectural patterns destroys developer trust.

---

## GitHub Code Scanning and SARIF

The distinction between these three tiers becomes critical when integrating with enterprise dashboards like GitHub Code Scanning.

When Zenzic runs in GitHub Actions, it exports its findings using the industry-standard **SARIF v2.1.0** format. The Zenzic SARIF formatter maps our internal taxonomy directly to OASIS SARIF levels:

- `error` → `error` (Red alert in GitHub)
- `warning` → `warning` (Yellow alert in GitHub)
- `info` → `note` (Gray informational badge in GitHub)

### The Alert Fatigue Problem

GitHub Code Scanning ingests the entire SARIF file. This means that even if `Info` findings are hidden in your local terminal, GitHub will display them as `note` alerts in the Security tab or on Pull Requests.

If your repository has 300 legitimate circular links, GitHub will show 300 `note` alerts. This is the definition of alert fatigue. A developer reviewing a PR might miss a critical `Z201` Credential Leak because it is buried under hundreds of circular link notices.

### The Zero-DBT Solution: Declarative Suppression

To solve this, Zenzic relies on its **Zero-DBT (Zero Documented Technical Debt)** philosophy. If a pattern is intentional, you must declare it in your configuration.

By adding a global directory policy in `.zenzic.toml`, you explicitly tell the engine: *"In this repository, circular links are an accepted design pattern. Do not compute them, and do not export them to SARIF."*

```toml
[governance.directory_policies]
# Suppress circular link notices globally to prevent SARIF noise
"docs/**" = ["Z106"]
```

This single line of configuration stops the engine from emitting the `Info` findings entirely. The terminal remains clean, the SARIF payload is optimized, and GitHub Code Scanning displays only actionable signals.

---

## Conclusion

A deterministic engine must provide deterministic observability. By strictly separating Errors, Warnings, and Info notices, and providing granular, declarative suppression mechanisms, Zenzic ensures that your CI/CD pipeline remains a reliable gatekeeper, not a source of noise.

To learn more about integrating Zenzic into your pipeline, read our [CI/CD Integration Guide](../../how-to/configure-ci-cd.md) or explore the [Finding Codes Taxonomy](../../reference/finding-codes.md).
