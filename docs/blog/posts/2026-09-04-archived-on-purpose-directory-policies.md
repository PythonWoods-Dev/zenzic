---
title: "Archived on Purpose: Exempting One Finding Without Losing the Rest"
slug: archived-on-purpose-directory-policies
date: 2026-09-04
authors:
  - pythonwoods
description: >
  How [governance.directory_policies] in .zenzic.toml lets a team exempt
  deliberately-archived content from one specific finding — like the
  orphan-page check — without turning off every other check on the same
  files, demonstrated against a real fixture with a genuinely broken link.
categories:
  - Best Practices
  - CI/CD
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

*This is the fifth article in Zenzic's Foundations series on practical adoption patterns, following [Snapshot Your Debt](2026-08-30-snapshot-your-debt-baseline-quality-gates.md), [Enforce What Matters First](2026-08-31-progressive-quality-gates-only-flag.md), [Bring Your Own Rules](2026-09-01-custom-rules-policy-as-code.md), and [Zero Network, By Default](2026-09-03-privacy-first-offline-scanning.md). The first of those, on baseline tracking, covers gating on regressions against debt a team intends to pay down over time. This article covers the opposite case: content that is never coming back into the navigation, on purpose, and needs a permanent exemption instead of a temporary one.*

A repository that's been alive for a few years usually accumulates content nobody wants to delete but nobody wants live in the navigation either — a retired migration guide, a deprecated API reference, a changelog for a version nobody runs anymore. It's still worth keeping as a historical record, so it stays in the repository, deliberately dropped from `mkdocs.yml`'s navigation the day it was retired. Every scan since then reports it as an orphan page, and no amount of time passing will make that finding go away, because the file is *supposed* to sit outside the nav permanently. This article answers a specific, practical question: how do you tell Zenzic to stop flagging that one fact about that one directory, without also telling it to stop checking the directory at all.

<!-- more -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

`[governance.directory_policies]` is the mechanism. It removes one finding code from one glob pattern of paths, and nothing else — every other check Zenzic runs against those same files keeps running, unchanged. The rest of this article demonstrates that narrowness directly, on a real fixture, rather than just asserting it.

---

## The fixture: a retired guide with a real, unrelated defect

The demonstration uses a small fixture: `docs/archive/old-migration-guide.md`, a Markdown file that exists on disk but is never listed in `mkdocs.yml`'s navigation, and that contains a genuine broken link — a reference to a page (`removed-target.md`) that was deleted when the migration it documented finished.

Before any exemption is configured, running `zenzic check all` against this fixture reports two separate findings on it: `Z402` (`ORPHAN_PAGE`, "Markdown file not listed in the site navigation") and `Z101` (`LINK_BROKEN`), the genuine broken link. Both are correct. The file really isn't in the nav, and the link really doesn't resolve. The problem isn't that either finding is wrong — it's that one of them (`Z402`) is never going to become right, no matter what anyone does to this file, because staying out of the nav is the entire point of the archive directory. The other (`Z101`) is exactly the kind of thing a quality gate exists to catch, regardless of which directory it happens to live in.

## Declaring the exemption

`directory_policies` lives under `[governance]` in `.zenzic.toml`, as a mapping from a glob pattern to a list of Z-codes exempted for anything that pattern matches:

```toml
[governance.directory_policies]
"docs/archive/**" = ["Z402"]
```

That's the entire declaration, and it says something specific: for any file under `docs/archive/`, do not report `Z402`. It doesn't say anything about `Z101`, `Z410`, `Z502`, or any other code — those keep being evaluated by their own independent logic, exactly as they would anywhere else in the repository. Zenzic's reference documentation describes the mechanism as a zero-debt directory-level policy exemption, and in `--audit` mode a finding removed this way is still surfaced, labeled `[POLICY_EXEMPTION]`, rather than disappearing from the record entirely — a declared exemption stays visible as a declared exemption, not as silence.

## What the same fixture reports after the exemption

Re-running `zenzic check all` against the same fixture, with that `.zenzic.toml` entry in place, produces this:

```text
docs/archive/old-migration-guide.md:1  ⚠  [Z410]  Document is isolated and unreachable from defined entry points: '/archive/old-migration-guide/'

docs/archive/old-migration-guide.md:1  ⚠  [Z502]  Page has only 40 words (minimum 50).

docs/archive/old-migration-guide.md:4  ✘  [Z101]  'removed-target.md' resolves to '/archive/removed-target/' which is not in the Virtual Site Map — the target file may not exist

    4  ❱  longer linked from navigation. It references a [removed page](removed-target.md)

FAILED: Hard errors detected. Exit code 1 is mandatory.
DQS Final Score: 80/100 (Gate Failed)
```

`Z402` is gone from the report — exempted exactly as declared, for exactly this directory. Everything else on the same file, in the same directory, still fires: `Z101`, the genuine broken link, still fails the build with a hard error, exactly as it would with no exemption in place at all. `Z502` (short content) still fires too. And so does `Z410` — a different isolation-related finding, "document is isolated and unreachable from defined entry points" — even though it shares the same underlying cause as `Z402` (the file sits outside the nav graph). The exemption was written for `Z402` specifically, and `Z402` is the only one of the three isolation-adjacent findings that went away.

That last detail is the actual proof this article is built around. It would have been easy to exempt "this directory" in some broader sense and call it done. Instead, the exemption removed one specific claim — "this page should be reachable from navigation" — a claim that was never going to be true for content that's archived on purpose. Every other claim keeps being checked, including whether a genuinely broken link on the very same line resolves, because that claim has nothing to do with navigation reachability.

## Why the scope stays this narrow

Every Z-code in Zenzic encodes a distinct, checkable claim about a document — reachability, link resolution, word count, and so on are independent questions, evaluated independently of each other. `directory_policies` operates at the level of one code against one glob, not at the level of "this directory is special, skip it." A team that wants two exemptions on the same directory declares two codes in the same list; a team that wants the exemption to also cover a sibling directory adds a second glob key. Nothing about the mechanism collapses multiple codes into a single on/off switch for a path — every code keeps evaluating unless it's individually named.

## The hygiene backstop: Z620

An exemption that's declared but never actually matches anything is its own kind of drift — a `.zenzic.toml` entry nobody remembers the reason for, guarding against a finding that no longer occurs. Zenzic tracks this automatically: if a `directory_policies` pattern is never used to suppress a real finding during a scan, Zenzic emits `Z620` (`STALE_GLOBAL_SUPPRESSION`) instead of letting the dead entry sit unnoticed in configuration. In practice, this means a team can't declare a broad `docs/**` exemption "just in case some subdirectory needs it later" without eventually being told, in the same report, that the entry isn't doing anything — the same discipline that governs `per_file_ignores` and the other governance-level exemptions applies here too.

## Where this fits with the rest of the series

A baseline snapshot and `directory_policies` solve visually similar problems — both make a finding stop blocking the build — but they answer different questions about *why*. A baseline exists because a team hasn't gotten to fixing something yet; every baselined finding is, in principle, fixable, and the mechanism is built to shrink as fixes land. `directory_policies` exists because a specific claim was never going to be true for a specific class of content in the first place — an archived page isn't "not yet" reachable from navigation, it's deliberately not, permanently. Reaching for a baseline entry on structurally-permanent content works today but degrades over time into noise nobody re-checks; reaching for `directory_policies` on temporary debt hides something a team actually intends to fix. The two mechanisms are shaped for opposite time horizons, even though both remove a finding from the gate.

The `--only` flag narrows scope along a different axis entirely: it changes which codes block CI *everywhere* in the repository, for every file, without treating any single path specially. `directory_policies` does close to the opposite — it leaves every code active everywhere, and narrows scope down to one code for one glob. The two compose without conflict, because they're orthogonal: `--only` decides what's load-bearing for CI globally, `directory_policies` decides what's structurally exempt for specific paths, and neither mechanism has to know the other exists.

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

Add the `[governance.directory_policies]` block to `.zenzic.toml` under either path, and the exemption takes effect on the very next scan — no separate flag, no CLI opt-in, because governance-level configuration is read the same way regardless of how the analyzer itself got installed.

If you only want a one-off look at whether a specific directory is currently tripping the orphan-page check — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all
```

## Closing

An archive directory and a pile of unfixed debt look similar from the outside — both trip findings that a clean-nav repository wouldn't have. They aren't the same problem, and treating them the same way either leaves permanently-true findings cluttering a baseline forever, or tempts a team toward a broader carve-out that quietly turns off checking on that directory altogether. `directory_policies` exists for the narrower case in between: content whose only real defect is not being in the nav, on purpose, where every other defect a document could have — a broken link, thin content, missing structure — keeps getting caught exactly as it would anywhere else in the repository.

Full field reference for `directory_policies`, including its interaction with `per_file_ignores` and `suppression_cap`, is in the [Configuration Reference](../../reference/configuration-reference.md#directory-policies).

That closes the practical sequence. For the scoring model all five of these mechanisms sit on top of — what actually gets weighted into a score, and what sits outside it entirely — see [The Quality Pyramid: Four Scored Categories, One Zero-Tolerance Gate](2026-09-02-quality-pyramid-five-layers-of-the-dqs.md).
