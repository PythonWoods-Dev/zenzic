---
description: "The design rationale behind Zenzic's conscious exclusion model versus blind automation."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Exclusion Design

---

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

```toml title="pyproject.toml"
[tool.zenzic]
excluded_dirs = ["includes", "stylesheets", "overrides"]
excluded_file_patterns = ["*.it.md", "CHANGELOG*.md"]

# respect_vcs_ignore = true   ← default; omit or set explicitly
```

**When to enable `respect_vcs_ignore`**

Enable it for projects with a clean, documentation-focused `.gitignore` where VCS-excluded paths genuinely map to documentation that should not be linted (e.g. auto-generated API reference in `site/`). `--show-info` does not audit exclusion effect — it surfaces `info`-severity findings unrelated to exclusion (e.g. `Z106` circular links). To confirm which value is actually in effect, run `zenzic config explain`, which prints the resolved `respect_vcs_ignore` value alongside its source (default, `.zenzic.toml`, or `pyproject.toml`) — it shows the resolved *setting*, not a per-file list of what was excluded.

---

## Governance Score Math

`excluded_dirs`/`excluded_file_patterns` and the `suppression_cap`/`fail_under` gates are
independent mechanisms with independent math — see
[Dual-Gate Architecture & Suppression Budget](scoring-system.md#dual-gate-architecture-suppression-budget)
for the full `fail_under`/`suppression_cap` formula and worked example, canonical for this
project. The short version relevant to exclusion design: an *excluded* path never reaches the
scorer at all, so it costs nothing against `suppression_cap`; a path that's merely *suppressed*
(via `zenzic:ignore` or a directory policy) does cost against the cap. Choosing exclusion over
suppression for content that should never be linted at all keeps the suppression budget free for
genuine, reviewable technical debt.

---

## See Also

- [Manage Cross-Site Links](../how-to/manage-cross-site-links.md)
