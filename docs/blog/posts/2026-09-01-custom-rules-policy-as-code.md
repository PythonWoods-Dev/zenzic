---
title: "Bring Your Own Rules: Policy-as-Code Without Forking Zenzic"
slug: custom-rules-policy-as-code
date: 2026-09-01
authors:
  - pythonwoods
description: >
  How a team adds its own organization-specific lint rules — a banned internal
  hostname, a forbidden word, a required pattern — directly in .zenzic.toml,
  without forking the engine or maintaining a second linting tool.
categories:
  - Best Practices
  - CI/CD
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

*This is the third article in Zenzic's Foundations series on practical adoption patterns. Part 1, [Snapshot Your Debt: Adopting Quality Gates Without Fixing Everything First](2026-08-30-snapshot-your-debt-baseline-quality-gates.md), covers gating on regressions against a frozen baseline. Part 2, [Enforce What Matters First: Progressive Quality Gates with --only](2026-08-31-progressive-quality-gates-only-flag.md), covers narrowing which built-in codes block CI on day one. Read either first if you haven't yet — this article assumes a gate is already running.*

Every team eventually hits a rule that isn't built in. Not a bug in Zenzic's rule set — a rule specific to *this* organization: a legacy internal hostname that must never leak into public docs, a banned word from a past incident, a naming pattern a style guide requires but no general-purpose tool would ever ship by default. The usual fork in the road is unattractive either way: fork the engine to add one regex, or stand up a second linting tool just to cover the gap, and now the team maintains two configs, two CI steps, and two places a check can silently drift out of sync.

<!-- more -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

The "without a separate tool" clause is not aspirational — it's a real, present-tense feature. `[[custom_rules]]` lets a team declare its own lint rules directly in `.zenzic.toml`, evaluated by the same engine, in the same run, alongside every built-in Z-code. No fork. No second tool. No second CI step to keep synchronized with the first.

---

## The reframe: policy as configuration, not as code you maintain

The instinct when a team needs a rule Zenzic doesn't ship is to reach for something heavier than the problem calls for. That usually means a pre-commit hook shelling out to a hand-rolled script, a second linter installed just for one check, or a fork of the engine itself to add a single pattern match. Each of those solutions works, and each of them adds a second thing to maintain, upgrade, and keep in sync with the first.

`[[custom_rules]]` reframes the problem: a rule that's really "does this pattern appear where it shouldn't" doesn't need code at all. It needs a declaration — an ID, a pattern, a message, a severity — sitting in the same config file that already governs everything else Zenzic checks.

## The DSL: one TOML block, no Python

Verified directly from Zenzic's own how-to guide, this is the real, current syntax:

```toml
[[custom_rules]]
id       = "ZZ-NOINTERNAL"
pattern  = "internal\\.corp\\.example\\.com"
message  = "Internal hostname must not appear in public documentation."
severity = "error"

[[custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"
```

Each `[[custom_rules]]` header — the TOML array-of-tables syntax, double brackets — appends one rule to the list. The pattern is applied line-by-line to every `.md` file; a match produces a finding with the ID, message, and severity you declared, reported exactly like a built-in code.

We ran this against a real fixture: a documentation page with a line referencing `internal.corp.example.com`. The rule fired exactly as declared:

```text
docs/index.md:3:25  ✘  [ZZ-NOINTERNAL]  Internal hostname must not appear in public documentation.
```

Exit code 1. The final score reflected it directly:

```text
DQS Final Score: 94/100 (Gate Failed)
```

One TOML block, no Python file, no plugin scaffolding — and the finding gates the build the same way a built-in `Z1xx` or `Z2xx` finding would.

There's one placement subtlety worth knowing before you add your first rule: root-level keys like `docs_dir` must come *before* any table header in the file. TOML applies a table header to every key that follows it, so a root key written after a `[section]` silently becomes that section's sub-key instead of a top-level setting. Once the root keys are in place, `[[custom_rules]]` blocks can go anywhere after them; there's no required ordering relative to other tables like `[build_context]`.

```toml
# Correct ordering — root keys first, tables in any order after that
docs_dir = "docs"

[[custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"

[build_context]
engine = "mkdocs"
```

A few pattern-writing habits carry over directly from the how-to guide's own reference table. Use `(?i)` for case-insensitive matching, and escape literal dots in hostnames (`internal\.corp\.example\.com`). A bare pattern like `EXAMPLE` matches anywhere on the line with no anchors required, so use `\b` word boundaries to avoid it accidentally matching inside `EXAMPLES`.

## Fail-fast, not silently wrong

The pattern field is compiled with RE2 (`zenzic.core.regex`, ADR-013) — the same regex engine every built-in rule uses, not Python's `re` module. That constraint isn't just a performance detail; it changes what happens when a rule is written wrong.

We tested this directly: a pattern using a lookahead — `foo(?=bar)` — a construct RE2 does not support. It doesn't match nothing and pass silently. It fails immediately, at config-load time, before the scan even starts:

```text
RE2 compilation failed: b'invalid perl operator: (?='. Note: RE2 does not support lookarounds (?=...) or backreferences.
```

Real exit code 1. That's the property that makes custom rules safe to hand to a team that isn't deeply familiar with regex engines: a rule that looks like it should work but silently doesn't is a worse failure mode than a rule that refuses to load at all. RE2's restricted grammar — no lookarounds, no backreferences, no catastrophic-backtracking constructs — trades a small amount of pattern expressiveness for the guarantee that if a custom rule loaded, it's actually doing what its pattern says.

## When a regex genuinely isn't enough

`[[custom_rules]]` covers a real slice of organization-specific policy, but it's a line-by-line regex match, deliberately — it has no access to document structure. If what you actually need is structural (heading hierarchy, paragraph counts, HTML tag attributes), the DSL is the wrong tool, and the project has a second one: the **Custom Rule SDK v3** (`ZenzicRuleV3`, registered via `.zenzic/rules/*.py` auto-discovery or an explicit `class_name` in `.zenzic.toml`). The two aren't competing options — they're two tiers of the same mechanism, picked by how much structure a rule actually needs. Most organization-specific policy (banned hostnames, forbidden words, required boilerplate patterns) lives comfortably in TOML; structural policy needs the SDK. The full SDK v3 migration story — including the breaking change from the legacy v2 API — is covered in depth in [Zenzic v0.28.0's governance and extensibility release notes](2026-08-11-zenzic-v0280-governance-and-extensibility.md); this article stays focused on the TOML DSL, which is where the adoption story above actually lives.

## Where this fits with baseline and `--only`

Part 1's baseline tracking and Part 2's `--only` flag both answer *when* a rule starts blocking the build. This article answers a different question: *what rules exist to enforce in the first place*, beyond what ships in the box. All three compose cleanly, because a custom rule produces a finding exactly like a built-in one — it has a code (`ZZ-NOINTERNAL`), a severity, and a place in the scan output.

That means a freshly added custom rule can be dropped straight into a baseline snapshot if a repository already has pre-existing violations of it, and it can be added to (or left out of) an `--only` list the same way any built-in code would be. A new org-specific rule doesn't bypass either adoption pattern — it just becomes one more code those patterns already know how to handle.

## Try it on your own repository

The pre-commit hook is the recommended way to try this — no global install, no environment pollution, just an isolated, pinned check on your staged files, with your `[[custom_rules]]` block already living in `.zenzic.toml` at the repo root:

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

Either way, the custom rule itself needs nothing beyond the `[[custom_rules]]` block shown above in `.zenzic.toml` — there's no separate install step for the DSL.

If you only want a one-off look at whether a candidate rule actually catches what you think it catches — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all
```

Whichever path you start from, the rule itself lives in the same `.zenzic.toml` a repository already has — there's nothing new to wire up beyond the `[[custom_rules]]` block itself.

---

*A brief scope note: `[[custom_rules]]` and the Custom Rule SDK are regex- and AST-structural mechanisms, respectively — pattern matching and document structure, not semantic language understanding. They're a different mechanism from Zenzic's own built-in editorial-policy codes (passive voice `Z518`, weasel words `Z519`), which are themselves lightweight RE2-based heuristics rather than full NLP grammar analysis. Custom rules extend what a team can *declare* as policy; they don't add semantic understanding beyond what regex or AST structure can express.*

## Closing

Across all three articles in this sequence, a legacy repository now has a complete on-ramp. Freezing existing debt with a baseline (Part 1) and narrowing which built-in codes are load-bearing on day one with `--only` (Part 2) get a gate running before the documentation is clean. Extending the rule set itself with organization-specific policy, in the same config file, with no second tool to maintain, is this article's contribution. None of it requires the documentation to be clean first, and none of it requires forking the engine to say "this specific thing must never appear in our docs."

The next article in this series has not been scheduled yet.
