---
title: "The DQS Mathematical Model: Flat-Cost Suppressions and Deterministic Gates"
date: 2026-05-25
authors:
  - pythonwoods
description: "The DQS Mathematical Model: Flat-Cost Suppressions and Deterministic Gates"
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

The Documentation Quality Score (DQS) is an integer from 0 to 100. Given the same repository state, it always produces the same number. v0.8.0 changed two things: it closed a gate paradox where CI-blocking codes had zero DQS weight, and it replaced the allowance-based suppression model with a flat-cost model.

<!-- more -->

## The Gate Paradox

Before v0.8.0, the scoring engine had two separate tables: `CODE_SARIF_LEVELS` (used by the CI gate) and a penalty table (used by the DQS calculator). These tables were maintained independently. The invariant — that a CI-blocking code must also deduct from the score — was not enforced.

Three codes broke that invariant:

| Code | Name | SARIF Level | DQS Penalty (before v0.8.0) |
| :--- | :--- | :--- | :--- |
| Z103 | ORPHAN_LINK | `error` | 0 pts |
| Z111 | VIRTUAL_ROUTE_BROKEN | `error` | 0 pts |
| Z113 | AUTHOR_KEY_COLLISION | `error` | 0 pts |

The observable consequence: a repository with 50 ORPHAN_LINK findings would fail the CI gate (exit code 1) but report a DQS of 100. The gate and the score were contradicting each other.

v0.8.0 established a single source of truth: `CodeDefinition`, a `NamedTuple` that stores `severity`, `penalty`, and `category` for each code in one place. `CODE_SARIF_LEVELS` is now derived from it. Structural registration is impossible without a penalty — the paradox cannot recur.

The three paradox codes received their penalties in the migration:

| Code | Name | Penalty | Category |
| :--- | :--- | :--- | :--- |
| Z103 | ORPHAN_LINK | 2.0 pts | Structural |
| Z111 | VIRTUAL_ROUTE_BROKEN | 8.0 pts | Structural |
| Z113 | AUTHOR_KEY_COLLISION | 2.0 pts | Structural |

!!! note "Historical snapshot"
    This table reflects the code registry as of v0.8.0. `Z111` has since been reassigned to a different meaning (`CONFIG_SCHEMA_ERROR`), and `Z113` has been removed entirely — codes referenced in this historical example may since have been renamed or removed.

---

## From Allowance to Flat-Cost

The previous suppression model was allowance-based:

$$
\omega_{\text{debt}} = \max(0,\; n - \text{cap})
$$

Suppressions up to `suppression_cap` were free. Only excess suppressions generated debt. The cap served two roles simultaneously: it was a governance allowance boundary and a hard-fail threshold.

That dual role was the problem. A project with `suppression_cap = 30` and 30 active suppressions had: score impact = 0, exit code = 0. Suppressions were invisible in the DQS.

The v0.8.0 model decouples the two roles:

$$
\omega_{\text{debt}} = n
$$

Every suppression deducts 1 point. The cap is exclusively a hard-fail threshold:

- When $n \leq \text{cap}$: score is reduced by $n$ points. Exit code is determined by the score gate.
- When $n > \text{cap}$: `zenzic score` exits with code 1 immediately, before score gate evaluation.

---

## The Complete DQS Formula

Assembling all five stages:

$$
DQS = \begin{cases}
0 & \text{if } \sum_{c \in \mathcal{S}} n_c > 0 \quad \text{(Security Override)} \\[8pt]
\max\!\left(0,\; S_{\text{gravity}} - n\right) & \text{otherwise}
\end{cases}
$$

where $\mathcal{S} = \{Z201, Z202, Z203, Z204\}$ (as of v0.8.0 — see historical note below), $n$ is the total active suppression count, and:

$$
S_{\text{gravity}} =
\begin{cases}
\min\!\left(S_{\text{base}},\; 70\right) & \text{if } \text{cat\_pts}_{\text{brand}} = 0 \\
S_{\text{base}} & \text{otherwise}
\end{cases}
$$

$$
S_{\text{base}} = 100 - \sum_{i \in \text{tiers}} \min\!\left(\text{Cap}_i,\; \sum_{c \in \text{tier}_i} \text{penalty}_c \times n_c\right)
$$

Or, expanding the full pipeline into a single expression:

$$
DQS = \max\!\left(0,\; S_{\text{gravity}} - \left| F_s \right| \times \text{DebtCost}\right)
$$

where $\left| F_s \right|$ is the total suppression count and $\text{DebtCost} = 1$.

!!! note "Historical snapshot"
    The Security Override set $\mathcal{S}$ reflects v0.8.0. `Z205` (`FORBIDDEN_SCHEME`) was added
    to this set in v0.17.0, after this post was written — the current set has five members, not
    four. The suppression-debt formula itself is unchanged.

---

## Numerical Properties

**Maximum achievable score** is now $100 - n$, where $n$ is the active suppression count. A project with 10 suppressions cannot exceed 90, regardless of finding counts.

**Monotonicity**: $DQS$ is non-increasing in $n$. Adding a suppression never improves the score.

**Score/gate coupling**: the CI gate threshold (configured via `--fail-under`) and the hard-fail suppression threshold (`suppression_cap`) are now independent. A project with a score of 80 and 29 suppressions (cap = 30) passes both. A project with a score of 95 and 31 suppressions (cap = 30) fails the cap gate regardless of the score.

---

## Closing the Mapping Gap

The `CodeDefinition` single source of truth was established to prevent gate/score divergence. But the initial migration targeted only the three paradox codes (Z103, Z111, Z113). A subsequent audit identified four additional codes that the engine could emit (causing Exit 1) while carrying a penalty of 0.0 in the penalty table. The same paradox, at a smaller scale.

Three of the four received penalties in the migration:

| Code | Name | Penalty | Category | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Z401 | MISSING_DIRECTORY_INDEX | 2.0 pts | Navigation | Directory reachable but no index page present |
| Z403 | MISSING_ALT | 1.0 pt | Content | Image with missing `alt` attribute (`is_warning=True`) |
| Z404 | CONFIG_ASSET_MISSING | 3.0 pts | Brand | Favicon or OG image declared in config but absent on disk |

The fourth — **Z602 (I18N_PARITY)** — remains frozen at 0.0 by architectural decision.
I18N_PARITY acts as a governance gate: it enforces language parity between documentation
trees and triggers Exit 1 when parity fails. Assigning it a DQS penalty would conflate
two independent quality dimensions (translation completeness vs. link health / content
quality) into a single number, making the score harder to interpret. A separate ADR is
required to add Z602 to the DQS formula. For now, it is excluded from the penalty table, listed in `FROZEN_CODES`, and defined in `CODE_DEFINITIONS` with penalty `0.0`.

---

## Migration Impact (v0.7.x → v0.8.0)

Projects with active suppressions will see their DQS decrease. The magnitude is exactly the active suppression count:

$$
\Delta DQS = -n
$$

For a project with 10 suppressions previously scoring 75 (under allowance model with $n \leq \text{cap}$), the new score is $75 - 10 = 65$.

The suppression audit output in the CLI is unchanged. The label semantics for `[MANAGED DEBT]` and `[EXTENDED DEBT]` describe governance posture, not score exemption.

---

## See Also

- [Scoring Algorithm Reference](../../reference/scoring-algorithm.md) — Full formula derivation and penalty table
- [Suppression Policy](../../reference/suppression-policy.md) — Three suppression levels and the `--audit` override
- [Finding Codes](../../reference/finding-codes.md) — Full Zxxx code encyclopedia with remediation steps
