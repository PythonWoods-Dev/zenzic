---
title: "Zenzic v0.10.0: Async Engine, Native Annotations, and Progressive Adoption"
date: 2026-06-06
authors:
  - pythonwoods
description: "Zenzic v0.10.0: Async Engine, Native Annotations, and Progressive Adoption"
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

Zenzic v0.10.0 introduces a massive performance upgrade with a new **Async Network Engine**, alongside two architectural changes designed strictly for the CI/CD pipeline: **Native GitHub Annotations** and **Destructive Rule Filtering**.

These features are not aesthetic. They are built to solve three specific operational bottlenecks: network-induced CI flakiness, context switching during Pull Request reviews, and the high friction of adopting static analysis in legacy documentation repositories.

<!-- more -->

## Native GitHub Annotations (`--ci`)

When a pipeline fails, developers do not want to dig through raw terminal logs to find the offending line of code.

Zenzic v0.10.0 introduces the `--format github-annotations` formatter. Instead of drawing terminal UI panels, Zenzic emits raw `::error::` workflow commands. GitHub Actions parses these commands natively and injects them as inline annotations directly into the Pull Request diff.

We also introduced the `--ci` shorthand flag. It performs two actions simultaneously:

1. Forces `--strict` mode (escalating all warnings to blocking errors).
2. Sets `--format github-annotations` automatically.

**The result:** Developer Experience is unified. The error is surfaced exactly where the code was changed. The cognitive overhead of mapping a terminal line number back to a file in the IDE is eliminated.

---

## Progressive Adoption (`--only`)

Adopting a strict linter on a mature, undocumented legacy repository usually results in thousands of initial violations. Forcing a team to fix every broken link, missing alt text, and unused asset before merging a single PR is a failure of governance. It blocks adoption.

The `--only` flag solves this by applying a destructive filter to the Zenzic analysis engine. It accepts a comma-separated list of Z-Codes and silently drops all findings that do not match.

```bash
uvx zenzic check all --ci --only Z201,Z204
```

This is the mechanism for **Progressive Adoption**. Tech Leads can deploy Zenzic to block critical security regressions (credential leaks, path traversal) without breaking the build over structural warnings. As the documentation debt is paid down, the `--only` filter can be expanded or removed entirely to enforce the full rule matrix.

---

## The End of Network Non-Determinism

Traditional linters fail in CI environments due to rate-limiting and external link timeouts, introducing unacceptable non-determinism into the build pipeline. Zenzic eliminates this bottleneck entirely by replacing synchronous network requests with an asynchronous I/O architecture.

Zenzic v0.10.0 ships with a new **Async Network Engine** built on `asyncio` and `httpx`, enabling concurrent validation of external links. To eradicate latency across repeated CI runs, we deployed **Atomic Local Caching** with a configurable 24-hour TTL, saving results safely to `.zenzic_cache/external_links.json`.

Furthermore, the engine now features an **Anti-Overfetching Smart Fallback**. When external servers arbitrarily block `HEAD` requests (e.g., returning 403 or 405), Zenzic immediately falls back to a streaming `GET` request, safely aborting the connection before downloading the actual payload. Zero false positives. Zero network non-determinism.

Hostile precision, zero fluff. Upgrade to v0.10.0 via the official `PythonWoods/zenzic-action` composite action or locally via `uv tool upgrade zenzic`.
