---
sidebar_label: Exclusion Design
description: "The design rationale behind Zenzic's conscious exclusion model versus blind automation."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Exclusion Design

This section details the specifications and guidelines for Exclusion Design within the Zenzic ecosystem.

## Conscious Control vs. Blind Automation

Zenzic defaults to **Conscious Control** rather than Blind Automation. Understanding this principle is the key to configuring the tool effectively in production projects.

`respect_vcs_ignore` is `true` by default. This aligns Zenzic with modern static analysis behavior: VCS-ignored paths are skipped unless explicitly included.

**The Noisy `.gitignore` Problem**

Consider a repository where `docs_dir = "."` (the repo root is also the docs root). This is common for projects that lint their `README.md`, `CHANGELOG.md`, and other root-level Markdown files. A typical Python project `.gitignore` contains entries like:

```gitignore
*.egg-info/
.coverage
dist/
htmlcov/
*.pyc
.venv/
```

If `respect_vcs_ignore = true`, Zenzic would silently exclude any documentation file whose path matches these patterns. A `docs/coverage-report.md` page, for instance, would vanish from orphan detection without any diagnostic message. The engine would appear healthy while silently skipping entire documentation subtrees.

**The Explicit `.zenzic.toml` is Superior**

The `excluded_dirs` and `excluded_file_patterns` fields in your project config (L3 in the Layered Exclusion hierarchy) are:

- **Visible** — exclusions are declared in one authoritative file, not scattered across `.gitignore`, `.dockerignore`, and `.npmignore`
- **Reviewable** — a new contributor running `git diff` sees exactly what Zenzic excludes and why
- **Stable** — exclusions do not change when a developer updates `.gitignore` for unrelated tooling reasons

```toml title=".zenzic.toml"
# Explicit exclusions are maintainable and auditable
excluded_dirs = ["includes", "stylesheets", "overrides"]
excluded_file_patterns = ["*.it.md", "CHANGELOG*.md"]

# respect_vcs_ignore = true   ← default; omit or set explicitly
```

**When to enable `respect_vcs_ignore`**

Enable it for projects with a clean, documentation-focused `.gitignore` where VCS-excluded paths genuinely map to documentation that should not be linted (e.g. auto-generated API reference in `site/`). Always audit the exclusion effect using `--show-info` after enabling.

## Governance Score Math

The `fail_under` and `suppression_cap` fields act as **orthogonal constraints**. Each active suppression deducts exactly **1 DQS point** (flat-cost model). The maximum score a project can achieve is therefore:

$$\text{Max Achievable Score} = 100 - |F_s|$$

where $|F_s|$ is the total active suppression count. Configuring `fail_under > 100 - suppression_cap` creates a mathematical contradiction: the score gate will trigger due to suppression debt *before* the suppression cap is reached, making the upper slots of the cap budget unreachable.

**Safe configuration rule:** `fail_under` ≤ `100 - suppression_cap`.

### Designing Hybrid Governance Policies

Setting `fail_under = 90` and `suppression_cap = 30` means: "The global repository quality must never drop below 90/100, **but** regardless of the score, we absolutely refuse to tolerate more than 30 suppressed defects." This prevents teams from hiding massive structural debt even if their active code is otherwise clean.

## See Also

- [Manage Cross-Site Links](../how-to/manage-cross-site-links.md)
