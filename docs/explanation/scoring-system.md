---
sidebar_label: "Scoring System"
sidebar_position: 4
description: "The Deterministic Quality Score (DQS) — conceptual model, penalty table, dual-gate architecture, worked examples, and CLI breakdown."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Scoring System — The Deterministic Quality Score (DQS)

Unmonitored documentation drift corrupts developer trust. A broken link degrades user experience, while an unredacted credential key requires immediate security incident response.

The Zenzic **Deterministic Quality Score (DQS)** provides a single **0–100 value** computed from the concrete finding count across every check. Zero findings evaluates to **100/100**. Given the same repository state and `.zenzic.toml` configuration, the score is **100% bit-for-bit deterministic** across machines, operating systems, and runners.

---

## DQS Category Weights

The Quality Score is a weighted composite of four distinct check categories:

| Category | Primary Command | Finding Codes | Weight |
| :--- | :--- | :--- | :---: |
| **Structural Integrity** | `zenzic check links` | `Z101`–`Z124` | **30%** |
| **Navigation Graph** | `zenzic check orphans` | `Z301`–`Z303`, `Z401`–`Z402` | **25%** |
| **Brand & Governance** | `zenzic check assets` | `Z404`–`Z406`, `Z601`–`Z603` | **25%** |
| **Content Excellence** | `zenzic check all` | `Z501`–`Z506` | **20%** |

!!! danger "Inviolable Security Override"
    If any security finding is detected — **Z201 Credential Scanner**, **Z202/Z203 Path Traversal Guard** — the Quality Score **collapses to 0/100 unconditionally**. A repository with active secret leaks receives zero quality credit.

---

## Dual-Gate Architecture & Suppression Budget

The `fail_under` score threshold and `suppression_cap` operate as orthogonal, independently enforced quality constraints:

- **Score Gate (`fail_under`)**: Fails CI (Exit 1) if computed DQS score falls below the required threshold.
- **Governance Cap (`suppression_cap`)**: Fails CI (Exit 1) if active suppressions exceed the configured debt limit (default: **30**).

Every active inline or per-file suppression deducts **1 Debt Point** from the score:

$$\text{Max Achievable Score} = 100 - |F_s|$$

---

## Worked Example & Mathematical Computation

**Scenario:** A repository contains 2 broken links (`Z101`), 3 orphan pages (`Z402`), 5 untagged code blocks (`Z505`), and 15 `Z601` brand violations, with 8 active suppressions (cap = 30).

| Stage | Deduction Calculation | Category Points Retained |
| :--- | :--- | :---: |
| **Stage 1 — Security Gate** | No `Z2xx` findings detected | Continue evaluation |
| **Stage 2 — Structural** | 2 × 8.0 = 16.0 pts | 14.0 / 30.0 |
| **Stage 2 — Navigation** | 3 × 4.0 = 12.0 pts | 13.0 / 25.0 |
| **Stage 2 — Content** | 5 × 1.0 = 5.0 pts | 15.0 / 20.0 |
| **Stage 2 — Governance** | 15 × 2.0 = 30.0 pts → capped to 25.0 | 0.0 / 25.0 |

$$\text{Subtotal} = 14.0 + 13.0 + 15.0 + 0.0 = 42.0$$

Applying active suppression debt ($n = 8$):

$$\text{Final DQS Score} = 42.0 - 8 = \mathbf{34 / 100}$$

---

## CLI Quality Breakdown Ledger

Executing `zenzic score` prints a transparent breakdown ledger detailing raw deductions, category caps, and debt subtotals:

```text title="Terminal"
✨ Quality Score: 65/100

╭─ Quality Breakdown ──────────────────────────────────────╮
│   Category     Issues  Weight  Raw Pts  Applied Pts      │
├──────────────────────────────────────────────────────────┤
│ ✓ structural      0      30%      0           0          │
│ ✓ navigation      0      25%      0           0          │
│ ✗ content         2      20%     -4          -4          │
│ ✗ brand          15      25%    -30         -25 (CAPPED) │
├──────────────────────────────────────────────────────────┤
│   Σ Subtotal                                71           │
╰──────────────────────────────────────────────────────────╯
  ! Technical Debt (6 suppressions)          -6 pts
  = Final Quality Score                      65 / 100
```

## See Also

- [Scoring Algorithm](../reference/scoring-algorithm.md)
