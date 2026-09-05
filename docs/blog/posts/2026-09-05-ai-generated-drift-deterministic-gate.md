---
title: "Looks Right, Isn't: Why AI-Generated Documentation Needs a Deterministic Gate"
slug: ai-generated-drift-deterministic-gate
date: 2026-09-05 08:00:00
draft: true
authors:
  - pythonwoods
description: >
  Why AI-generated edits to documentation are fluent but not necessarily
  correct, and how Zenzic's Policy-as-Code layer — required table columns
  and cell value enums — catches a specification violation that looks like
  an ordinary Markdown table, demonstrated against a real .zenzic.toml
  policy and a real CLI run.
categories:
  - Best Practices
  - CI/CD
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

*This article is the second companion piece to Zenzic's Foundations series on practical adoption patterns, alongside [The Quality Pyramid: Four Scored Categories, One Zero-Tolerance Gate](2026-09-02-quality-pyramid-five-layers-of-the-dqs.md). Like that piece, it isn't numbered among the five adoption-pattern articles — [Snapshot Your Debt](2026-08-30-snapshot-your-debt-baseline-quality-gates.md) through [Archived on Purpose](2026-09-04-archived-on-purpose-directory-policies.md) — because it isn't itself an adoption mechanism. It's a different kind of question: not how to gate what's already broken, but why new damage keeps showing up faster than a reviewer can catch it by reading.*

Every article in this series so far has assumed the finding already exists somewhere in the repository — as accumulated debt, as a deliberately archived exemption, as a rule a team wants to add for its own conventions. This one is about how a new finding gets introduced in the first place. A specific and increasingly common kind of edit causes it: an AI coding assistant reformatting a table, updating a status field, or filling in a missing section. The result reads cleanly and parses without error, while quietly breaking a contract that nothing in the Markdown itself could ever encode.

<!-- more -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

That's the same protection this series has pointed back to from the first article. Zenzic doesn't need to know whether an edit came from a person typing at a keyboard or an agent regenerating a section. It only needs the contract encoded once, as policy, and it checks every edit against that contract the same way, regardless of where the edit came from.

---

## Fluent is not the same as correct

Zenzic's v0.31.0 release article, [Specification-Driven Development & AI Knowledge Graph Integrity](2026-08-22-zenzic-v0310-specification-driven-development.md), named this problem directly in its own subtitle, and it's worth restating rather than paraphrasing, because the framing is precise:

> An AI system consuming a repository does not automatically know which parts of the documentation are authoritative, which values are permitted, which sections are mandatory, or which relationships are required by the development process. If those constraints exist only as conventions in people's heads, they are difficult to enforce consistently. If they are encoded as Policy-as-Code, they become part of the repository's executable contract.

That same article makes the point concrete with a worked example: a `Status` field defined as `draft`, `review`, or `stable` can still receive `approved`, `complete`, or `final` — words that are meaningful, grammatically fine, and still invalid states for that specific specification, because "the Markdown is syntactically valid. The specification is not." The SDD release piece covers the full rule suite that resulted from that observation — `Z521`, `Z522`, `Z523`, and `Z412` — in real depth; this article doesn't re-walk that ground. What it adds is the other half of the argument the release piece didn't have space to make: *why* this particular failure mode is one AI-assisted editing makes more common, not just possible, and one live demonstration of it happening.

## Why this accelerates drift specifically

The SDD article's own language is the right starting point. AI coding assistants are, as it put it, "remarkably good at writing Markdown that *looks* correct, without any way of knowing which parts of that Markdown are load-bearing." That's not a criticism of any particular tool — it's a structural property of the task. An assistant asked to reformat a table, add a row, or update a field is optimizing for producing valid, readable Markdown. Nothing about that task tells it that a `Status` column has a closed vocabulary, or that an `Owner` column is contractually required for every table of this kind. Those constraints live outside the syntax entirely — in a policy file, a style guide, a convention someone explained once in a review comment. An assistant with no access to that policy has no way to know it exists, let alone honor it.

The second half of the argument is about friction, not capability. A person retyping a requirements table by hand tends to notice when a familiar column goes missing, because retyping is slow enough to register what's disappearing. Regenerating the same table programmatically removes that friction along with the manual effort — there's no natural moment where an assistant would pause and ask whether the column it's not producing was supposed to be there. And the same fluency that makes an AI-authored table read cleanly to its author makes it read cleanly to a reviewer skimming a diff. A well-formatted table with a plausible value in every cell doesn't visually signal that anything is wrong, because nothing about it *is* wrong at the level a human reviewer or a Markdown parser can see.

Put together, this is not a claim that AI-generated content is unusually error-prone in general — it's a narrower, more defensible claim: content generated quickly, fluently, and without access to a project's declared contracts will drift from those contracts at whatever rate the contracts go unencoded. The faster documentation changes, the faster that drift compounds, and AI-assisted editing is, among other things, a way of making documentation change faster.

## A fixture, not a hypothetical

The rest of this article is a live demonstration, run today against the current CLI (v0.30.0), not an illustrative snippet. It uses a policy pairing distinct from the SDD article's own example — `required_table_columns` combined with `table_cell_enums` on the same table — so the two pieces don't cover identical ground.

The policy, declared once in `.zenzic.toml`:

```toml
[policies.table_cell_enums]
Status = ["draft", "review", "stable"]

[policies.required_table_columns]
"*" = ["Owner"]
```

The content, `docs/index.md`, exactly the shape of table an assistant could produce while "helpfully" cleaning up or extending an existing requirements section:

```markdown
# Requirements

| ID      | Requirement              | Status   |
| ------- | ------------------------ | -------- |
| REQ-001 | Users can export reports | approved |
```

Nothing about this table is malformed. It's a valid GFM table with a header row, a separator row, and one data row, and it would render correctly on any Markdown viewer. It's also wrong in two independent ways relative to the declared contract: every table in this document is required to carry an `Owner` column, and this one doesn't; and `Status` is restricted to `draft`, `review`, or `stable`, and this cell holds `approved` — a plausible-sounding word that simply isn't one of the three permitted values.

Running `zenzic check all` against it produces this, trimmed to the two policy findings. The same real run also flags two unrelated structural warnings from the fixture's own minimalism — a missing outbound link and a short page — which is why the summary line below counts four warnings against the two shown here.

```text
docs/index.md:3  ⚠  [Z521]  Table missing required column 'Owner' (declared in [policies].required_table_columns under context '*').

    3  ❱  | ID      | Requirement              | Status   |

docs/index.md:5  ⚠  [Z522]  Table cell value 'approved' in column 'Status' is not in allowed enum list ['draft', 'review', 'stable'] (declared in [policies].table_cell_enums).

    5  ❱  | REQ-001 | Users can export reports | approved |

Summary:  ✘ 0 errors  ⚠ 4 warnings  💡 0 info  • 1 file with findings
DQS Final Score: 90/100 (Gate Passed)
```

Both findings point at exactly what's wrong and exactly where: `Z521` (`REQUIRED_TABLE_COLUMN`) at the table's header line, `Z522` (`TABLE_CELL_ENUM`) at the precise data row carrying the invalid value. Neither a syntax formatter nor a prose linter would flag either line — the Markdown is well-formed and the prose is grammatically fine. The only way to catch it is to check the table's content against a contract that was declared once, in policy, ahead of time.

## What this does and doesn't establish

It's worth being precise about the boundary here, in both directions. This mechanism doesn't detect *that* an edit came from an AI assistant — Zenzic has no such capability, and per this project's own determinism invariant, the Core engine has no LLM dependency and makes no probabilistic judgment about authorship at all. What it detects is narrower and, for that reason, reliable: that a table's structure or content no longer matches a contract the project declared. It applies identically whether the edit that broke the contract came from a person, a script, or an agent — which is precisely why it works as a backstop for AI-assisted editing without needing to specifically target it.

The fixture above demonstrates two of the four SDD rules — `Z521` and `Z522` — against one table. `Z523` (`HEADING_ORDER_VIOLATION`) and `Z412` (`TRACEABILITY_BROKEN`) address adjacent failure modes — section ordering and cross-document reference coverage — that aren't exercised in this specific fixture; the [SDD release article](2026-08-22-zenzic-v0310-specification-driven-development.md) and the [Configuration Reference](../../reference/configuration-reference.md#required-table-columns) cover their exact syntax and behavior in full.

## Where this closes the series

Across six pieces, this series has covered baseline snapshots for existing debt, `--only` for scoping day-one enforcement, custom rules for organization-specific conventions, the scoring model those mechanisms sit on top of, zero-network scanning for regulated environments, and permanent exemptions for content that's deliberately outside the navigation. This last piece is less about a single adoption mechanism and more about the reason any of the others end up needing to run at all. Documentation edits are now arriving faster, and from more sources, than a human reviewer can fully verify by reading — and that is the moment a declared, checkable contract stops being optional.

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

For a Python project already using a lockfile, the analyzer can instead live as a project dependency, declared with a compatible-release constraint rather than an exact pin:

```text
zenzic~=0.30
```

Add the `[policies.required_table_columns]` and `[policies.table_cell_enums]` blocks to `.zenzic.toml` under either path, and the next scan checks every table in the repository against them — no separate flag required.

If you only want a one-off look at what a specific table in your own repository currently violates — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all
```

## Closing

An AI assistant regenerating a table isn't doing anything wrong by producing Markdown that looks correct — that's the actual task it was given, and it has no visibility into constraints that were never encoded anywhere it could read them. The fix isn't asking assistants to somehow infer unwritten conventions more carefully. It's writing the convention down once, as policy, so that every edit — human or automated — gets checked against the same contract the same way, deterministically, every time.

Full field reference for `required_table_columns` and `table_cell_enums`, including scope patterns and matching behavior, is in the [Configuration Reference](../../reference/configuration-reference.md#required-table-columns). Full depth on the rest of the SDD rule suite — `Z523` and `Z412` included — is in [Specification-Driven Development & AI Knowledge Graph Integrity](2026-08-22-zenzic-v0310-specification-driven-development.md).

That's the whole series. If you're arriving here first, the practical starting point is [Snapshot Your Debt: Adopting Quality Gates Without Fixing Everything First](2026-08-30-snapshot-your-debt-baseline-quality-gates.md) — freezing existing debt before adding anything else.
