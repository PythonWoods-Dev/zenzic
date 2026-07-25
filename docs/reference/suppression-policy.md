---
sidebar_position: 5
sidebar_label: "Suppression Policy"
description: "The Zenzic Suppression Manifesto — four suppression levels, Technical Debt cost formula, inviolable security codes, and the --audit override."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Suppression Policy

> *"A suppression is not a cancellation. It is an assumption of responsibility."*

Zenzic's suppression system lets teams declare **validated exceptions** — intentional deviations that are not defects. It is a precision governance instrument, not an escape hatch. Every suppression is recorded, audited, and **costs Quality Score points**.

---

## Reporting Levels — Audit Footer Semantics {#reporting-levels}

When you run `zenzic check all` or `zenzic check all --audit`, Zenzic emits a footer reporting the current state of suppressions. This footer uses a semantic taxonomy with four distinct reporting levels:

| State | Suppressions | Label | Severity | Meaning |
| :--- | :---: | :--- | :--- | :--- |
| **Clean State** | 0 | *(no label)* | ✅ Green | Full integrity — no suppressions in use. Documentation is at baseline. |
| **Managed Debt** | 0 < n ≤ CAP and CAP ≤ 30 | `[MANAGED DEBT]` (cyan) | ⏳ OK | Suppressions are in use within the sovereign cap profile. |
| **Extended Debt** | 0 < n ≤ CAP and CAP > 30 | `[EXTENDED DEBT]` (yellow) | ⚠️ Warning | Suppressions are in use under an expanded cap profile and require governance review. |
| **Cap Exceeded** | n > CAP | `[CAP_EXCEEDED]` (red) | 🚨 Error | Suppressions exceed the configured cap. CI gate fails with exit code 1 when `suppression_cap_fail_hard=true`. Remediation is mandatory. |

### Footer Examples

```shell
# Clean state — zero suppressions
🔒 Suppression Audit: 0/34 (inline: 0, per-file: 0)

# Managed debt — within budget (25 out of 34 suppressions allowed)
🔒 Suppression Audit: 25/34 (inline: 25, per-file: 0) [MANAGED DEBT]

# Extended debt — at the cap (34 out of 34 suppressions; limit reached)
🔒 Suppression Audit: 34/34 (inline: 34, per-file: 0) [EXTENDED DEBT]

# Cap exceeded — over the cap (39 out of 34; gate fails)
🔒 Suppression Audit: 39/34 (inline: 35, per-file: 4) [CAP_EXCEEDED] — EXIT CODE 1
```

### Setting the Suppression Budget

The CAP is configured in `.zenzic.toml`:

```toml
[governance]
suppression_cap = 34  # Maximum allowed suppressions before gate failure
```

If `suppression_cap` is omitted, Zenzic uses a built-in default of **30**.

---

## The Four Suppression Levels {#levels}

Zenzic offers four levels of suppression, from the most precise to the most broad.
They are designed to be combined: a well-governed project uses each level for its intended purpose.

| Level | Mechanism | Scope | Audit Trail | Score Cost |
| :--- | :--- | :--- | :---: | :---: |
| **1. Inline** | `<!-- zenzic:ignore: ZXXX -->` comment | Single line | ✅ Yes | 1 pt/suppress |
| **2. Per-file** | `governance.per_file_ignores` in TOML | File glob | ✅ Yes | 1 pt/entry |
| **3. Exclusion Zone** | `excluded_dirs` / `excluded_file_patterns` | Directory or pattern | ❌ No | 0 pt |
| **4. Directory Policy** | `governance.directory_policies` in TOML | File glob | ✅ Yes (audit mode) | **0 pt** |

!!! warning "Exclusion Zones are silent"
    Files in exclusion zones are completely invisible to Zenzic. No findings are emitted, no audit trail is kept, and no score impact is recorded. Use exclusion zones only for genuine non-documentation assets (build outputs, third-party files). For intentional exceptions in documentation, use Level 1 or Level 2 — they keep the audit trail alive.

---

## Level 1 — Inline Suppression {#inline}

The most precise suppression: one comment, one line, one finding.

**Markdown (`.md`) files:**

```markdown
Legacy product name retained for historical accuracy. <!-- zenzic:ignore: Z601 -->
```

**Markdown (`.md`) files:**

```html
Legacy product name retained for historical accuracy. <!-- zenzic:ignore: Z601 -->
```

Both comment forms are invisible in rendered output. Use the comment form that matches the surrounding file style to keep source examples consistent.

To suppress **multiple codes on the same line**, add one comment per code:

```html
Some line. <!-- zenzic:ignore: Z107 --> <!-- zenzic:ignore: Z601 -->
```

### Recommended: Trailing Position

The comment should always appear at the **end of the line**, following the industry convention established by `# noqa` (Python), `// eslint-disable-line` (JavaScript), and `// lint:ignore` (Go).

```html
- Historical reference — legacy product naming retained here. <!-- zenzic:ignore: Z601 -->
```

---

## Level 2 — Per-File Suppression {#per-file}

Silence a rule for an entire file glob without adding inline comments to the source.
Use this for pages where intentional exceptions are structurally necessary (legacy guides, migration docs).

Add a `[governance.per_file_ignores]` table to your `.zenzic.toml`:

```toml
[governance.per_file_ignores]
"docs/migration/**"  = ["Z601"]  # intentional brand refs in migration context
"docs/legacy/*.md"   = ["Z101"]  # known broken links to decommissioned systems
```

The map key is a glob pattern relative to the repository root (matching the paths displayed in the CLI output). Each entry in the list is one suppression, counted toward the Technical Debt total.

!!! tip "Use `zenzic explain` to check status"
    Run `zenzic explain Z601` to see the current per-file suppression status for a rule — the Config Genealogy table will show every glob pattern where the rule is silenced.

---

## Level 3 — Exclusion Zones {#exclusion}

Full bypass: paths in exclusion zones are never scanned.

```toml
excluded_dirs          = ["legacy/", "third-party/"]
excluded_file_patterns = ["CHANGELOG*.md"]
```

Exclusion zones carry **no score cost** because they are not suppressions — they are scope boundaries. Use them for:

- Build outputs and generated assets (`build/`, `dist/`)
- Third-party documentation included as-is
- Historical changelogs that contain example secrets and deprecated syntax

Do **not** use exclusion zones to hide real documentation debt.

---

## Level 4 — Directory Policy {#directory-policy}

Zero-debt strategic exemptions for entire directory trees or specific file globs.
Designed for **structural exceptions** where suppressions are organizationally mandated, not technical debt.
Unlike exclusion zones, directory policies keep an audit trail in `--audit` mode.

Add a `[governance.directory_policies]` table to your `.zenzic.toml`:

```toml
[governance.directory_policies]
"docs/blog/**"                   = ["Z601"]  # historical blog posts — brand refs expected
"docs/explanation/registry.md" = ["Z601"]  # SSOT codename registry
```

The map key is a glob pattern relative to the repository root (matching the paths displayed in the CLI output). Matched findings are **silently dropped before display** with **zero suppression debt cost** — they are never counted in the Suppression Audit footer.

!!! info "Hierarchy: Directory Policy > Per-file ignore > Inline"
    When choosing a suppression level:
    - **Level 4** for strategic, organizationally-ratified exemptions affecting multiple files (e.g. entire `blog/` archive). Zero cost.
    - **Level 2** for file-by-file exceptions with explicit debt (1 pt/entry). Appears in Suppression Audit.
    - **Level 1** for ad-hoc, line-level exceptions in prose. 1 pt each. Most visible in source.

### Audit Mode and `[POLICY_EXEMPTION]` Label

When running `zenzic check all --audit`, directory policy exemptions are **not dropped** — they surface with a `[POLICY_EXEMPTION]` label prepended to the finding message. This lets governance reviewers inspect what is strategically exempt without breaking the zero-debt invariant:

```shell
$ zenzic check all --audit
explanation/brand-history.md:21 [Z601] [POLICY_EXEMPTION] Brand obsolescence: 'LegacyNameA'
explanation/brand-history.md:22 [Z601] [POLICY_EXEMPTION] Brand obsolescence: 'LegacyNameB'
blog/2026-05-24-log-v080.md:1 [Z601] [POLICY_EXEMPTION] Brand obsolescence: 'LegacyReleaseCodename'
```

!!! danger "Inviolable Security Surface (Z201–Z205)"
    Security findings (**Z201 Credential Scanner**, **Z202/Z203 Path Traversal Guard**) unconditionally bypass all directory policies, per-file ignores, and inline comments. They are non-suppressible security facts that trigger exit codes 2 and 3 regardless of any TOML configuration.


---

## Technical Debt Cost Formula {#debt}

Active suppressions (Levels 1 and 2) reduce the quality score:

$$
 \text{debt} = n
$$

Where $n$ is the total number of active suppressions and `cap` is `governance.suppression_cap` (default: **30**).

| Active suppressions | Cap = 30 | Debt | Final score (from 100) |
| :---: | :---: | :---: | :---: |
| 0 | 30 | 0 pt | **100** |
| 1 | 30 | 1 pt | **99** |
| 10 | 30 | 10 pt | **90** |
| 30 | 30 | 30 pt | **70** |
| 31 | 30 | 31 pt | **69** |
| 35 | 30 | 35 pt | **65** |

The debt is applied **after** the Gravity Cap. If your brand score is 0, the total is capped at 70, and then debt is subtracted from that.

`suppression_cap` is a governance hard-fail threshold, not a debt multiplier. Exceeding the cap triggers exit code 1 independently from the score gate (`fail_under`).

!!! info "Why does suppression cost points?"
    Zenzic cannot assess the quality of what it cannot see. Every suppression is a blind spot. The debt formula makes this cost explicit and visible in the score, instead of hiding it behind a perfect number. *Zenzic does not grade on a curve.*

---

## Suppressible vs Inviolable Codes {#codes}

Zenzic divides finding codes into two classes: **Suppressible** (author intent is sovereign) and **Inviolable** (security facts cannot be declared false positives).

| Code | Name | Suppressible? |
| :--- | :--- | :---: |
| Z101 | LINK_BROKEN | ✅ Yes |
| Z102 | ANCHOR_MISSING | ✅ Yes |
| Z103 | ORPHAN_LINK | ✅ Yes |
| Z104 | FILE_NOT_FOUND | ✅ Yes |
| Z105 | ABSOLUTE_PATH | ✅ Yes |
| Z106 | CIRCULAR_LINK | ✅ Yes |
| Z107 | CIRCULAR_ANCHOR | ✅ Yes |
| **Z201** | **CREDENTIAL_SECRET** | 🔒 **Never** |
| **Z202** | **PATH_TRAVERSAL** | 🔒 **Never** |
| **Z203** | **PATH_TRAVERSAL_FATAL** | 🔒 **Never** |
| **Z204** | **FORBIDDEN_TERM** | 🔒 **Never** |
| Z301 | DANGLING_REF | ✅ Yes |
| Z302 | DEAD_DEF | ✅ Yes |
| Z303 | DUPLICATE_DEF | ✅ Yes |
| Z401 | MISSING_DIRECTORY_INDEX | ✅ Yes |
| Z402 | ORPHAN_PAGE | ✅ Yes |
| Z403 | MISSING_ALT | ✅ Yes |
| Z404 | CONFIG_ASSET_MISSING | ✅ Yes |
| Z501 | PLACEHOLDER | ✅ Yes |
| Z502 | SHORT_CONTENT | ✅ Yes |
| Z503 | SNIPPET_ERROR | ✅ Yes |
| Z505 | UNTAGGED_CODE_BLOCK | ✅ Yes |
| Z901 | RULE_ENGINE_ERROR | ✅ Yes |
| Z902 | RULE_TIMEOUT | ✅ Yes |
| Z405 | UNUSED_ASSET | ✅ Yes |
| Z406 | NAV_CONTRACT | ✅ Yes |
| Z601 | BRAND_OBSOLESCENCE | ✅ Yes |

!!! danger "The Inviolability Law"
    `zenzic:ignore: Z201`, `Z202`, `Z203`, and `Z204` are **silently rejected**. The security gate operates independently of the suppression engine. Even if a `zenzic:ignore` comment is present, Zenzic still emits the finding and exits with code 2 or 3.

    **You cannot ignore a breach.**

---

## Bypassing All Suppressions: `--audit` {#audit}

The `--audit` flag forces a full sovereign audit: all active suppressions — both inline and per-file — are ignored during the check run. Every finding that would be hidden by a `zenzic:ignore` comment or a `per_file_ignores` entry is surfaced.

```bash
zenzic check all --audit
```

Use `--audit` to:

- See the true state of your documentation before a release
- Understand the scope of suppressed debt before raising or lowering the cap
- Verify that suppressed findings are still intentional exceptions (not regressions)

Exclusion zones (`excluded_dirs`, `excluded_file_patterns`) are **not** bypassed by `--audit` — they define the scan perimeter, not the suppression policy.

---

## Interaction with `--strict` Mode {#strict}

`--strict` and `zenzic:ignore` operate at **different layers** of the analysis pipeline:

1. **Detection:** Zenzic finds a violation (e.g. Z402, severity `warning`).
2. **Suppression filter:** If `zenzic:ignore: Z402` is present, the finding is removed.
3. **Severity evaluation:** `--strict` promotes surviving warnings to errors. It only acts on findings that passed step 2.

| Finding state | `--strict`? | Exit code | Reason |
| :--- | :---: | :---: | :--- |
| Warning present | No | `0` | Tolerated by default |
| Warning present | **Yes** | `1` | Promoted to error |
| Warning + `ignore` | No | `0` | Validated exception |
| Warning + `ignore` | **Yes** | `0` | **Intent wins over rigour** |
| Z201/Z202/Z203/Z204 | Any | `2` or `3` | Inviolable |

---

## When to Suppress vs When to Fix {#guidance}

Use suppression for **documented intent**, not evasion:

- **Historical brand references** — CHANGELOG entries, migration guides, and historical documentation may legitimately retain obsolete product naming.
- **ToC navigation links** — `[Section](#section-name)` patterns that trigger Z107 in long documents are intentional.
- **Intentionally short pages** — A glossary page may be below the Z502 word-count threshold by design.

Do **not** suppress to:

- Hide a real broken link instead of fixing the target.
- Silence Z402 instead of adding the page to navigation.
- Bypass Z201/Z204 to "document" a real credential or forbidden term.

---

## See Also {#see-also}

- [Handle Technical Debt](../how-to/handle-technical-debt.md) — Step-by-step guide to auditing and reducing suppression debt.
- [Scoring Algorithm](./scoring-algorithm.md) — How suppression debt interacts with the full quality score.
- [Finding Codes Reference](./finding-codes.md) — Full catalog of all Zxxx codes with remediation steps.
- [Configuration Reference](./configuration-reference.md) — Full `governance` section reference.
