---
title: "Snapshot Your Debt: Adopting Quality Gates Without Fixing Everything First"
slug: snapshot-your-debt-baseline-quality-gates
date: 2026-08-30
authors:
  - pythonwoods
description: >
  How to turn on a documentation quality gate today, on a legacy repository
  with hundreds of existing findings, without fixing any of them first —
  using deterministic baseline snapshots to gate on new debt only.
categories:
  - Best Practices
  - CI/CD
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

*This is the first article in Zenzic's Foundations series on practical adoption patterns.*

Every team that considers a new documentation quality gate eventually runs into the same wall: the first scan of a real, multi-year repository does not come back clean. It comes back with hundreds of findings — broken links nobody noticed, orphan pages nobody prunes, headings that drifted out of sequence years ago. The instinctive response is to postpone enforcement until the backlog is cleared. In practice, that backlog is rarely cleared, and the gate never turns on.

<!-- more -->

This is a false choice. You do not need a clean repository to start enforcing a quality gate — you need a gate that distinguishes debt you already knew about from debt you are about to introduce.

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

That protection extends to adoption itself: Zenzic's baseline engine lets a team snapshot its current findings once, then gate CI only on regressions against that snapshot — not on the full historical count.

---

## The reframe: existing debt vs. new debt

The adoption blocker usually gets stated as a single, all-or-nothing requirement:

> "We can't turn on CI enforcement until the documentation is clean."

Baseline tracking splits that requirement into two much smaller ones:

1. **Existing findings** are captured once, tagged, and no longer fail the build.
2. **Any new finding**, or any drop in the overall Document Quality Score (DQS), fails the build immediately.

The repository does not become clean on day one. It becomes *frozen* on day one — nothing gets worse from this point forward, and the team pays down the frozen backlog on its own schedule instead of as a blocking prerequisite.

## How the snapshot actually works

Each finding is matched across runs using a deterministic signature: `SHA-256(RuleCode + PosixPath + ContextTarget)`. Line numbers are deliberately excluded from that signature. This matters in practice — a finding's identity survives someone editing an unrelated paragraph earlier in the same file. Without that exclusion, every baseline would need re-generating after nearly every commit, which would defeat the purpose.

Capturing the current state into `.zenzic-baseline.json` is one command:

```bash
zenzic check all --update-baseline
```

The resulting file is a plain, readable JSON snapshot — this is the exact shape Zenzic's reference documentation shows:

```json
{
  "$schema": "https://zenzic.dev/schemas/zenzic-baseline.schema.json",
  "version": "1.0",
  "created_at": "2026-08-01T17:40:00Z",
  "score": 85.0,
  "findings_count": 3,
  "signatures": [
    "7a2b9f1c3d4e5f6a",
    "8b3c0d2e4f5a6b7c",
    "9c4d1e3f5a6b7c8d"
  ],
  "metadata": {
    "zenzic_version": "0.27.0"
  }
}
```

Every subsequent run consumes that snapshot automatically, once it exists in the workspace root — or explicitly, via `--baseline`:

```bash
zenzic check all --baseline .zenzic-baseline.json
```

Findings that match a signature in the snapshot are not dropped from the report. They are tagged `is_baselined: true` and surfaced in editor integrations and reports, so the debt stays visible instead of disappearing — the engine does not pretend the finding no longer exists, it changes only whether that finding is allowed to fail the build.

## The gate: what actually fails CI

With an active baseline, the CI decision is a two-part rule, not a raw finding count:

- **Exit 0**: every active defect is already present in the baseline snapshot, and the current DQS score is at or above the baseline's recorded score.
- **Exit 1**: a defect appears that is *not* in the baseline snapshot, or the current DQS score drops below the baseline's recorded score.

The score check matters as much as the new-finding check. A change could avoid introducing any single new signature while still degrading the document overall — the score-regression clause closes that gap.

There is also a resolution nudge built into the same flow: when a team fixes baselined issues rather than merely avoiding new ones, Zenzic detects it and prompts a baseline refresh instead of leaving the snapshot stale:

```text
💡 2 baselined issues resolved! Run 'zenzic check --update-baseline' to refresh baseline.
```

That is the mechanism doing the actual work of "pay down debt over time" — the snapshot is not a one-time exemption, it is meant to shrink.

## A real number, from Zenzic's own docs

Baseline debt and suppression debt are two different, complementary levers — worth distinguishing so they aren't conflated. Baseline tracking gates the *build* on regressions; it does not, by itself, change the score. Suppressions (`<!-- zenzic:ignore -->` comments and per-file `.zenzic.toml` ignores) directly cost DQS points at a flat rate of 1 point per active suppression, independent of any baseline.

We ran `zenzic score docs --breakdown` against this repository's own `docs/` tree. It returned 98/100, with exactly 2 of those points coming from 2 active suppressions — matching the flat per-suppression cost model documented in Zenzic's technical-debt guide exactly. Both debt mechanisms make cost visible rather than hiding it. They just apply to different questions: "did this change make things worse?" versus "how much responsibility is the team currently assuming for known exceptions?"

## Putting it into a legacy repository

The tutorial walkthrough for a first audit treats this as its fifth step, after the initial scan:

```bash
# Capture current findings into .zenzic-baseline.json snapshot
zenzic check all --update-baseline
```

```bash
# CI Quality Gate — verify PR against repository baseline
zenzic check all --baseline .zenzic-baseline.json
```

Commit `.zenzic-baseline.json` alongside the code. From that point forward, a pull request that only touches unrelated files passes even though the underlying repository still has all of its original findings — because none of them are new, and the score has not regressed. A pull request that introduces a genuinely new broken link, on the other hand, fails immediately, on exactly the line that broke it.

This is the practical unlock: the team gets a real CI gate on day one, not a promise to gate "once the docs are clean."

---

¹ *Note: Zenzic's editorial policy checks (such as passive voice `Z518` and weasel words `Z519`) are lightweight RE2-based regex heuristics designed for fast CI guardrails, not full natural language grammar parsing.* The baseline mechanism described above applies uniformly to every finding code, editorial ones included. It does not change what those checks can detect — only whether an already-known instance of a detection blocks the build.

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

```toml title="pyproject.toml"
[tool.zenzic]
docs_dir = "docs"
```

```text
zenzic~=0.30
```

If you only want a one-off look at where a repository currently stands — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all --update-baseline
```

Whichever path you start from, the baseline command is the same: `zenzic check all --update-baseline` to freeze current state, then `zenzic check all --baseline .zenzic-baseline.json` in CI going forward.

For the deeper question of *why* those three paths — pre-commit, project dependency, ephemeral `uvx` — exist as distinct enforcement boundaries rather than interchangeable install options, see [Deterministic Tooling & The Pre-Commit Distribution Model](2026-08-23-deterministic-tooling-and-pre-commit.md).

---

## What comes next

Baseline tracking answers "how do we start gating without fixing everything." It does not answer a related but separate question: once a gate is on, how does a team progressively raise the bar on which specific rules it enforces, without re-litigating the whole rule set at once. That is the subject of the next article in this series, on progressive rule adoption — link to follow once it publishes.

For now, the baseline engine gives a legacy repository exactly one thing it did not have before: a CI gate that can turn on today, on the documentation set that already exists, without either lying about its state or blocking on a cleanup project with no defined end date.
