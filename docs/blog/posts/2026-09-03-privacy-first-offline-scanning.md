---
title: "Zero Network, By Default: The Privacy Gate for Regulated Documentation"
slug: privacy-first-offline-scanning
date: 2026-09-03
authors:
  - pythonwoods
description: >
  How Zenzic's zero-network-by-default core engine, and the two-file Privacy
  Gate that keeps forbidden internal terms out of committed configuration,
  let regulated teams adopt an automated documentation quality gate without
  sending document content to an external service.
categories:
  - Best Practices
  - CI/CD
  - Security
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

*This is the fourth article in Zenzic's Foundations series on practical adoption patterns. Part 1, [Snapshot Your Debt: Adopting Quality Gates Without Fixing Everything First](2026-08-30-snapshot-your-debt-baseline-quality-gates.md), covers gating on regressions against a frozen baseline. Part 2, [Enforce What Matters First: Progressive Quality Gates with --only](2026-08-31-progressive-quality-gates-only-flag.md), covers narrowing which built-in codes block CI on day one. Neither one touches network access — this article covers a different adoption blocker: whether a gate is allowed to run at all inside an environment that isn't permitted to send document content off-machine in the first place.*

For a regulated team, that permission question usually gets asked before anything else. Security review at a healthcare, finance, or government-contracting organization asks a narrower question than whether an automated documentation check catches broken links well: what does the tool send off-machine, to what destination, and under which conditions. If the honest answer is "we'd have to check," the tool often doesn't get past that stage at all.

<!-- more -->

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

The "protects the graph" half of that tagline is what this article is about, seen from a different angle than the rest of the series: protecting the graph includes not exposing it. Zenzic's core engine has exactly one network-capable code path in the entire scan, it's off by default, and there's a second, independent mechanism — the Privacy Gate — for the specific case of a confidential term making it into a public document at all.

---

## Zero network calls, until you explicitly ask for one

We checked this directly rather than assuming it: across the entire core engine source tree, the only network-calling code anywhere is a single `httpx.AsyncClient`, in `src/zenzic/core/validator.py`, used exclusively to validate external links by making a real HTTP request to each one.

That client doesn't run on a default scan; the gate is written directly into the source — `validate_links = strict and check_external` — so external link validation only happens when `--strict` is passed, and even then `--no-external` can turn it back off.

We tested both states against a real fixture containing a link to a nonexistent domain. Without `--strict`, `zenzic check all` completed with no "Validating links" step in its progress output at all — no DNS lookup, no connection attempt, nothing to log, because nothing ran. With `--strict` added, a real step appeared:

```text
Validating links (1 external URLs)...
```

And a real DNS resolution followed, and failed, with a genuine OS-level error rather than an application-level message:

```text
connection error: [Errno -2] Name or service not known
```

That failure is the proof, not a liability: a fake domain only produces a DNS error if the process genuinely tried to resolve it. Everything else in a `zenzic check all` run — structural parsing, the AST pass, scoring, governance evaluation, the Privacy Gate below — is pure in-memory computation over files already on disk. A team running Zenzic under `--strict --no-external`, or simply without `--strict` at all, has a scan that never opens a socket, and that isn't an inference from reading the code — it's what actually happened, and didn't happen, when we ran it.

## The two-file model: what's shared, and what never leaves the machine

Offline scanning solves "does the tool call home," but not a related and separate problem: a project codename, an internal hostname, or a staging URL that a contributor pastes straight into a Markdown file, which then gets committed and published like any other line of prose. Zenzic's answer to that is a two-file configuration model, not a scanning behavior:

| File | Purpose | Committed? |
|:-----|:--------|:-----------|
| `.zenzic.toml` | Shared project configuration | Yes |
| `.zenzic.local.toml` | Machine-local forbidden patterns | **No** |

`zenzic init` adds `.zenzic.local.toml` to `.gitignore` automatically, and it's real, checked-in protection, not a documentation promise:

```bash
git check-ignore -v .zenzic.local.toml
# .gitignore:16:.zenzic.local.toml .zenzic.local.toml
```

`forbidden_patterns`, the setting that actually declares what's confidential, lives exclusively under `[governance]` in `.zenzic.local.toml`, with no equivalent field available in the shared, committed `.zenzic.toml` — the list of things a team considers too sensitive to name publicly is, by construction, a file that never gets pushed anywhere.

## Z204: the forbidden-term gate

A `.zenzic.local.toml` with a real `forbidden_patterns` list looks like this:

```toml
[governance]
forbidden_patterns = [
    "CODENAME-PHOENIX",
    "internal-staging.example.corp",
]
```

We tested this against a fixture document that mentioned both terms. Both were caught, reported as `POLICY VIOLATION DETECTED`, tagged `Z204`. The run exited with code `2`, and the final score line read exactly:

```text
DQS Final Score: 0/100 (Security Override)
```

`Z204` sits in the same zero-tolerance security tier as `Z201` (`CREDENTIAL_SECRET`) and carries the identical penalty: both collapse the score to 0 unconditionally, and both exit non-zero regardless of any suppression, baseline, or `--only` list a repository has configured. A document either has a forbidden term in it or it doesn't, and Zenzic treats that fact the same way it treats a hardcoded API key.

## Literal strings, not regex — deliberately

`forbidden_patterns` matches as a literal, case-insensitive string, not a regular expression. We confirmed this by including, in the same test fixture, a line containing the literal characters `(?i)` with no actual forbidden term anywhere in it. The scan came back clean, at 94/100, with no false match — the parenthesis-and-question-mark sequence was treated as four ordinary characters to search for, not as a regex flag to interpret.

That restriction is a usability choice, not a performance shortcut applied after the fact: a team declaring "never let this codename appear in public docs" shouldn't also need to know regex escaping rules to declare it safely. Internally, the compiled patterns are merged into a single escaped RE2 union so that matching stays O(1) regardless of how many terms are on the list — but that's an implementation detail behind the literal-string contract, not a second, regex-shaped surface a user has to reason about.

## CI: opt-in, not automatic

Because `.zenzic.local.toml` is gitignored, it typically isn't checked out at all in a CI runner — which means `Z204` doesn't fire in CI by default, not because the check is disabled there, but because the file that would trigger it was never brought along. A team that wants the same forbidden-term enforcement in CI has to provision it explicitly, and Zenzic's own how-to guide documents the mechanism for doing that with a secret rather than a committed file:

```yaml
# GitHub Actions example
- name: Write local zenzic overlay
  run: |
    cat > .zenzic.local.toml << 'EOF'
    [governance]
    forbidden_patterns = ${{ secrets.ZENZIC_FORBIDDEN_PATTERNS }}
    EOF
```

There's no `--forbidden-pattern` CLI flag as a shortcut around this — writing `.zenzic.local.toml` at runtime, from a secret, is the only supported way to get `Z204` enforcement into a pipeline. That's a deliberate narrowing of the surface area: exactly one mechanism to audit, rather than a config file and a CLI flag that both need to be checked for drift.

## Precedence: additive, never a silent override

`.zenzic.toml` and `pyproject.toml [tool.zenzic]` aren't merged with each other — `.zenzic.toml` wins outright if it exists, and `pyproject.toml` is read only as a fallback when it doesn't. `.zenzic.local.toml` sits on top of whichever of those is active. For `forbidden_patterns` specifically, that overlay is additive: patterns declared locally are appended to whatever the shared configuration already declares, never substituted for them. A machine-local override can add confidential terms a shared config doesn't already know about, but it has no way to remove or override a pattern the shared config declares.

## Where this fits with the rest of the series

Part 2's `--only` flag lets a team choose which finding codes are load-bearing for CI today, and it documents explicitly that the `Z201`–`Z205` security tier is always evaluated regardless of what's in that list. `Z204` is part of that same tier, so the same guarantee holds here without needing a separate carve-out. No `--only` list, however narrow, can silently exempt a forbidden term from blocking the build, no matter how the rest of a team's rule coverage is being progressively expanded elsewhere.

## Try it on your own repository

Because the pre-commit hook runs entirely on the contributor's own machine, it's a natural fit for a privacy-sensitive workflow specifically, not just the generally recommended starting point:

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

Either path picks up the zero-network default and the two-file Privacy Gate the same way, with no separate "offline mode" to enable, because offline is what the engine already does unless `--strict` says otherwise.

If you only want a one-off look at whether a candidate term already appears somewhere in a repository — no commitment, nothing added to the workflow yet — `uvx`, pinned, is appropriate for that single run:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all
```

## Closing

Offline-by-default and the Privacy Gate solve two different halves of the same compliance question. The first means a security review doesn't have to ask what a scan sends off-machine, because under default operation, nothing does. The second means that if a confidential term does make it into a document anyway, it's caught with the same zero-tolerance treatment as a leaked credential, using a file that's structurally incapable of being committed alongside the docs it's protecting. Together, they let a regulated team adopt a documentation quality gate as a genuine yes-or-no security question, answered once, rather than a case-by-case exception it has to keep re-justifying.

Full field reference for `forbidden_patterns`, and the complete precedence chain across `.zenzic.toml`, `pyproject.toml [tool.zenzic]`, and `.zenzic.local.toml`, is in the [Configuration Reference](../../reference/configuration-reference.md#local-sanctuary). Step-by-step setup, including the `.gitignore` verification command above, is in [Configure the Privacy Gate](../../how-to/configure-privacy-gate.md).
