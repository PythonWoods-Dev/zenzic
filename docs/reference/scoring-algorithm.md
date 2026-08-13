---
sidebar_position: 6
sidebar_label: "Scoring Algorithm"
description: "The Zenzic scoring engine: 5-tier weight matrix, complete per-code penalty table, Gravity Cap, Governance Escalation, Suppression Debt formula, and Security Override."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Scoring Algorithm

The Zenzic Documentation Quality Score (DQS) is a **deterministic, 0–100 integer** computed from the findings of every active check. Given the same repository state, the algorithm always produces the exact same score.

> For conceptual model, CLI output interpretation, and worked examples, see [Scoring System](../explanation/scoring-system.md).

---

## Architecture Overview {#overview}

The scoring pipeline operates across five sequential stages:

```text
1. Security Gate    → Z2xx finding? score = 0, early return.
2. Penalty Table    → per-code deductions, per-tier caps.
3. Governance Esc.  → exponential amplification if Z6xx > 10.
4. Gravity Cap      → brand score = 0 ⟹ total ≤ 70.
5. Suppression Debt → subtract ω_debt from capped total.
```

---

## Stage 1 — Security Override {#security-override}

Before any category calculation, the engine evaluates **Z2xx findings**:

$$
S_{\text{final}} = 0 \quad \text{if } \sum_{c \in \mathcal{S}} n_c > 0
$$

where $\mathcal{S} = \{Z201, Z202, Z203, Z204, Z205\}$.

This is an **unconditional early return** — no flags, no configuration options, and no suppressions can bypass it. The five codes in $\mathcal{S}$ represent binary failure conditions:

| Code | Title | Condition |
| :--- | :--- | :--- |
| Z201 | CREDENTIAL_SECRET | Credential pattern or secret detected in document |
| Z202 | PATH_TRAVERSAL | Link target escapes `docs/` to a non-system path |
| Z203 | PATH_TRAVERSAL_FATAL | Link target resolves to an OS system path |
| Z204 | FORBIDDEN_TERM | Privacy Gate — confidential term exposure |
| Z205 | FORBIDDEN_SCHEME | XSS Gate — `javascript:` or `data:` URI scheme |

When the Security Override fires, `ScoreReport` returns `security_override=True` and `security_findings=N` (total Z2xx count).

!!! danger Security Codes Are Non-Suppressible
    No inline `<!-- zenzic:ignore -->`, no `per_file_ignores`, and no `excluded_dirs` can suppress a Z2xx finding.

---

## Stage 2 — Weight Matrix & Penalty Table {#penalty-table}

If no Z2xx finding is detected, the engine calculates per-category scores using the **5-Tier Weight Matrix**:

### Zenzic Weight Matrix (5-Tier)

| Tier | Category | Finding Codes | Weight | Bucket Cap |
| :--- | :--- | :--- | ---: | ---: |
| Security Gate | — | Z2xx | — | score = 0 |
| Structural | `structural` | Z101–Z105, Z107–Z109, Z113, Z121, Z124, Z410, Z411 | 30% | 30 pts |
| Navigation | `navigation` | Z301–Z303, Z402 | 25% | 25 pts |
| Content | `content` | Z120, Z122, Z403, Z501–Z503, Z505, Z506, Z510–Z512 | 20% | 20 pts |
| Governance & Brand | `brand` | Z620, Z404–Z406, Z601, Z603, Z610, Z611 | 25% | 25 pts |

### Category Penalty Formula

For each category bucket $i$:

$$
\text{cat\_pts}_i = \max\!\left(0,\; w_i \times 100 - \sum_{c \in \text{category}_i} \text{penalty}_c \times n_c\right)
$$

### Complete Penalty Reference Table

Below is the authoritative, full reference table for all 36 active penalty-bearing Zenzic codes:

| Code | Title | Penalty / Occurrence | Category | Opt-In Policy |
| :--- | :--- | ---: | :--- | :---: |
| **Z101** | LINK_BROKEN | 8.0 pts | Structural | Standard |
| **Z102** | ANCHOR_MISSING | 5.0 pts | Structural | Standard |
| **Z103** | ORPHAN_LINK | 2.0 pts | Structural | Standard |
| **Z104** | FILE_NOT_FOUND | 8.0 pts | Structural | Standard |
| **Z105** | ABSOLUTE_PATH | 2.0 pts | Structural | Standard |
| **Z107** | CIRCULAR_ANCHOR | 1.0 pts | Structural | Standard |
| **Z108** | EMPTY_LINK_TEXT | 1.0 pts | Structural | Standard |
| **Z109** | EXTERNAL_LINK_BROKEN | 3.0 pts | Structural | Standard |
| **Z113** | AUTHOR_KEY_COLLISION | 2.0 pts | Structural | Standard |
| **Z620** | STALE_GLOBAL_SUPPRESSION | 1.0 pts | Governance & Brand | Standard |
| **Z120** | UNKNOWN_HTML_ATTRIBUTE | 1.0 pts | Content | Standard |
| **Z121** | MISSING_OR_EMPTY_HREF | 1.0 pts | Structural | Standard |
| **Z122** | JUMP_LINK_DETECTED | 1.0 pts | Content | Standard |
| **Z124** | OPAQUE_HTML_CONTEXT | 1.0 pts | Structural | Standard |
| **Z301** | DANGLING_REF | 4.0 pts | Navigation | Standard |
| **Z302** | DEAD_DEF | 1.0 pts | Navigation | Standard |
| **Z303** | DUPLICATE_DEF | 3.0 pts | Navigation | Standard |
| **Z402** | ORPHAN_PAGE | 4.0 pts | Navigation | Standard |
| **Z403** | MISSING_ALT | 1.0 pts | Content | Standard |
| **Z404** | CONFIG_ASSET_MISSING | 3.0 pts | Governance & Brand | Standard |
| **Z405** | UNUSED_ASSET | 3.0 pts | Governance & Brand | Standard |
| **Z406** | NAV_CONTRACT | 2.0 pts | Governance & Brand | Standard |
| **Z410** | UNREACHABLE_GRAPH_NODE | 5.0 pts | Structural | Standard |
| **Z411** | DEAD_END_NODE | 5.0 pts | Structural | Standard |
| **Z501** | PLACEHOLDER | 2.0 pts | Content | Standard |
| **Z502** | SHORT_CONTENT | 1.0 pts | Content | Standard |
| **Z503** | SNIPPET_ERROR | 10.0 pts | Content | Standard |
| **Z505** | UNTAGGED_CODE_BLOCK | 1.0 pts | Content | Standard |
| **Z506** | MALFORMED_FRONTMATTER | 5.0 pts | Content | Standard |
| **Z510** | HEADING_HIERARCHY | 1.0 pts | Content | Standard |
| **Z511** | EXCESSIVE_SENTENCE_LENGTH | 1.0 pts | Content | Standard |
| **Z512** | EMPTY_SECTION | 1.0 pts | Content | Standard |
| **Z601** | BRAND_OBSOLESCENCE | 2.0 pts | Governance & Brand | Standard |
| **Z603** | DEAD_SUPPRESSION | 1.0 pts | Governance & Brand | Standard |
| **Z610** | REQUIRED_FRONTMATTER_MISSING | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z611** | FORBIDDEN_DOMAIN_REFERENCE | 3.0 pts | Governance & Brand | **Opt-In** |

!!! note Informational & Configuration Codes Excluded
    - **Z106** (CIRCULAR_LINK), **Z114** (LARGE_PAGINATION_SET), **Z123** (NON_HTTP_SCHEME), **Z401** (MISSING_DIRECTORY_INDEX), and **Z504** (QUALITY_REGRESSION) carry **0.0 pts** penalty and do not impact the DQS.
    - **Z110** (CONFIG_SYNTAX_ERROR) and **Z111** (CONFIG_SCHEMA_ERROR) trigger fatal non-zero exits before scoring begins.

---

## Stage 3 — Governance Escalation {#governance-escalation}

When Governance & Brand findings (codes $\mathcal{G} = \{Z601, Z603, Z610, Z611\}$) exceed **10 total occurrences**, an exponential penalty amplifier is applied to the Governance category deduction:

$$
\text{deduction}_{\text{brand}}' = \min\!\left(\text{cap}_{\text{brand}},\; \text{deduction}_{\text{brand}} \times 2^{(n_{\text{excess}} / 5)}\right)
$$

where $n_{\text{excess}} = \sum_{c \in \mathcal{G}} n_c - 10$.

---

## Stage 4 — Gravity Cap {#gravity-cap}

If the Governance bucket is fully zeroed ($\text{cat\_pts}_{\text{brand}} = 0$):

$$
S_{\text{base}} = \min\!\left(S_{\text{base}},\; 70\right)
$$

A document repository with unaddressed governance failures cannot score above 70/100.

---

## Stage 5 — Suppression Debt {#suppression-debt}

Under the **flat-cost model**, every active inline or per-file suppression deducts **exactly 1 point**:

$$
\omega_{\text{debt}} = n
$$

where $n$ is the total count of active suppressions (`<!-- zenzic:ignore -->` and `per_file_ignores` entries).

The final score is:

$$
S_{\text{final}} = \max\!\left(0,\; S_{\text{base}} - n\right)
$$

---

## See Also {#see-also}

- [Scoring System](../explanation/scoring-system.md) — DQS conceptual model, CLI breakdown, and worked example.
- [Suppression Policy](./suppression-policy.md) — Suppression posture levels and debt limits.
- [Finding Codes](./finding-codes.md) — Full reference encyclopedia of all Z-codes.
- [Configuration Reference](./configuration-reference.md) — `.zenzic.toml` options and policy-as-code controls.
