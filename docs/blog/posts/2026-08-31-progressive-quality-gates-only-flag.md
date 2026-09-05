---
title: "Enforce What Matters First: Progressive Quality Gates with --only"
slug: progressive-quality-gates-only-flag
date: 2026-09-05
draft: true
authors:
  - pythonwoods
description: >
  How to turn on real, blocking CI enforcement immediately, without
  requiring every rule to pass on day one — using --only to gate on the
  highest-value finding codes first, then expanding coverage as debt is
  paid down.
categories:
  - Best Practices
  - CI/CD
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

*This is the second article in Zenzic's Foundations series on practical adoption patterns. [Snapshot Your Debt: Adopting Quality Gates Without Fixing Everything First](2026-08-30-snapshot-your-debt-baseline-quality-gates.md) covers how to gate on regressions against a frozen baseline instead of the full historical finding count — read it first if you haven't yet.*

Baseline tracking answers one adoption question: how do you turn a gate on today, on a repository that isn't clean. It does not answer a related one: which rules should that gate actually enforce on day one. Turning on every Z-code at once — structural, navigational, editorial, security — on a legacy repository is its own way of stalling adoption, even with a baseline absorbing the historical count, because every *new* commit still has to satisfy the entire rule set to pass.

<!-- more -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

`--only` is the second half of that protection during adoption: it lets a team choose which findings are allowed to fail the build today, without weakening what the engine actually detects or silently opting out of the categories that matter most.

---

## The reframe: which rules earn day-one enforcement

The instinct, once a baseline is in place, is to flip the gate to "enforce everything, forever, starting now" — a reasonable place to end up, but a poor place to start.

A repository can have real credential leaks and broken links sitting alongside years of accumulated passive-voice sentences and heading-order drift. Those are not the same kind of problem, and they should not be gated with the same urgency. `--only` lets a team declare, explicitly, which finding codes are load-bearing for CI *right now* — and defer the rest without pretending they don't exist.

## What `--only` actually does

`--only` takes a comma-separated list of Z-codes and applies a destructive filter: any finding whose code is not in the list is discarded before it reaches scoring or output. The documented starting point, from Zenzic's own technical-debt guide, enforces the security tier plus broken links first:

```bash
# Start by enforcing only Security Gates and Broken Links
zenzic check all --only Z201,Z202,Z204,Z101,Z104
```

Re-running that exact example against this repository's own documentation today still returns clean — it is real, current CLI behavior, not an illustrative snippet.

`--only` is also fast to fail on a mistake rather than silently doing nothing. Passing an unknown or mistyped code is rejected immediately:

```text
Error: Invalid finding code 'Z999' provided to --only flag.
```

The command exits 1. A team that fat-fingers a code finds out at the command line, not by wondering later why a finding it expected to block the build didn't. Code matching is also case-insensitive: `--only z101,Z204` and `--only Z101,Z204` filter identically. The flag isn't a source of subtle drift based on how someone happened to capitalize it in a CI YAML file.

## The guarantee that makes narrowing safe

Narrowing `--only` down to a handful of codes only works as an adoption strategy if narrowing it can't accidentally remove protection nobody meant to remove. This is the property that makes the whole pattern trustworthy, not a footnote to it. Zenzic's technical-debt guide states the guarantee directly:

> The `Z201`/`Z202`/`Z203`/`Z204`/`Z205` security tier and the `Z110`/`Z111` fatal config-load errors are always evaluated regardless of `--only`'s contents — narrowing the flag to a smaller list, or omitting the security codes entirely, cannot silence them. A minimal `--only Z104` scoped purely to broken links still fails the build on a real credential leak.

In practice, this means a team that narrows `--only` down to exactly the codes they care about this quarter — say, just link-checking — cannot construct a `--only` list, by accident or by omission, that lets a real secret ship. The Z2xx security gate and the Z110/Z111 fatal config-load errors sit outside the filter entirely, evaluated on every run regardless of what you asked for. This is what separates "progressive adoption" from "progressively less protection": the parts of the rule set that were never meant to be optional stay non-optional, no matter how aggressively the rest of the list gets trimmed.

## Expanding the list as debt is paid down

The starting `--only` list is not the destination. As the structural debt captured by the baseline gets paid down, the team adds codes to the `--only` list — heading structure, orphan detection, then editorial policy checks — until the list covers everything `zenzic check all` would enforce unfiltered, at which point `--only` can simply be dropped.

That last tier is worth naming precisely, because it's the one this series' tagline points to directly. Passive-voice detection (`Z518`) and weasel-word flags (`Z519`) are Zenzic's lightweight editorial-policy layer, and they're a reasonable rule to add near the *end* of a progressive rollout rather than the start. They're lower urgency than a broken link or a leaked credential, and slower for a team to burn down since they touch prose style rather than a single fixable fact.¹

## The two patterns together

Baseline tracking and this article's `--only` solve adjacent but distinct problems, and most real adoptions use both. Baseline tracking answers "how do we gate on regressions without fixing the existing backlog first." `--only` answers "which rules are we willing to have block a merge today."

A team commonly starts with a narrow `--only` list *and* a baseline snapshot at the same time: the baseline absorbs whatever the narrow rule set still finds in the existing repository, and the `--only` list keeps the gate from becoming an all-or-nothing wall on day one. As the `--only` list grows, the baseline keeps absorbing what's newly in scope but not yet fixed, so the gate never has to go backward to "everything blocks everything" as a precondition for expanding coverage.

## Try it on your own repository

The pre-commit hook remains the recommended way to try this — no global install, no environment pollution, just an isolated, pinned check on your staged files:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      - id: zenzic-guard
```

(`rev:` should track the latest tagged release rather than being copy-pasted indefinitely — check the repository's release tags before pinning.)

For CI enforcement specifically, pass `--only` as an argument to the same check, starting with the security-and-links list above and expanding it as coverage grows. For a Python project already using a lockfile, declare the analyzer as a project dependency with a compatible-release constraint:

```text
zenzic~=0.30
```

If you only want a one-off look at what a narrow `--only` list would currently catch — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all --only Z201,Z202,Z204,Z101,Z104
```

Whichever path you start from, the pattern is the same: pick the smallest `--only` list that covers what genuinely can't ship broken, let the always-evaluated security tier cover what should never be optional, and grow the list from there.

---

¹ *Note: Zenzic's editorial policy checks (such as passive voice `Z518` and weasel words `Z519`) are lightweight RE2-based regex heuristics designed for fast CI guardrails, not full natural language grammar parsing*. Adding them to a progressive `--only` rollout narrows *when* an already-known class of finding starts blocking the build. It does not change what those checks are able to detect.

## Closing

Between baseline tracking and `--only`, a legacy repository has everything it needs to start real, blocking CI enforcement. It doesn't require either of the two false choices teams usually default to: waiting for the backlog to be clean, or turning on the full rule set and accepting that the first PR after rollout will be unreviewable.

Snapshot the existing debt with a baseline. Choose the smallest `--only` list that covers what actually can't ship broken. Expand both over time, on the team's own schedule — not as a blocking prerequisite to getting a gate at all.

Full reference for `--only`, including flag behavior for `zenzic check` versus `zenzic fix`, is in the [CLI reference](../../reference/cli.md) and the [technical-debt how-to guide](../../how-to/handle-technical-debt.md#progressive-adoption).

Once the gate is running on the codes that matter today, the next question is what happens when a team needs a rule Zenzic doesn't ship at all — the subject of [Bring Your Own Rules: Policy-as-Code Without Forking Zenzic](2026-09-01-custom-rules-policy-as-code.md).
