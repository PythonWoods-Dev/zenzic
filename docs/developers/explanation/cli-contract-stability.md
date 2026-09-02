---
title: "CLI Contract Stability"
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CLI Contract Stability

Zenzic is consumed by things that cannot read a release note: CI gates keyed on an exit
code, scripts parsing `--format json`, a pre-commit hook, a GitHub Action, an editor
extension, an MCP server. For those consumers the command-line surface *is* the API, and
a change to it is a change to somebody's build.

This page defines what counts as a breaking change to that surface, and what must happen
when one ships.

## What the contract covers

Four surfaces, in descending order of how loudly a change to them will be felt.

| Surface | Why it is load-bearing |
| :--- | :--- |
| **Exit codes** | The only part of the output a CI gate is guaranteed to read. A changed exit code silently changes what passes. |
| **Machine-readable output** | `--format json`, `sarif`, `github-annotations`. Consumers parse these by field name; a renamed or removed field breaks them without an error message. |
| **Command and option names** | A removed flag is a hard failure at invocation; a *repurposed* flag is worse, because it succeeds and does something else. |
| **Finding-code identity** | `Z201` must always mean what `Z201` meant. Baselines, suppression files and `--only` lists are stored by code. |

The authoritative statement of each of these lives elsewhere and this page does not
duplicate it: exit codes in the [CLI reference](../../reference/cli.md), the finding-code
registry in [Finding Codes](../../reference/finding-codes.md), and what each check emits in
the [Checks reference](../../reference/checks.md). This page defines what may change about
them, not what they currently are.

Human-readable terminal output is deliberately **not** in the contract: colour, panels,
wording and layout change freely. Anything a script needs must come from a machine-readable
format, and any consumer parsing prose output is relying on something Zenzic does not
promise.

## What counts as breaking

A change is breaking if a consumer that was correct before is wrong after, without ever
being told. Concretely:

- **An exit code changes meaning, or a condition changes which code it produces.** Both
  directions count. Widening exit 3 to a new class of input is breaking for anyone whose
  pipeline treated exit 3 as impossible; narrowing it is breaking for anyone who relied on
  it firing.
- **A field disappears, is renamed, or changes type** in any machine-readable format.
  Adding a field is not breaking.
- **A command, subcommand or option is removed or renamed**, or keeps its name and changes
  what it does.
- **A finding code is removed, renumbered, or changes severity** — severity feeds the exit
  code and the score, so it is contract, not presentation.
- **A default changes** such that the same invocation on the same repository produces a
  different exit code.

Two things that are *not* breaking, stated because they have been mistaken for it:

- A finding whose **detection improves** — the same code firing on inputs it should always
  have caught. That is the rule doing its job. It may still change a consumer's exit code,
  so it is announced (see below) but not treated as a contract break.
- A change to prose, colour, ordering or panel layout in terminal output.

## What must happen when one ships

Every breaking change carries all four of these. None is optional, and none substitutes
for another.

1. **A `!` in the commit subject** — `fix(cli)!:`, `feat(check)!:`. This is what makes the
   change findable in history later.
2. **A `CHANGELOG.md` entry under `### Changed` or `### Removed`, marked BREAKING**, that
   names the old behaviour, the new behaviour, and the concrete consumer that breaks. "Any
   script parsing `X` will now see `Y`" — not "improved exit code handling".
3. **A documentation update in the same commit**, not a follow-up: the reference page that
   states the old behaviour is part of the change, per Rule 17.
4. **A test that pins the new behaviour**, so the next change to the same line has to
   argue with a failing assertion rather than a comment.

For an **exit-code** change specifically, one more requirement: state in the CHANGELOG
entry what a consumer should key on instead. An exit code is not something a user can
adapt to by reading the code; they need the replacement spelled out.

## Versioning

Zenzic is pre-1.0 (`0.x.y`). Under SemVer, breaking changes are permitted in a minor
release, and this project takes that permission — but takes it *loudly*. The `0.x`
allowance is a licence to change the contract, not a licence to change it quietly. Every
requirement above applies exactly as it would after 1.0; what `0.x` buys is the absence of
a deprecation cycle, not the absence of an announcement.

After 1.0, add to the above: a deprecation period of at least one minor release, during
which the old behaviour still works and emits a warning.

## Why this page exists

Three exit-code semantics changed within a single development cycle. Usage errors moved
off exit 2, which the contract reserves for a credential breach. The security tier gained
a single evaluation choke point, changing which findings could reach exit 2 and exit 3.
And a content rule stopped firing on a pattern it had always flagged. Each change was
correct and each was individually well-argued. Together they made it clear that the project had a
contract it enforced by memory, and that the memory belonged to whoever happened to be
writing the commit.

The rules above are that contract written down. They are deliberately stricter than what
`0.x` requires, because the consumers this surface has — a CI gate, a hook, an extension —
are exactly the ones that cannot read a version number and decide to be careful.
