---
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
| Structural | `structural` | Z101–Z105, Z107–Z109, Z112, Z121, Z124, Z410, Z411 | 30% | 30 pts |
| Navigation | `navigation` | Z301–Z303, Z401, Z402, Z412 | 25% | 25 pts |
| Content | `content` | Z120, Z122, Z403, Z501–Z503, Z505, Z506, Z510–Z523 | 20% | 20 pts |
| Governance & Brand | `brand` | Z620, Z404–Z406, Z601, Z603, Z610–Z619 | 25% | 25 pts |

### Category Penalty Formula

For each category bucket $i$:

$$
\text{cat\_pts}_i = \max\!\left(0,\; w_i \times 100 - \sum_{c \in \text{category}_i} \text{penalty}_c \times n_c\right)
$$

---

## 5. Finding Penalty Matrix

Every finding code is assigned a base penalty points value. Penalties are deducted from the respective category score during DQS evaluation.

| Code | Name | Penalty | Category | Opt-In / Active |
| :--- | :--- | :---: | :--- | :--- |
| **Z001** | CORE_CONFIG_STRUCTURE | 0.0 pts | Configuration Guard | Fatal Guard |
| **Z101** | LINK_BROKEN | 8.0 pts | Structural Integrity | Default |
| **Z102** | ANCHOR_MISSING | 5.0 pts | Structural Integrity | Default |
| **Z103** | ORPHAN_LINK | 2.0 pts | Structural Integrity | Default |
| **Z104** | FILE_NOT_FOUND | 8.0 pts | Structural Integrity | Default |
| **Z105** | ABSOLUTE_PATH | 2.0 pts | Structural Integrity | Default |
| **Z106** | CIRCULAR_LINK | 0.0 pts | *(uncategorized)* | Informational — no DQS penalty |
| **Z107** | CIRCULAR_ANCHOR | 1.0 pt | Structural Integrity | Default |
| **Z108** | EMPTY_LINK_TEXT | 1.0 pt | Structural Integrity | Default |
| **Z109** | EXTERNAL_LINK_BROKEN | 3.0 pts | Structural Integrity | Default |
| **Z110** | CONFIG_SYNTAX_ERROR | 0.0 pts | Configuration Guard | Fatal Guard |
| **Z111** | CONFIG_SCHEMA_ERROR | 0.0 pts | Configuration Guard | Fatal Guard |
| **Z112** | STALE_ALLOWLIST_ENTRY | 1.0 pt | Structural Integrity | Default |
| **Z120** | UNKNOWN_HTML_ATTRIBUTE | 1.0 pt | Content Excellence | Default |
| **Z121** | MISSING_OR_EMPTY_HREF | 1.0 pt | Structural Integrity | Default |
| **Z122** | JUMP_LINK_DETECTED | 1.0 pt | Content Excellence | Default |
| **Z123** | NON_HTTP_SCHEME | 0.0 pts | *(uncategorized)* | Informational — no DQS penalty |
| **Z124** | OPAQUE_HTML_CONTEXT | 1.0 pt | Structural Integrity | Default |
| **Z201** | CREDENTIAL_SECRET | Security | Inviolable Override | Security Gate |
| **Z202** | PATH_TRAVERSAL | Security | Inviolable Override | Security Gate |
| **Z203** | PATH_TRAVERSAL_FATAL | Security | Inviolable Override | Security Gate |
| **Z204** | FORBIDDEN_TERM | Security | Inviolable Override | Security Gate |
| **Z205** | FORBIDDEN_SCHEME | Security | Inviolable Override | Security Gate |
| **Z301** | DANGLING_REF | 4.0 pts | Navigation Graph | Default |
| **Z302** | DEAD_DEF | 1.0 pt | Navigation Graph | Default |
| **Z303** | DUPLICATE_DEF | 3.0 pts | Navigation Graph | Default |
| **Z401** | MISSING_DIRECTORY_INDEX | 0.0 pts | Navigation Graph | Informational — no DQS penalty |
| **Z402** | ORPHAN_PAGE | 4.0 pts | Navigation Graph | Default |
| **Z403** | MISSING_ALT | 1.0 pt | Content Excellence | Default |
| **Z404** | CONFIG_ASSET_MISSING | 3.0 pts | Governance & Brand | Default |
| **Z405** | UNUSED_ASSET | 3.0 pts | Governance & Brand | Default |
| **Z406** | NAV_CONTRACT | 2.0 pts | Governance & Brand | Default |
| **Z410** | UNREACHABLE_GRAPH_NODE | 5.0 pts | Structural Integrity | Default |
| **Z411** | DEAD_END_NODE | 5.0 pts | Structural Integrity | Default |
| **Z412** | TRACEABILITY_BROKEN | 4.0 pts | Navigation Graph | **Opt-In** |
| **Z501** | PLACEHOLDER | 2.0 pts | Content Excellence | Default |
| **Z502** | SHORT_CONTENT | 1.0 pt | Content Excellence | Default |
| **Z503** | SNIPPET_ERROR | 10.0 pts | Content Excellence | Default |
| **Z504** | QUALITY_REGRESSION | 0.0 pts | Baseline Audit | **Reserved — not emitted at runtime** |
| **Z505** | UNTAGGED_CODE_BLOCK | 1.0 pt | Content Excellence | Default |
| **Z506** | MALFORMED_FRONTMATTER | 5.0 pts | Content Excellence | Default |
| **Z510** | HEADING_HIERARCHY | 1.0 pt | Content Excellence | Default |
| **Z511** | EXCESSIVE_SENTENCE_LENGTH | 1.0 pt | Content Excellence | Default |
| **Z512** | EMPTY_SECTION | 1.0 pt | Content Excellence | Default |
| **Z513** | DUPLICATE_HEADING | 2.0 pts | Content Excellence | Default |
| **Z514** | GENERIC_IMAGE_ALT_TEXT | 2.0 pts | Content Excellence | Default |
| **Z515** | BARE_URL_USED | 1.0 pt | Content Excellence | Default |
| **Z516** | MULTIPLE_H1_HEADINGS | 5.0 pts | Content Excellence | Default |
| **Z517** | HEADING_PUNCTUATION | 1.0 pt | Content Excellence | Default |
| **Z518** | PASSIVE_VOICE_DETECTED | 1.0 pt | Content Excellence | **Opt-In** |
| **Z519** | WEASEL_WORDS | 1.0 pt | Content Excellence | **Opt-In** |
| **Z520** | MALFORMED_LIST_DETECTED | 2.0 pts | Content Excellence | Default |
| **Z521** | REQUIRED_TABLE_COLUMN | 2.0 pts | Content Excellence | **Opt-In** |
| **Z522** | TABLE_CELL_ENUM | 2.0 pts | Content Excellence | **Opt-In** |
| **Z523** | HEADING_ORDER_VIOLATION | 2.0 pts | Content Excellence | **Opt-In** |
| **Z601** | BRAND_OBSOLESCENCE | 2.0 pts | Governance & Brand | Default |
| **Z603** | DEAD_SUPPRESSION | 1.0 pt | Governance & Brand | Technical Debt |
| **Z610** | REQUIRED_FRONTMATTER_MISSING | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z611** | FORBIDDEN_DOMAIN_REFERENCE | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z612** | FORBIDDEN_FRONTMATTER_KEY | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z613** | FRONTMATTER_SCHEMA_MISMATCH | 5.0 pts | Governance & Brand | **Opt-In** |
| **Z614** | UNAPPROVED_DOMAIN_REFERENCE | 5.0 pts | Governance & Brand | **Opt-In** |
| **Z615** | FORBIDDEN_URL_SCHEME | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z616** | CROSS_NAMESPACE_LINK_FORBIDDEN | 8.0 pts | Governance & Brand | **Opt-In** |
| **Z617** | FORBIDDEN_CONTENT_PATTERN | 2.0 pts | Governance & Brand | **Opt-In** |
| **Z618** | REQUIRED_HEADING_PATTERN | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z619** | MAX_DOCUMENT_COMPLEXITY | 3.0 pts | Governance & Brand | **Opt-In** |
| **Z620** | STALE_GLOBAL_SUPPRESSION | 1.0 pt | Governance & Brand | Default |
| **Z901** | RULE_ENGINE_ERROR | 0.0 pts | Configuration Guard | HALT Gate |
| **Z902** | RULE_TIMEOUT | 0.0 pts | *(uncategorized)* | Diagnostic — no DQS penalty |
| **Z906** | NO_FILES_FOUND | 0.0 pts | *(uncategorized)* | Informational — no DQS penalty |

---

## Stage 3 — Governance Escalation {#governance-escalation}

When Governance & Brand findings (codes $\mathcal{G} = \{Z601, Z603, Z610, Z611, Z612, Z613, Z614, Z615, Z616, Z617, Z618, Z619, Z620\}$) exceed **10 total occurrences**, an exponential penalty amplifier is applied to the Governance category deduction:

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
