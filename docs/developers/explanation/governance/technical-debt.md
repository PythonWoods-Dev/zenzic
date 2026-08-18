---

description: "The deliberate, declared list of capabilities Zenzic chose NOT to ship — and the engineering reasoning that makes each deferral a feature, not an oversight."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Technical Debt Ledger

> *"Hidden debt corrupts trust. Declared debt is engineering."*

This page is the **public, deliberate list** of capabilities Zenzic chose
**not** to ship — and the engineering reasoning
that makes each deferral a conscious design choice, not an oversight.

Zenzic's stance: a project that lints other people's documentation must hold
itself to a higher standard of honesty about its own evolution. Every entry
below names what is missing, why it was deferred, and which milestone owns the
follow-through.

---

## Open Entries

This section details the specifications and guidelines for Open Entries within the Zenzic ecosystem.

### Z108 STALE_ALLOWLIST_ENTRY

**Category:** Configuration hygiene
**Status:** Deferred
**Tracked:** GitHub issue (tracked for future resolution)
**Related:** ADR 011 (removed in v0.8.0)

#### What was deferred

A check that warns when a prefix declared in
`[link_validation] absolute_path_allowlist` is never actually referenced by
any link in the project — i.e. the allowlist entry has become **stale** and
can be safely removed.

#### Why we deferred it

The check is conceptually simple but architecturally expensive:

1. **Pillar 3 violation.** Z110 and Z105 are pure per-link / per-file
   functions — they decide independently in each `pytest-xdist` worker with
   no shared state. A "used / unused" determination requires aggregating
   results across **every** scanned file in **every** worker, then
   reconciling at the end of the run. Introducing aggregate state into the
   validator pass would force a Pillar 3 redesign in a release cycle whose stated
   goal is *consolidation*, not refactor.
2. **Wrong category.** Linting the *content* of documentation and linting
   the *configuration* of the engine itself are different problem spaces.
   Mixing them inflates the validator's scope and obscures which findings
   are about user-authored content vs. project setup.
3. **YAGNI signal absent.** No real-world reports of stale allowlist
   entries exist yet. The current Technical Debt Ledger already has the feature at
   all. Adding a hygiene check for a problem that has never been observed
   would be premature.

#### What we will do in

The natural home for this check is a dedicated configuration-audit surface
under the existing introspection family (today: `zenzic config explain`):
unreferenced allowlist entries, contradictory `excluded_dirs` patterns,
deprecated keys, etc. This separates **content lint** (the validator pass)
from **config audit** (the inspector pass) and keeps both passes pure.

#### Mitigation in

`.zenzic.toml` is small, version-controlled, and code-reviewed at every PR.
A stale allowlist entry is a code-review concern during stabilization, promoted to a
tooling concern during the inspector audit phase. The risk window is bounded: a stale entry can at
worst silence a legitimate Z105 finding for a prefix that no longer needs
silencing — it cannot create false positives, leak data, or weaken any
security check.

---

## Closed Entries

This section will accrue entries as deferred items ship. Each closed entry
will name the version that resolved it and link to the merged PR.

### (none yet — this is the first public Technical Debt Ledger with a published record.)

---

## Why this page exists

Zenzic's first invariant is **Transparency**. An analysis engine that hides its own
shortcomings is not trustworthy: every project that adopts Zenzic should be
able to read this ledger and judge for themselves whether the deferred work
matters to their use case.

Three commitments govern this page:

1. **Every deferral is named.** No silent backlog. A capability that was
   considered and deliberately not shipped lands here.
2. **Every deferral has a reason.** "We ran out of time" is acceptable
   when true; vague hand-waving is not. The reason must be specific enough
   that a future contributor can decide whether the constraint still holds.
3. **Every deferral has an owner.** Either a target release, or an explicit "indefinitely deferred" with the rationale.
   Ledger entries without owners decay into folklore.

When you contribute a deferral here, you are not admitting weakness — you
are protecting the next contributor from rediscovering the same trade-off.

## See Also

- [Finding Codes Index](../../../reference/finding-codes.md)
