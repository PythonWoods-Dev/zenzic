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

Capabilities Zenzic has deliberately not shipped yet, and the reasoning behind
each deferral.

### CLI/LSP Topology Model Divergence

**Category:** Architecture — orphan/topology detection
**Status:** Deferred — formally tracked, not silently accepted
**Tracked:** Forthcoming ADR in [ADR Vault](../adr-vault/index.md)
**Related:** `CHANGELOG.md` → `### Known Limitations`

#### What was deferred

A single, shared analysis primitive for orphan/topology detection across the
CLI and the Language Server. Most other pipeline steps — file discovery, rule
engine construction/execution, config loading, adapter resolution — are
already shared between the two. Topology detection is the one significant
area that is not: the CLI's `Z402` (nav-membership-based) and the LSP's
`Z410`/`Z411` (VSM-graph-reachability-based) are two independent algorithms
for related-but-not-identical concepts. A narrower gap in the same family:
`zenzic check all <file>` still cannot be near-instant — the rule-engine pass
now skips non-target files, but full VSM construction and Pass 1-3
security/topology scanning still run project-wide by design, so total time
stays proportional to project size, not target-file size.

#### Why we deferred it

Unifying `Z402`'s nav-membership model with `Z410`/`Z411`'s
VSM-graph-reachability model is a genuine architectural decision, not a
mechanical refactor — the two approaches answer subtly different questions
("is this page in the nav?" vs. "is this page reachable from an entry point
in the VSM graph?"), and collapsing them into one primitive requires deciding
which semantics wins, or whether both need to keep existing under a shared
implementation. That decision needs a real ADR, not an ad hoc code change
buried in an unrelated release.

#### What we will do

Write the ADR that reconciles the two topology models, then implement the
shared primitive it specifies. Near-instant single-file CLI checking needs
the same kind of persistent-process architecture the LSP already has — no
broader change is currently planned for the CLI without one. Until the ADR
exists, the divergence stays open and explicitly disclosed rather than
silently worked around.

#### Mitigation

Both algorithms are independently correct for what they check today — this
is a duplication-of-effort and maintenance-cost problem, not a correctness
gap. Neither the CLI's `Z402` nor the LSP's `Z410`/`Z411` produces wrong
findings because of this divergence; a project running both surfaces may see
the two disagree at the margins on edge cases neither model was designed to
share.

---

## Closed Entries

Each closed entry names what shipped and links to the finding code (or PR)
that resolved it.

### Z112 STALE_ALLOWLIST_ENTRY (logged here as "Z108" while open)

**Resolved as:** `Z112` (`STALE_ALLOWLIST_ENTRY`, `warning`, 1.0 pt,
`structural` category) — see `CHANGELOG.md`'s `[Unreleased]` section for the
full renumbering rationale.

#### What shipped

A check that warns when a prefix declared in
`[link_validation] absolute_path_allowlist` is never actually referenced by
any link in the project. Live emission site in `scanner.py`'s
`_run_vsm_and_urp_pass`, wired through `validator.py` and `_check.py`. Neither
of this entry's originally-cited candidate numbers were used: `Z108` was
already live for an unrelated check (`EMPTY_LINK_TEXT`) by the time this
shipped, and `Z110` (this entry's other original candidate) was already
`CONFIG_SYNTAX_ERROR`. `Z112` — a previously-reserved, unused slot — was
free.

#### How the original deferral concern was addressed

The original entry deferred this on a "Pillar 3" concern: Z110/Z105 decide
independently per link/file with no shared state, and a "used/unused"
determination needs the results of every scanned file reconciled together.
The shipped check avoids redesigning per-file worker independence to get
there. It runs as one aggregation pass over already-collected per-file link
data (`raw_extracted_links`, built during `_run_vsm_and_urp_pass`), in the
main process, after the parallel per-file pass has already returned its
results — the same place the VSM/topology passes already do their own
post-aggregation work, not a new pattern introduced for this check.
The entry's other two original deferral reasons ("wrong category," mixing
content lint with config audit; "YAGNI signal absent," no real-world reports)
were the softer of the three and are not separately re-litigated here — the
check shipped as a `structural`-category content-lint finding rather than
under a dedicated config-audit surface, the alternative home the original
entry proposed.

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

---

## See Also

- [Finding Codes Index](../../../reference/finding-codes.md)
