---
description: "Architectural Decision Record for flat-cost suppression debt: every suppression in use deducts one DQS point, suppression_cap is a hard-fail threshold rather than a free allowance, and the constraint the two place on fail_under."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 061: Flat-Cost Suppression Debt

This document records how a suppression is charged in the Documentation Quality Score: what counts as a suppression, what one costs, what `suppression_cap` means, and the constraint the two place on `fail_under`. The flat-cost model shipped in v0.8.0 ("The Governance Engine") and was cited in source as ADR 061 before a record existed; this record was written afterwards, from that release's changelog, its pull request and the code. What the model counts was widened in v0.31.0, recorded below as its own decision.

---

## Context

Before v0.8.0, suppression debt was an allowance:

$$
\omega_{\text{debt}} = \max(0,\; n - \text{cap})
$$

Suppressions up to `suppression_cap` cost nothing, and the cap was at once the size of that free allowance and the hard-fail threshold. A project with `suppression_cap = 30` and 30 active suppressions scored as if it had none: every suppressed finding was invisible in the score.

Until v0.31.0, what `n` counted did not match what silences a finding. Inline directives and `per_file_ignores` entries were counted whether or not they silenced anything, while `directory_policies` silenced findings without being counted at all. A project could move an exception from a per-file entry to a directory policy and gain a point without changing what it hid.

---

## Decision

1. **Flat cost (v0.8.0).** Every suppression deducts exactly one point, after the category penalties and the Gravity Cap ([ADR 031](./adr-031-ssot-code-definitions-and-gate-paradox.md)):

    $$
    S_{\text{final}} = \max(0,\; S_{\text{gravity}} - n)
    $$

2. **The cap is a threshold, not an allowance (v0.8.0).** When `n > suppression_cap`, the run fails with exit code 1 regardless of the score. The cap grants no free suppressions.

3. **What `n` counts (v0.31.0).** `n` is the number of declared exceptions in use — those that silenced a finding in the run:

    - an inline directive — `<!-- zenzic:ignore: Zxxx -->`, its MDX comment form, or a `data-zenzic-ignore` attribute — that silenced a finding on its line;
    - a `per_file_ignores` pattern–code pair that matched a finding;
    - a `directory_policies` pattern–code pair that matched a finding.

    A declaration that silences nothing counts zero and is reported instead: `Z603` inline, `Z620` in configuration. The score, the cap gate, the report footer, `zenzic audit`, and the JSON and SARIF outputs all read this one count.

4. **Exclusions are not suppressions.** `excluded_dirs` and `excluded_file_patterns` remove files from the scan before any finding exists, and add no debt.

5. **Security findings are outside the model.** `Z2xx` codes cannot be suppressed by any mechanism, so they never enter `n`.

---

## Rationale

**Why a flat cost rather than an allowance.** An allowance makes the first `cap` suppressions free, so the score cannot tell a project that fixed its findings from one that silenced them. A flat cost puts every silenced finding in the number and leaves the cap a single meaning.

**Why the unit is the declaration, not the findings it silences.** Four units were measured against this repository's own configuration before v0.31.0: pattern–code pairs declared (17), pairs in use (17), pairs weighted by the files each pattern matches (125), and findings silenced (117). The two proportional units move with content that has nothing to do with the decision to exempt: a new blog post raises the cost of an unchanged `docs/blog/posts/**` policy, and a new decision record adds orphan-page debt under an unchanged policy. A justified exemption would cost more every week. A pair changes only when the configuration changes, or when it stops silencing anything — which is already reported.

**Why in use, not declared.** A declaration that silences nothing hides nothing. Its defect is that it is dead, and `Z603` and `Z620` report exactly that; charging it as debt as well would price the same defect twice, in the wrong unit.

**Why directory policies are charged.** A directory policy silences findings exactly as a per-file entry does. Leaving it free made the broadest mechanism the cheapest one, and made the score depend on which table an exception was written in.

**What the pair does not do.** Under this unit a policy covering a whole tree costs the same, per code, as one covering a single file. Breadth is visible — `--audit` labels every silenced finding `[POLICY_EXEMPTION]` — but not charged: charging it needs a scale, and no measurement supports one.

---

## Invariants

- The score's debt and the cap gate count the same population, from the same count.
- Debt is applied after the Gravity Cap, once per suppression in use — never once per silenced finding.
- A declaration that silences nothing adds no debt and is always reported.
- No suppression is free: there is no allowance below the cap.
- `Z2xx` findings are never suppressed and never counted.

---

## Consequences

- **A project at its cap cannot score above `100 − suppression_cap`.** `zenzic init` writes the resulting constraint, `fail_under <= 100 − suppression_cap`: above it, a project within its cap can fail the score gate on debt alone. The constraint bounds the floor from above; it does not choose one. A floor at exactly `100 − suppression_cap` holds only while the project has no penalised finding at all.
- **The default cap of 30 is not calibrated.** It was the size of the pre-v0.8.0 free allowance and was kept as the threshold when the allowance was removed; no derivation of the number exists. A project is expected to declare the cap it defends — see [`suppression_cap`](../../../../reference/configuration-reference.md#suppression-cap).
- **Counting suppressions in use is a breaking change (v0.31.0).** A project's score drops by the number of directory-policy pairs in use and rises by the number of declarations that silenced nothing. A score baseline recorded under the earlier count measures a different unit.
- The count is reported by mechanism — `inline`, `per-file`, `directory` — in the footer, in `zenzic audit`, and in the JSON and SARIF cap statistics.

For the complete scoring pipeline, see the [Scoring Algorithm reference](../../../../reference/scoring-algorithm.md#suppression-debt); for the mechanisms themselves, the [Suppression Policy](../../../../reference/suppression-policy.md).
