---
title: "The Quality Pyramid: Four Scored Categories, One Zero-Tolerance Gate"
slug: quality-pyramid-five-layers-of-the-dqs
date: 2026-09-02
authors:
  - pythonwoods
description: >
  A conceptual breakdown of what actually makes up Zenzic's Deterministic
  Quality Score: four weighted categories that can be scored, and a security
  gate that overrides all of them. Explains the model that baseline tracking,
  --only, and custom rules all sit on top of.
categories:
  - Architecture
  - Best Practices
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

![The zenzic score docs --breakdown terminal output showing four weighted quality categories — structural, navigation, content, brand — each reporting 0 issues, followed by a structurally separate SECURITY GATE section where a single Z201 credential finding collapses the final score from 100 to 0](../../assets/images/blog/quality_pyramid_demo.webp)

*This article is a companion piece to Zenzic's Foundations series on practical adoption patterns — [Snapshot Your Debt: Adopting Quality Gates Without Fixing Everything First](2026-08-30-snapshot-your-debt-baseline-quality-gates.md), [Enforce What Matters First: Progressive Quality Gates with --only](2026-08-31-progressive-quality-gates-only-flag.md), and [Bring Your Own Rules: Policy-as-Code Without Forking Zenzic](2026-09-01-custom-rules-policy-as-code.md). Unlike those three, it isn't numbered — it describes the model those three adoption patterns all sit on top of, rather than an adoption pattern in its own right, and it can be read at any point in the sequence, including first.*

Every one of the previous three articles assumes the reader already has a rough mental model of how a Zenzic quality score is put together: that some findings cost points, some findings block CI outright, and those two things are not the same mechanism. None of the three actually lays that model out on its own terms. This article does.

<!-- more -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

## An upfront disclosure

Zenzic doesn't document this as "five layers" anywhere else — not in the CLI, not in `docs/explanation/scoring-system.md`, not in any ADR. This is this article's own way of organizing what the tool actually, verifiably does: four category weights that sum to a score, plus one security mechanism that is architecturally distinct from all four. The number five is accurate to that shape once you count the gate alongside the categories, but it is a synthesis for this piece, not a name you'll find published anywhere else in the project. Treat it as an explanatory lens, not a spec.

## The four categories that get scored

The Deterministic Quality Score (DQS) is a weighted composite of exactly four check categories, documented in [Scoring System](../../explanation/scoring-system.md):

| Category | Weight | Bucket Cap |
| :--- | :---: | :---: |
| Structural Integrity | 30% | 30 pts |
| Navigation Graph | 25% | 25 pts |
| Brand & Governance | 25% | 25 pts |
| Content Excellence | 20% | 20 pts |

Each category has its own bucket cap — a ceiling on how many points that category alone can cost, regardless of how many findings pile up inside it. A repository with fifteen brand violations does not lose more than 25 points to the brand bucket, even if the raw penalty math would otherwise deduct more; the excess is absorbed at the cap rather than compounding indefinitely. That capping behavior matters for what comes next.

## The category that isn't a category

Security findings — `Z201` (`CREDENTIAL_SECRET`), `Z202`/`Z203` (`PATH_TRAVERSAL`/`PATH_TRAVERSAL_FATAL`), `Z204` (`FORBIDDEN_TERM` — the Privacy Gate), `Z205` (`FORBIDDEN_SCHEME` — the XSS Gate, a `javascript:`/`data:` URI scheme) — do not appear anywhere in that four-row table. They are not a fifth weighted bucket sitting alongside structural or content. `docs/explanation/scoring-system.md` calls this out explicitly as an "Inviolable Security Override": if any security finding is detected, the Quality Score collapses to 0/100 unconditionally, independent of how clean the four scored categories are.

We ran `zenzic score docs --breakdown` against a fixture built specifically to isolate this distinction: every one of the four scored categories clean, one deliberately planted `Z201` credential finding. This is the real, current CLI output:

```text
Quality Breakdown
Category      Issues  Weight  Applied Pts
structural    0       30%     -30
navigation    0       25%     -25
content       0       20%     -20
brand         0       25%     -25

SECURITY GATE (Zero-Tolerance Override)
  X Z201 (CREDENTIAL_SECRET): 1 occurrence(s) -> COLLAPSES SCORE TO 0

Final Score: 100 - 100 = 0
```

The layout of that output is the whole argument, before you even read the numbers. `SECURITY GATE (Zero-Tolerance Override)` is set apart from the `Quality Breakdown` table entirely — a separate header, a separate line, evaluated after the four categories rather than as a fifth row inside them. Four categories were computed, weighted, and would have summed to a perfect 100. None of that arithmetic survived contact with a single credential finding. That's the fifth layer: not a fifth thing you can lose points in, but a gate that decides whether the other four are allowed to count at all.

## Why a gate, not a fifth weighted category

A weighted category, by construction, degrades gradually — more findings cost more points, up to that category's bucket cap, and the other categories keep contributing regardless. A gate has no gradient. It is binary: present or absent. Folding security into the same weighted-average machinery as structural or content findings would mean a repository could, in principle, buy back a leaked credential's cost with clean navigation and good prose elsewhere in the same score. That's the wrong shape for a defect where "mostly safe" isn't a meaningful state — a repository either has a leaked secret in it or it doesn't, and no amount of unrelated quality elsewhere changes which of those is true. Keeping the security check outside the weighted average is what makes the zero-tolerance framing literal rather than aspirational.

## What happens when a category collapses without a security breach

It's worth distinguishing the gate from a related but different mechanic: a *scored* category bottoming out on its own, with no security finding involved. `docs/explanation/scoring-system.md`'s own worked CLI example shows this — a fixture with 2 content findings and 15 brand violations, no suppressions, no security findings:

```text
✨ Quality Score: 70/100
  Base Score: 100
  ...
  ! Gravity Cap Enforcement (Brand = 0): -3 pts
  ! Technical Debt (0 suppressions): 0 pts
  = Final Score: 100 - 30 = 70
```

Here, the brand bucket is fully zeroed out (its Applied Pts hit `0.0 / 25.0`), and that triggers a separate mechanism — the Gravity Cap — which caps the pre-debt subtotal at 70 rather than letting a merely-bad category collapse the whole score. That's the contrast worth holding onto: a scored category bottoming out costs a bounded, documented penalty (here, 3 additional points on top of the category's own deductions). A security finding bottoming out costs everything, unconditionally, with no cap on the fall.

## Suppression debt is a separate axis, not a sixth layer

One more mechanic worth ruling out of this model explicitly, so it doesn't get folded in by accident: every active suppression — inline or per-file — deducts a flat 1 point from the score, independent of which category the suppressed finding belonged to. That's not a sixth layer in this model; it's an orthogonal debt count applied after the four categories and the security gate have already been evaluated. The full mathematical derivation of that flat-cost model, including its migration history from an earlier allowance-based approach, is covered in depth in [The DQS Mathematical Model](2026-05-25-dqs-mathematical-model.md) — this article isn't re-deriving that formula, only placing it correctly relative to the four-categories-plus-gate shape described above.

Similarly, severity is a separate axis from category membership. An Error, a Warning, and an Info finding can each belong to any of the four scored categories. A `Z101` broken link and a `Z511` long sentence can both live in the same scored category while carrying entirely different severities. That taxonomy, and how it interacts with `--strict` and SARIF export, is the subject of [Signal-to-Noise in CI/CD](2026-08-14-signal-to-noise-in-ci-cd-managing-diagnostic-severity.md).

## Where the three adoption articles fit on top of this

Once the four-plus-gate shape is clear, the three practical articles in this series read as three different answers to "given this model, where do we start."

Part 1's baseline tracking freezes the *current* count in all four scored categories — but it explicitly does not, and cannot, absorb a security finding into the baseline. A `Z201` credential leak fails the gate on every run regardless of baseline state, because the gate sits outside the category machinery baselining operates on.

Part 2's `--only` flag narrows which codes are allowed to fail a build across the four scored categories. The security tier (`Z201`–`Z205`) and the fatal config-load codes (`Z110`/`Z111`) are always evaluated regardless of what the flag's list contains — for the same structural reason as the baseline case above: they were never part of the weighted-category system `--only` operates on in the first place.

Custom rules add new findings into the same four scored categories a team already has, or introduce a new gate-adjacent policy entirely — the mechanism doesn't grant an escape from the security override any more than a built-in rule does.

None of those three articles restates this underlying shape, because a reader coming to any one of them individually doesn't strictly need it to follow the adoption pattern being described. But the shape is why each pattern behaves the way it does around security findings specifically, and that's worth having in one place.

---

¹ *Note: Zenzic's editorial policy checks (such as passive voice `Z518` and weasel words `Z519`) live inside the Content Excellence category above. They are lightweight RE2-based regex heuristics designed for fast CI guardrails, not full natural language grammar parsing.* Nothing about the four-category-plus-gate model changes what those specific checks are able to detect — it only describes where their findings sit relative to everything else the engine computes.

## Try it on your own repository

The pre-commit hook is the recommended way to try this — no global install, no environment pollution, just an isolated, pinned check on your staged files:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      - id: zenzic-guard
```

(`rev:` should track the latest tagged release rather than being copy-pasted indefinitely — check the repository's release tags before pinning.)

For a Python project already using a lockfile, the analyzer can instead live as a project dependency, declared with a compatible-release constraint rather than an exact pin:

```text
zenzic~=0.30
```

To see the category-plus-gate breakdown directly, rather than just a pass/fail exit code, run:

```bash
zenzic score docs --breakdown
```

If you only want a one-off look at how your own repository's score is currently composed — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 score docs --breakdown
```

Whichever path you start from, the breakdown output is the same one shown above: four weighted categories, and a security gate that sits structurally apart from all of them.

## Closing

Four categories get scored, weighted, and capped. One gate sits outside that scoring entirely and can zero it out regardless of how clean the four categories are. That's the whole model this article set out to describe — and, again, "five layers" is this article's framing for it, not a name Zenzic's own documentation uses. What Zenzic's documentation does state, and what this article has tried to cite precisely rather than approximate, is the real weight table, the real Gravity Cap behavior, and the real, unconditional security override. The three adoption articles in this series each build a practical workflow on top of some part of that shape; this one was only ever meant to make the shape itself visible.

Full derivation of the DQS formula — including the flat suppression-debt model and its migration history — is in [The DQS Mathematical Model](2026-05-25-dqs-mathematical-model.md). Full severity taxonomy — Errors, Warnings, Info, and how they map to `--strict` and SARIF — is in [Signal-to-Noise in CI/CD](2026-08-14-signal-to-noise-in-ci-cd-managing-diagnostic-severity.md). The complete category weight table, Gravity Cap mechanics, and worked example this article draws its numbers from are in [Scoring System](../../explanation/scoring-system.md), and the full 5-stage algorithm specification is in the [Scoring Algorithm Reference](../../reference/scoring-algorithm.md).
