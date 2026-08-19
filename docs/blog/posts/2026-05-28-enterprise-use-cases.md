---
title: "Three Zenzic Deployment Patterns for Teams"
date: 2026-05-28
authors:
  - pythonwoods
description: "Three Zenzic Deployment Patterns for Teams"
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic is designed to run inside automated pipelines without configuration drift. On the v0.9.0 line, three patterns appear consistently in production deployments: a quality gate that blocks merges on score regression, a containment strategy for repositories with accumulated link debt, and an i18n parity gate enforcing structural symmetry across translations.

These patterns target different teams at different stages: DevOps teams enforcing merge gates in CI, technical leads scoping governance adoption in repositories with accumulated debt, and documentation engineers maintaining multilingual portals. The patterns are independent and can be combined. A repository with legacy debt can run Pattern 2 to fence exemptions while still enforcing a quality floor via Pattern 1 and structural i18n parity via Pattern 3.

<!-- more -->

## Pattern 1 — CI/CD Quality Gate

Documentation quality drift rarely looks catastrophic in isolation. A broken link here, a suppressed warning there — each individually justifiable. The aggregate effect is a score that drifts down one point per release cycle until the baseline expectation shifts downward to match. The suppression count is the critical signal: when teams learn that adding a `zenzic:ignore` directive prevents a CI failure, the suppression budget becomes the real quality floor rather than the score threshold. Both conditions need to be gated independently.

A quality gate blocks a merge if the documentation score falls below a threshold or if the active suppression count exceeds a budget. Both conditions can co-exist independently.

**Configuration:**

```toml title=".zenzic.toml"
[governance]
fail_under = 80
suppression_cap = 15
```

`fail_under` is a mathematical floor: Zenzic computes the weighted score and exits with code 1 if it falls below 80. `suppression_cap` is a count ceiling: if more than 15 `zenzic:ignore` directives are active at the time of the check, exit code 1 is issued regardless of the computed score.

**GitHub Actions integration:**

```yaml title=".github/workflows/docs.yml"
- name: Check documentation quality
  run: zenzic check all --strict
```

`--strict` elevates all `warning`-severity findings to `error`. Combined with `fail_under`, this enforces both a minimum score and a zero-warning policy. The two controls are independent: removing `--strict` does not change the score; lowering `fail_under` does not relax the warning policy.

**`zenzic diff` for regression detection:**

```bash
zenzic diff main
```

Compares the quality score of the current branch against `main`. Exits with code 1 on regression. Suitable for pull request checks where the absolute score is acceptable but a branch-local regression is not.

---

## Pattern 2 — Legacy Debt Containment

The most common reason teams delay governance adoption is accumulated technical debt. A repository with hundreds of broken links in archived migration guides, deprecated API references, or legacy tutorials cannot pass a strict quality gate without a remediation campaign first — which blocks every other improvement. The result is that governance tooling goes unconfigured rather than progressively adopted. `governance.directory_policies` breaks this deadlock by fencing the debt structurally without touching the affected files.

Repositories with historical documentation debt — archived migration guides, deprecated API references, legacy tutorials — accumulate broken links and stale brand references over time. Eradicating debt from exempted directories blocks releases unnecessarily. `governance.directory_policies` fences it instead.

**Configuration:**

```toml title=".zenzic.toml"
[governance.directory_policies]
"docs/archive/**" = ["Z101", "Z102", "Z601"]
"docs/legacy/**"  = ["Z101", "Z601"]
```

Each key is a glob pattern relative to `docs_dir`. The value is a list of finding codes suppressed for every file that matches. Suppressed findings do not contribute to the quality score for those files and do not count against `suppression_cap`.

This approach isolates the debt rather than distributing inline `zenzic:ignore` directives across hundreds of legacy files. The governance policy remains visible, auditable, and centralized in `.zenzic.toml`.

**Auditing the exempted directories:**

```bash
zenzic check all --audit
```

`--audit` bypasses all suppressions — including `governance.directory_policies` — and reports every finding with a `[POLICY_EXEMPTION]` label. Use this during periodic debt review cycles to quantify the residual finding count before deciding whether to reduce the exemption scope.

---

## Pattern 3 — Sovereign I18N Parity

Locale drift is invisible at authoring time. A contributor adding a new reference page to the English site has no immediate feedback that the Italian mirror is now structurally incomplete. The gap only surfaces when a translated-site user encounters a 404, or when a periodic manual audit catches it — neither of which scales as the documentation site grows. Z602 surfaces this gap at every CI run, before the missing translation reaches production.

Multilingual documentation sites accumulate structural drift: pages added to the default locale are not mirrored in secondary locales, leaving translated sites incomplete. Z602 I18N_PARITY detects this gap at the structural level.

**Configuration:**

```toml title=".zenzic.toml"
[i18n]
enabled = true
default_locale = "en"
locales = ["en", "it"]
strict_parity = true
```

When `strict_parity = true`, every page present in `default_locale` must have a counterpart in every other locale. Missing translations surface as `Z602 I18N_PARITY` findings at `error` severity.

**Enforcement in CI:**

```bash
zenzic check all --strict
```

Z602 findings are `error`-severity by default. `--strict` is not required to block the pipeline on I18N_PARITY violations; it ensures that no other `warning`-class finding silently passes alongside them.

**Gradual adoption:**

If the translation backlog is substantial, set `strict_parity = false` initially and use `governance.directory_policies` to suppress Z602 for specific locale directories that are still under active translation work:

```toml title=".zenzic.toml"
[governance.directory_policies]
"i18n/it/mkdocs-plugin-content-docs/current/reference/**" = ["Z602"]
```

Remove the exemption when the translation reaches structural parity. `zenzic diff main` confirms the removal does not regress the quality score.
