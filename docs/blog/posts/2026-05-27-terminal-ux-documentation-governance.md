---
title: "Terminal UX as a Governance Interface: How Zenzic Renders Diagnostic Contracts"
date: 2026-05-27
authors:
  - pythonwoods
description: "Terminal UX as a Governance Interface: How Zenzic Renders Diagnostic Contracts"
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

A linter reports violations within individual files. A governance engine verifies
that a set of invariants holds across the entire document graph — and halts the
pipeline when one does not.

This analysis reflects the terminal contract as shipped on the v0.9.0 release line.

<!-- more -->

## Beyond Linting

The distinction between a linter and a governance engine is not one of depth.
It is one of scope and contract type.

A linter's analysis terminates at the file boundary. It reports violations of
formatting rules — incorrect indentation, undefined references within a single
file, missing required metadata fields. Each file is processed independently,
in isolation. The diagnostic is local: a violation in `file-a.md` has no
bearing on the analysis of `file-b.md`.

Zenzic operates on a different unit: the document graph. A single invocation of
`zenzic check all` evaluates the entire scope defined by the adapter
configuration — every internal link, every navigation contract, every credential
surface, every suppression directive — as a unified object. No file is analyzed
in isolation, because no documentation system exists in isolation. A broken
internal link is not a property of the page that contains it. It is a property
of the relationship between two nodes in the graph. An orphaned page is not
detectable from within that page. It is detectable only when the navigation
manifest is resolved against the full file tree.

This distinction has a direct consequence for the design of the terminal output.
When the unit of analysis is a graph, a single-line error message is
insufficient. The interface must communicate: what the violation is, where in
the file it occurs, which contract it violates, and enough surrounding context
for the reader to understand the issue without opening the source file.

Zenzic exposes two orthogonal instruments for evaluating the document graph:

* `zenzic check` — a binary gate. It returns an exit code in `{0, 1, 2, 3}`
    and a structured list of findings. The exit code is the contract with CI:
    deterministic, machine-readable, with semantics that hold regardless of
    configuration.
* `zenzic score` — a weighted penalty model. It returns a Documentation
    Quality Score (DQS) in the range 0–100, decomposed by diagnostic category.
    The output is audit-oriented: it answers not whether the documentation
    passes, but by how much and in which domains it deviates from the
    governance baseline.

Both instruments share the same analysis engine. They answer different questions.

The rest of this article examines each layer of the terminal interface that
implements these contracts: the run header, the diagnostic renderer, the
suppression audit model, and the exit code semantics.

<ZenzicTerminal title="zenzic check all">
<span className="text-zinc-400 block">standalone · 20 files (14 docs, 6 assets) · 0.8 s · 38 files/s</span>
<span className="text-emerald-500 font-medium block mt-1">✔ All checks passed — exit 0</span>
</ZenzicTerminal>

---

## Information Density in the Run Header

At the end of every `zenzic check` invocation, a single telemetry line is
printed below the findings list:

```text
standalone • 20 files (14 docs, 6 assets) • 0.8s • 38 files/s
```

This line encodes four independent signals. Each field answers a distinct
operational question.

**Adapter mode** (`standalone`). Zenzic resolves the adapter from the project
configuration at startup. Supported modes include `docusaurus`, `mkdocs`,
`zensical`, and `standalone`. The adapter determines the navigation contract: which files
constitute the document graph, how routes are resolved, and which structural
checks are active. When no recognized configuration file is present, `standalone`
is the default.

!!! note "Historical snapshot"
    This post is dated 2026-05-27. `docusaurus` was a real, supported adapter mode
    at the time of writing; it was removed in v0.14.0 (2026-06-21) — see
    [Why We Dropped Docusaurus](2026-06-13-why-we-dropped-docusaurus.md). The
    real current adapter modes are `mkdocs`, `zensical`, `standalone`,
    `prebuilt`, and `vsm`.

The adapter label carries a constraint that is not stated elsewhere in the
output. In `standalone` mode, the navigation manifest is absent. Checks that
require a resolved route graph — orphaned-page detection being the primary
example — are structurally inactive for that run. The label is the sole
communication of this fact.

**Scope decomposition** (`20 files (14 docs, 6 assets)`). The file count is
split into two categories: documents (`.md` and `.md`) and assets (images,
data files, schema definitions, and any other non-document file within the
analyzed tree). The split is not cosmetic: document checks operate on file
content; asset checks operate on the asset manifest. Different scanners activate
for each category.

The analyzed scope is bounded by `docs_dir` and `excluded_dirs` in
`.zenzic.toml`. Files outside this boundary are not evaluated, regardless of
their position in the repository tree. The counts in the footer reflect exactly
the scope that was evaluated — nothing more, nothing less.

**Elapsed time** (`0.8s`). Wall-clock duration from invocation to the final
diagnostic line. This includes file I/O, adapter resolution, and all analysis
passes. It is not a CPU-time measurement. On the same hardware and the same
scope, consecutive runs produce consistent values, making elapsed time a
reproducibility indicator without additional instrumentation.

**Throughput** (`38 files/s`). Derived as scope divided by elapsed time. The
value is hardware-specific and not portable across machines. Its utility is
local: establishing a baseline on a given host makes performance regressions
in the analysis pipeline detectable before they affect CI wall time.

| Field | Example | What it communicates |
|---|---|---|
| Adapter mode | `standalone` | Active navigation contract; which structural checks apply |
| Scope | `20 files (14 docs, 6 assets)` | Exact file boundary of the analysis; nothing outside is evaluated |
| Elapsed | `0.8s` | Wall-clock duration; reproducibility signal on fixed hardware |
| Throughput | `38 files/s` | Analysis rate; baseline for performance regression detection |

To enumerate the full scanner manifest active for a given configuration — codes,
capabilities, and exit-code contracts — use `zenzic inspect`.

<ZenzicTerminal title="zenzic inspect rules">
<span className="text-zinc-400 block">Rule Registry · 12 rules loaded</span>
<span className="text-emerald-500 font-medium block mt-1">✔ exit 0</span>
</ZenzicTerminal>

---

## Diagnostic Rendering

A finding is self-describing. It carries enough information for triage without
opening the source file, navigating the repository, or invoking additional tools.
This property is not incidental — it is a design constraint that shapes every
layer of the diagnostic output.

Each finding is rendered as a three-layer block.

**Layer 1 — Finding header.** The first line identifies the finding
unambiguously: file path, line number, column (when available), Z-code, and
message. The Z-code is the machine-readable identifier of the violated contract.
The message is a human-readable description of the violation.

```text
docs/guides/install.md:47:29
✘ Z101  Broken internal link → install.md
```

**Layer 2 — Source snippet.** Five lines of source context are shown: two lines
before the error line, the error line itself, and two lines after. Context lines
are rendered with a `│` gutter marker in muted style. The error line is rendered
with a `❱` gutter marker in error style.

```text
     45  │  ## Installation Prerequisites
     46  │
     47  ❱  See the [Installation Guide](install.md) for details.
     48  │
     49  │  Continue to the Configuration section when ready.
```

This window is the primary triage surface. The two lines of context before the
error establish what the offending line belongs to — a section header, a
paragraph, a list item. The two lines after establish what follows. In a CI
log, this eliminates the need to reproduce the run locally, open the file, or
reconstruct the surrounding context manually. The context-switching overhead
between reading a pipeline failure and understanding its location is zero.

**Layer 3 — Caret row.** When the scanner that produced the finding also
provides the exact byte offset of the matched token in the source line, a caret
row is rendered immediately below the error line. The caret spans the matched
token precisely.

```text
     47  ❱  See the [Installation Guide](install.md) for details.
            │                             ^^^^^^^^^^
```

The caret length equals the length of the matched string. The caret start
position equals the byte offset of that string in the raw source line — the
exact value returned by the pattern match, with no rounding, padding, or
adjustment. If the scanner does not report a native column position, the caret
row is omitted entirely. There is no fallback, no estimation, and no
approximation. A caret in the output is always exact; the absence of a caret
means the scanner operates at line granularity rather than token granularity.

The practical consequence: for findings where column data is available — such
as credential detections and inline link violations — the operator sees the
precise token that triggered the finding. No surrounding content requires manual
inspection.

The three layers together form a self-contained diagnostic unit:

```text
docs/guides/install.md:47:29
✘ Z101  Broken internal link → install.md

     45  │  ## Installation Prerequisites
     46  │
     47  ❱  See the [Installation Guide](install.md) for details.
            │                             ^^^^^^^^^^
     48  │
     49  │  Continue to the Configuration section when ready.
```

<ZenzicTerminal title="zenzic check all">
<div className="text-zinc-400 text-[11px] mb-2">docs/guides/install.md:47</div>
<div className="flex gap-2 items-baseline"><span className="text-rose-500">✘</span><span className="bg-rose-500/10 text-rose-400 px-1 rounded-sm text-[11px]">[Z101]</span><span className="text-zinc-300">Broken internal link → install.md</span></div>
<div className="mt-2 text-rose-500 font-semibold text-[11px] tracking-wide">FAILED — exit 1</div>
</ZenzicTerminal>

---

## The Mathematics of Suppression Debt

The `zenzic:ignore` inline directive tells Zenzic to skip the finding on the
annotated line. Each active directive — whether applied inline or via the
per-file suppression list in `.zenzic.toml` — costs exactly one point from the
Documentation Quality Score. No directive is free.

This is the flat-cost model. It replaced an allowance-based model in which a
configured number of suppressions carried no penalty, and costs applied only to
the excess. The allowance model produced a predictable outcome: teams treated
the free allowance as a budget to fill, not a limit to avoid. A model in which
the first N suppressions are free and the (N+1)th costs a point is not a
governance model — it is a permission slip. The incentive it creates is to
suppress freely below the free threshold and worry about governance only after
that line is crossed.

Under the flat-cost model, the first suppression costs one point. The tenth
costs one point. There is no free zone. The `suppression_cap` value configured
in `.zenzic.toml` is not an allowance — it is a hard-fail ceiling. When the
suppression count exceeds the cap, the build fails regardless of the numeric
score.

**The DQS formula.** The Documentation Quality Score is computed in three
stages. First, per-category subtotals:

$$
\text{DQS} = \underbrace{\sum_{i=1}^{4} \max\!\bigl(0,\ C_i - D_i\bigr)}_{\text{category subtotal}} - n_{\text{sup}}
$$

Where:

* $C_i$ is the point cap for category $i$: Structural (30), Navigation (25),
    Content (20), Brand & Governance (25).
* $D_i = \sum_{c \in i} p_c \cdot k_c$ is the total penalty for category $i$:
    the sum of per-code penalty $p_c$ multiplied by finding count $k_c$, for
    all codes assigned to that category.
* $n_{\text{sup}}$ is the total count of active suppression directives, each
    contributing exactly 1 point of deduction.

Two invariants constrain the formula:

* **Category Cap Invariant.** Deductions within a category cannot exceed the
    category cap. One thousand occurrences of a 1-point finding in the Content
    category deduct at most 20 points — the Content cap. The remaining
    categories are unaffected.
* **Gravity Cap.** If the Brand & Governance category is fully zeroed by
    findings, the category subtotal is capped at 70. Uncontrolled governance
    violations impose a structural ceiling on the total score regardless of how
    other categories perform.

Suppression debt ($n_{\text{sup}}$) is applied after both invariants, as a
final deduction from the adjusted subtotal.

**The Quality Breakdown Ledger.** The `zenzic score` command renders a
per-category table that exposes the deduction mechanics:

```text
 Quality Breakdown
 ─────────────────────────────────────────────────────────
   Category      Issues  Weight   Raw Pts      Applied Pts
 ✔ structural         0    30%          0                0
 ✔ navigation         0    25%          0                0
 ✔ content            0    20%          0                0
 ✘ brand             42    25%        -60     -25 (CAPPED)
 ─────────────────────────────────────────────────────────
   Σ Subtotal                                           75

  ! Gravity Cap Enforcement (Brand = 0):   -5 pts
  ! Technical Debt (5 suppressions):       -5 pts
  = Final Quality Score                    65 / 100
```

**Raw Pts** is the total deduction accumulated within the category before the
cap is applied. Here, 42 brand findings produced −60 raw points. **Applied Pts**
is the deduction after the category cap: the Brand cap is 25 points, so the
applied penalty is −25. The `(CAPPED)` marker confirms that the raw deduction
was truncated by the cap boundary. The difference between Raw Pts and Applied
Pts is not recovered — it signals that the category has been fully zeroed.

The `! Gravity Cap Enforcement` line appears when the zeroed Brand category
causes the subtotal to be reduced from 75 to 70, applying a 5-point structural
penalty. The `! Technical Debt` line shows the flat-cost deduction: five active
suppression directives produce a deduction of five points, applied after all
category calculations.

The suppression count is also compared to `governance.suppression_cap`. When
the count exceeds the cap, the build fails with a distinct message:

```text
FAILED: suppression cap exceeded (36/30).
Update governance.suppression_cap in .zenzic.toml if intentional.
```

This failure is Exit 1 and remains fail-hard when suppression cap is exceeded.
It cannot be resolved by adding more `zenzic:ignore` directives — each
additional directive increases the count and the debt simultaneously.

<ZenzicTerminal title="zenzic check all"><span className="text-emerald-500 font-medium">✔ All checks passed — exit 0</span></ZenzicTerminal>

---

## Exit Semantics as a CI Contract

The exit code is not a summary of the terminal output. It is the primary
contract between Zenzic and the CI pipeline. The pipeline reads the exit code,
not the display. The display is for operators; the exit code is for automation.
This distinction determines how the exit semantics are designed.

The four exit codes and their contracts:

| Code | Trigger | Suppressible via directive? | `--exit-zero` effect |
|------|---------|-----------------------------|----------------------|
| 0 | No error-severity findings in the analyzed scope | — | No effect |
| 1 | Error-severity findings detected | Yes — via `zenzic:ignore` | Converts to 0 |
| 1 | Suppression cap exceeded | No — directives increase debt/cap pressure | No effect (fail-hard) |
| 2 | Credential detected in documentation content (Z2xx) | Never | No effect |
| 3 | Path traversal to system directories detected (Z203) | Never | No effect |

**Exit 0.** The analyzed scope contains no error-severity findings. When
`fail_under` is configured, a score below the threshold also produces Exit 1 —
so Exit 0 confirms both the absence of findings and that the Documentation
Quality Score meets the configured threshold. The scope qualifier is precise:
files outside the configured `docs_dir` boundary are not evaluated, and their
state is not reflected in the exit code.

**Exit 1.** One or more error-severity findings were detected, or the
suppression count exceeded `governance.suppression_cap`. This is the standard
CI gate. `--exit-zero` converts Exit 1 to Exit 0 only for the standard
error-findings path; suppression-cap failures remain fail-hard. The conversion
does not suppress findings from the output — they remain visible in the
terminal. `--exit-zero` cannot be combined with `--strict`; Zenzic rejects that
combination with Exit 2 at startup.

<ZenzicTerminal title="zenzic check all"><span className="text-rose-500 font-medium">✘ 1 error — exit 1</span></ZenzicTerminal>

**Exit 2.** A finding with `security_breach` severity was produced — meaning a
credential or secret was detected in the documentation source tree. This exit
code cannot be suppressed by `zenzic:ignore`, cannot be overridden by
`--exit-zero`, and cannot be silenced by per-file ignore policies. The
credential scanner (Z2xx codes) is active regardless of adapter mode,
`--offline` flag, or `--no-external` flag.

**Exit 3.** A path traversal to an operating-system system directory was
detected. This is a distinct severity class (`security_incident`) and
represents the maximum security contract: the `docs_dir` configuration value or
a scanned path attempted to escape the repository boundary toward system paths.
Like Exit 2, it precedes all other exit-code evaluation. `--exit-zero` has no
effect.

The evaluation order is fixed: Exit 3 conditions are checked first, Exit 2
second, Exit 1 third. This order ensures that security contracts are never
shadowed by governance failures or score thresholds.

---

The four elements of the terminal interface analyzed in this article — the run
header, the diagnostic block, the suppression ledger, and the exit code table —
are not independent display decisions. They form a single interface that makes
the documentation governance policy machine-readable, auditable, and
deterministic.

A `fail_under` threshold, a `suppression_cap`, a per-category penalty model,
and an immutable exit code contract are the formal encoding of what a team
considers acceptable documentation quality. The terminal output is where that
encoding is evaluated on every run. Treating it as display-only discards that
evaluation. Treating it as a governance interface — machine-readable exit codes,
auditable debt counters, caret-precise diagnostics — makes it enforceable at
the pipeline boundary.
