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
