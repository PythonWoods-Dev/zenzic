---
description: "Step-by-step guide to auditing, understanding, and reducing suppression debt in your Zenzic quality score."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Handle Technical Debt

> *"Why did my score drop after I ignored an error?"*

When you suppress a finding in Zenzic — via an inline comment or a per-file config entry — you are not erasing the problem. You are **assuming responsibility** for it. That assumption has a cost: **Technical Debt Points** deducted from your quality score.

This guide explains how to read the debt, understand the cost formula, and reduce it over time.

---

## Reading the Score Output {#reading}

After running `zenzic score`, you may see an extra line below the score table:

```text
Score: 93/100
! Technical Debt (Suppressions): -7 pts
Suppression Audit: 7/30 (inline: 5, per-file: 2)
```

This means:

- **7 active suppressions** are hiding findings from the audit stream.
- **5** are inline `zenzic:ignore` comments in Markdown files.
- **2** are per-file entries in `governance.per_file_ignores`.
- The debt formula reduced the score by **7 pts**.

---

## The Cost Formula {#formula}

$$
\text{debt} = n
$$

Where:

- $n$ = total active suppressions (inline + per-file)
- `cap` = `governance.suppression_cap` in `.zenzic.toml` (default: **30**)

The debt cost is **flat**: each suppression always costs **1 pt**.

| Suppressions | Debt | Score (from 100) |
| :---: | :---: | :---: |
| 0 | 0 pt | 100 |
| 10 | 10 pt | 90 |
| 30 | 30 pt | 70 |
| 31 | 31 pt | 69 |
| 35 | 35 pt | 65 |

When suppressions exceed the configured cap, the run still hard-fails via the governance gate (`suppression_cap`) even though debt remains linear. The score gate (`fail_under`) and the cap gate are orthogonal and evaluated independently.

---

## Step 1: See What You Are Hiding {#step-1}

Run a sovereign audit to see all findings that are currently suppressed:

```bash
zenzic check all --audit
```

The `--audit` flag bypasses all inline `zenzic:ignore` comments and all `governance.per_file_ignores` entries. It shows the true state of your documentation.

Compare the `--audit` output with a normal `zenzic check all` run to see exactly which findings are hidden.

---

## Step 2: Understand the Rule's Cost {#step-2}

For each suppressed finding, use `zenzic explain` to see its scoring impact:

```bash
zenzic explain Z601
```

The output shows:

- The rule's scoring tier (structural / navigation / content / brand)
- The penalty per occurrence (pts/occurrence)
- The per-file suppression status from your current `.zenzic.toml`

---

## Step 3: Fix vs Acknowledge {#step-3}

For each suppressed finding, make an explicit decision:

### Fix it (reduce debt)

Remove the suppression and fix the underlying issue:

1. Delete the `<!-- zenzic:ignore ZXXX -->` comment from the Markdown line.
2. Or remove the entry from `governance.per_file_ignores`.
3. Then fix the actual violation (update the link, remove the obsolete term, etc.).
4. Run `zenzic check all` to verify.

### Acknowledge it (document the intent)

If the suppression is genuinely intentional (historical reference, migration context, etc.):

1. Keep the suppression but add a prose comment explaining why.
2. Prefer per-file suppression over inline comments for structural exceptions — it centralises the policy in `.zenzic.toml`.
3. Adjust `governance.suppression_cap` if your project has a legitimately higher baseline.

---

## Step 4: Adjust the Governance Cap {#step-4}

If your project has a known-good suppression baseline that is higher than 30, raise the cap in `.zenzic.toml`:

```toml
[governance]
suppression_cap = 45           # adjusted for a large i18n project
suppression_cap_fail_hard = true
```

The same keys are available under `[tool.zenzic.governance]` in `pyproject.toml`:

```toml title="pyproject.toml"
[tool.zenzic.governance]
suppression_cap = 45
suppression_cap_fail_hard = true
```

Setting the cap to the current suppression count gives you a governance floor: new suppressions will immediately escalate the cost and eventually trigger `suppression_cap_fail_hard`.

---

## Why Security Violations Cannot Be Suppressed {#security}

Findings in the Z2xx Security Gate category cannot be suppressed by any mechanism. See the
[Suppression Policy — Inviolable Security Surface](../reference/suppression-policy.md) for the
full code list and exit-code contract; note the codes' exit codes differ (`Z201`/`Z204` exit 2,
`Z203` exit 3, `Z202` exits 1 — not escalated by design).

A `<!-- zenzic:ignore: Z2XX -->` comment is **silently ignored**. The finding is still emitted.
The score collapses to 0.

This is by design. Security findings are facts, not style opinions. You cannot assume responsibility for a credential leak and call it a validated exception.

---

## Progressive Adoption via CLI Filtering {#progressive-adoption}

When introducing Zenzic to a legacy repository, you may encounter hundreds of structural or stylistic warnings. Attempting to fix everything at once often stalls adoption.

The new `--only` flag (introduced in v0.10.0) allows teams to adopt Zenzic progressively without blocking CI. You can enforce only the most critical rules (such as credential leaks and broken links) and systematically add more codes as the technical debt is paid down.

```bash
# Start by enforcing only Security Gates and Broken Links
zenzic check all --only Z201,Z202,Z204,Z101,Z104
```

As your team resolves the structural debt, you can progressively expand the `--only` list until the repository is ready for a full, unfiltered `zenzic check all`. This allows you to secure the most critical aspects of your documentation immediately.

---

## Reference {#reference}

- [Suppression Policy](../reference/suppression-policy.md) — Full reference for all three suppression levels.
- [Scoring Algorithm](../reference/scoring-algorithm.md) — How debt interacts with the Gravity Cap and category weights.
- [`zenzic explain`](../reference/cli.md) — Inspect any rule's cost and suppression status.
- [Example: Suppression Mechanics](https://github.com/PythonWoods/zenzic/tree/main/examples/scoring) — Runnable demo with 7 active suppressions.
