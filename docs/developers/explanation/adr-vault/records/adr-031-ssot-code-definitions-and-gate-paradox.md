---
description: "Architectural Decision Record establishing CodeDefinition as the Single Source of Truth for per-code severity, DQS penalty, and scoring category — closing the Gate Paradox where CI-blocking codes carried zero DQS weight, and introducing the Gravity Cap built on top of that registry."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 031: SSoT Code Definitions & the Gate Paradox

This document details the architectural specification and contract for ADR 031: the `CodeDefinition` Single Source of Truth and the Gravity Cap built on top of it, shipped together in v0.8.0 ("The Governance Engine").

---

## Context

Before v0.8.0, the scoring engine maintained two separate, independently-updated tables: `CODE_SARIF_LEVELS` (consulted by the CI gate to decide pass/fail) and a penalty table (consulted by the DQS calculator to compute the 0-100 score). Nothing enforced the invariant that a CI-blocking code must also deduct from the score.

Three codes broke that invariant in practice: `Z103` (`ORPHAN_LINK`), `Z111` (`VIRTUAL_ROUTE_BROKEN`, since reassigned to a different meaning), and `Z113` (`AUTHOR_KEY_COLLISION`, since removed). All three were registered at SARIF level `error` — CI-blocking — yet carried `0` DQS penalty points. A repository with 50 `Z103` findings would fail `zenzic check all` (exit code 1) while `zenzic score` reported a perfect `100/100`. The gate and the score contradicted each other: **the Gate Paradox**.

---

## Decision

1. **`CodeDefinition` as Single Source of Truth**:
   `codes.py` gains `CodeDefinition`, a `NamedTuple` storing `severity`, `penalty`, and `category` for every Z-code in exactly one place (`CODE_DEFINITIONS`). `CODE_SARIF_LEVELS` (consulted by the CI gate) is now *derived* from this structure at module init, rather than maintained as an independent table. `scorer.py` derives its `_CODE_PENALTY`/`_CODE_CATEGORY` tables from the same source; `_check.py` derives finding severity via `_finding_severity()`. A code cannot be structurally registered without a penalty — the Gate Paradox cannot recur, because there is no longer a second table to drift out of sync with the first.

2. **Gate Paradox Resolution for the 3 Affected Codes**:
   `Z103`, `Z111`, and `Z113` all receive real penalties in the migration (`Z103`: 2.0 pts, Structural; `Z111`: 8.0 pts, Structural; `Z113`: 2.0 pts, Structural — historical figures as of v0.8.0; `Z111`/`Z113` have since been reassigned or removed). A project with only `Z103` findings now scores `98/100`, not `100/100` — the score can no longer contradict the gate.

3. **Gravity Cap**:
   Building on the SSoT registry, if any scoring category's contribution reaches `0.00` (its entire point allocation consumed by findings in that category), the total DQS score is capped at `70`, regardless of how clean the remaining categories are. A document with uncontrolled governance violations (`Z6xx`, brand category) cannot score above `70/100` even if every other category is perfect. This closes the same class of problem as the Gate Paradox one level up: a single fully-failing category must visibly cap the total, not be diluted into a passing average by the other three categories.

---

## Rationale

A registry that can silently diverge into two disagreeing copies of the same fact (severity/penalty/category) is a bug factory. `Z114` (`LARGE_PAGINATION_SET`) was independently confirmed, in the same v0.8.0 migration, to have been miscategorized as `severity="error"` by a `_check.py` catch-all despite being defined as `note` in `CODE_SARIF_LEVELS` — a second, structurally identical instance of the same root cause the SSoT migration was designed to eliminate. Centralizing the fact in one `NamedTuple` per code, with every consumer deriving from it, makes that entire class of drift structurally impossible rather than merely policed by convention.

The Gravity Cap extends the same principle from individual codes to categories. A scoring model that lets three passing categories mathematically dilute a completely failing fourth category into an acceptable-looking average is the category-level version of the Gate Paradox — technically correct arithmetic producing a result that misrepresents the document's real governance state.

---

## Invariants

- Every Z-code's `severity`, `penalty`, and `category` are defined exactly once, in `codes.py`'s `CODE_DEFINITIONS`. No other module may hardcode a competing value for any of the three; `CODE_SARIF_LEVELS`, `scorer.py`'s penalty/category tables, and `_check.py`'s finding severity must all derive from this single source, never redeclare it.
- A CI-blocking (`error`-severity) code must carry a nonzero DQS penalty. The registry's structure makes registering a zero-penalty `error` code impossible by construction, not merely discouraged.
- If any scoring category's contribution reaches `0.00`, the total DQS score is capped at `70`, regardless of the other categories' scores.

---

## Consequences

- `Z103`/`Z111`/`Z113` (and any future code sharing this shape) can no longer produce a passing DQS score while simultaneously failing the CI gate — the two signals are structurally guaranteed to agree.
- A document cannot achieve a high score by having three clean categories mask one completely failing category (most relevant to `Z6xx` brand/governance violations) — the Gravity Cap forces the total to visibly reflect the worst category.
- Adding a new Z-code requires supplying `severity`, `penalty`, and `category` together, in one place, as a condition of registration — there is no code path that defines a finding without also defining how it scores.
- The flat-cost inline-suppression model (every suppression costs `1` DQS point, `suppression_cap` as a hard-fail-only threshold) shipped in the same v0.8.0 release but is a separate decision, cited in source as `ADR-061` — not part of this record's scope. `ADR-061` is itself currently a phantom citation (no vault entry exists), logged separately and not resolved here.

For the DQS scoring model's full formulas, including the bucket-cap architecture and the Gravity Cap in the context of the complete category-weight system, see the [Scoring Algorithm reference](../../../../reference/scoring-algorithm.md) and the [DQS Mathematical Model](../../../../blog/posts/2026-05-25-dqs-mathematical-model.md) blog post.
