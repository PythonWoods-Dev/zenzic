---
sidebar_position: 6
sidebar_label: "Scoring Algorithm"
description: "The Zenzic scoring engine: 5-tier weight matrix, per-code penalty table, Gravity Cap, Governance Escalation, Suppression Debt formula, and Security Override."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Scoring Algorithm

The Zenzic Documentation Quality Score (DQS) is a **deterministic, 0–100 integer** computed from the findings of every active check. Given the same repository state, the algorithm always produces the same score.

> For design rationale, a worked example, and CLI output interpretation, see [Scoring Design](../explanation/scoring-design.md).

---

## Architecture Overview {#overview}

The scoring pipeline has five sequential stages:

```text
1. Security Gate    → Z2xx finding? score = 0, early return.
2. Penalty Table    → per-code deductions, per-tier caps.
3. Governance Esc.  → exponential amplification if Z6xx > 10.
4. Gravity Cap      → brand score = 0 ⟹ total ≤ 70.
5. Suppression Debt → subtract ω_debt from capped total.
```

Each stage is described below with its full formula.

---

## Stage 1 — Security Override {#security-override}

Before any score computation, the engine checks for **Z2xx findings**:

$$
S_{\text{final}} = 0 \quad \text{if } \sum_{c \in \mathcal{S}} n_c > 0
$$

where $\mathcal{S} = \{Z201, Z202, Z203, Z204\}$.

This is an **unconditional early return** — no flags, no config options, and no suppressions can bypass it. The four codes in $\mathcal{S}$ represent binary failure conditions:

| Code | Name | Condition |
| :--- | :--- | :--- |
| Z201 | CREDENTIAL | Credential pattern detected in document |
| Z202 | PATH_TRAVERSAL | Link target escapes `docs/` to a non-system path |
| Z203 | PATH_TRAVERSAL_FATAL | Link target resolves to an OS system path |
| Z204 | FORBIDDEN_TERM | Privacy Gate — confidential term exposure |

When the Security Override fires, `ScoreReport` returns `security_override=True` and `security_findings=N` (total Z2xx count). The `--strict` flag and `fail-on-error` configuration are irrelevant — the gate operates before all of them.

!!! danger Security Codes Are Non-Suppressible
    No inline `<!-- zenzic:ignore -->`, no `per_file_ignores`, and no `excluded_dirs` can suppress a Z2xx finding. The finding still fires. The score is still 0.

---

## Stage 2 — Penalty Table and Tier Caps {#penalty-table}

If no Z2xx finding is present, the engine computes a per-tier score.

### Zenzic Weight Matrix (5-Tier)

| Tier | Category | Codes | Weight | Cap |
| :--- | :--- | :--- | ---: | ---: |
| Security Gate | — | Z2xx | — | score = 0 |
| Structural | `structural` | Z1xx | 30% | 30 pts |
| Navigation | `navigation` | Z3xx, Z4xx | 25% | 25 pts |
| Content | `content` | Z5xx | 20% | 20 pts |
| Governance | `brand` | Z404, Z405, Z406, Z6xx | 25% | 25 pts |

### Per-Category Formula

For each tier $i$:

$$
\text{cat\_pts}_i = \max\!\left(0,\; w_i \times 100 - \sum_{c \in \text{tier}_i} \text{penalty}_c \times n_c\right)
$$

The **Category Cap Invariant** guarantees that a single tier cannot drag the score below its floor. For example, 1 000 occurrences of Z505 (1 pt each) exhaust the content bucket at −20 pts. The remaining 80 pts from other tiers are unaffected.

### Base Score

$$
S_{\text{base}} = \sum_{i \in \{\text{structural, navigation, content, brand}\}} \text{cat\_pts}_i
$$

### Penalty Reference Table

| Code | Name | Penalty / occurrence | Tier |
| :--- | :--- | ---: | :--- |
| Z101 | LINK_BROKEN | 8.0 pts | Structural |
| Z102 | ANCHOR_MISSING | 5.0 pts | Structural |
| Z103 | ORPHAN_LINK | 2.0 pts | Structural |
| Z104 | FILE_NOT_FOUND | 8.0 pts | Structural |
| Z105 | ABSOLUTE_PATH | 2.0 pts | Structural |
| Z107 | CIRCULAR_ANCHOR | 1.0 pts | Structural |
| Z106 | CIRCULAR_LINK | 0.0 pts | Informational (no DQS impact) |
| Z108 | EMPTY_LINK_TEXT | 1.0 pts | Structural |
| Z110 | STALE_ALLOWLIST_ENTRY | 1.0 pts | Structural |
| Z111 | VIRTUAL_ROUTE_BROKEN | 8.0 pts | Structural |
| Z113 | AUTHOR_KEY_COLLISION | 2.0 pts | Structural |
| Z301 | DANGLING_REF | 4.0 pts | Navigation |
| Z302 | DEAD_DEF | 1.0 pts | Navigation |
| Z303 | DUPLICATE_DEF | 3.0 pts | Navigation |
| Z402 | ORPHAN_PAGE | 4.0 pts | Navigation |
| Z401 | MISSING_DIRECTORY_INDEX | 2.0 pts | Navigation |
| Z501 | PLACEHOLDER | 2.0 pts | Content |
| Z502 | SHORT_CONTENT | 1.0 pts | Content |
| Z503 | SNIPPET_ERROR | 10.0 pts | Content |
| Z505 | UNTAGGED_CODE_BLOCK | 1.0 pts | Content |
| Z403 | MISSING_ALT | 1.0 pts | Content |
| Z405 | UNUSED_ASSET | 3.0 pts | Governance |
| Z404 | CONFIG_ASSET_MISSING | 3.0 pts | Governance |
| Z406 | NAV_CONTRACT | 2.0 pts | Governance |
| Z601 | BRAND_OBSOLESCENCE | 2.0 pts | Governance |

!!! note Z106 — Knowledge Graph telemetry, not a defect
    Z106 is excluded from the penalty table by design. Elevating it to a scored finding would deduct Quality Score points, pressuring engineers to remove cross-links to satisfy the quality gate — a perverse incentive that degrades real documentation quality. Circular links in a Knowledge Graph are structural data, not defects. Z106 is emitted as topological telemetry; inspect it with `--show-info`.

!!! note Z602 is not scored
    Z602 (I18N_PARITY) is a Governance gate that fires as a standalone finding. It does not contribute to any DQS bucket and therefore has no penalty value in the table above.

---

## Stage 3 — Governance Escalation {#governance-escalation}

Beyond 10 Z6xx occurrences, the engine applies an exponential amplifier to the Governance bucket deductions:

$$
  \text{deduction}_{\text{brand}}' = \min\!\left(\text{cap}_{\text{brand}},\; \text{deduction}_{\text{brand}} \times 2^{n_{\text{excess}} / 5}\right)
$$

where $n_{\text{excess}} = n_{Z6xx} - 10$.

The deduction is capped at the Governance tier maximum (25 pts). The practical effect: a repository with 20 Z601 violations (10 excess → multiplier = $2^2 = 4$) takes four times the normal governance hit.

---

## Stage 4 — Gravity Cap {#gravity-cap}

If the Governance bucket is fully zeroed by its deductions:

$$
S_{\text{base}} = \min\!\left(S_{\text{base}},\; 70\right) \quad \text{if } \text{cat\_pts}_{\text{brand}} = 0
$$

---

## Stage 5 — Suppression Debt {#suppression-debt}

Every active suppression is an acknowledged assumption of responsibility. The **flat-cost model** deducts exactly **1 point per suppression**, regardless of how many suppressions are present. There is no free allowance.

`suppression_cap` (default: 30) is a **hard-fail threshold**, not an allowance boundary. In `zenzic score`, the `fail_under` gate is evaluated first and the suppression-cap gate is evaluated after it; both remain independent controls. The penalty formula is independent of the cap:

$$
\omega_{\text{debt}} = n
$$

where:

- $n$ = total active suppressions (inline `zenzic:ignore` + `per_file_ignores` entries)

The final score is:

$$
S_{\text{final}} = \max\!\left(0,\; S_{\text{base}} - n\right)
$$

### Suppression Cost Reference

| Suppression count | Cost per suppression | Notes |
| :--- | :---: | :--- |
| $n \leq \text{cap}$ | 1 pt each | Managed posture — every suppression costs |
| $n > \text{cap}$ | 1 pt each | Hard-fail: `zenzic score` exits with code 1 |

!!! info Boundary Condition — Configuration Invariant
    Because every suppression deducts 1 point, the **maximum achievable score** for a repository is:

    $$\text{Max Achievable Score} = 100 - |F_s|$$

    where $|F_s|$ is the total active suppression count. Configuring `fail_under > 100 - suppression_cap` creates a mathematical contradiction. Safe configuration rule: `fail_under` ≤ `100 - suppression_cap`.

> See [Scoring Design — Dual-Gate Architecture and Result Interpretation](../explanation/scoring-design.md) for worked examples, CLI output guide, and governance posture semantics.

---

## Complete Formula {#complete-formula}

Assembling all five stages:

$$
S_{\text{final}} =
\begin{cases}
0 & \text{if } \sum_{c \in \mathcal{S}} n_c > 0 \quad \text{(Security Override)} \\[6pt]
\max\!\left(0,\; S_{\text{gravity}} - n\right) & \text{otherwise}
\end{cases}
$$

where $n$ is the total active suppression count and:

$$
S_{\text{gravity}} =
\begin{cases}
\min\!\left(S_{\text{base}},\; 70\right) & \text{if } \text{cat\_pts}_{\text{brand}} = 0 \\
S_{\text{base}} & \text{otherwise}
\end{cases}
$$

---

## See Also {#see-also}

- [Scoring Design](../explanation/scoring-design.md) — Worked example, CLI output interpretation, and governance posture semantics.
- [Suppression Policy](./suppression-policy) — Three suppression levels, debt formula, and the `--audit` override
- [Finding Codes](./finding-codes) — Full encyclopedia of Zxxx codes with remediation steps
- [Handle Technical Debt](../how-to/handle-technical-debt) — Step-by-step remediation workflow
- [Configure Privacy Gate](../how-to/configure-privacy-gate) — Z204 FORBIDDEN_TERM architecture
