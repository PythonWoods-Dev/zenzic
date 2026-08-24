<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Category Cap Math — Empirical Sandbox

Demonstrates the DQS Category Cap invariant and the ADR-031 Gate Paradox
resolution, both introduced in Zenzic v0.8.0.

## What This Example Shows

| Property | Value |
| :--- | :--- |
| Engine | zensical (explicit nav) |
| Structural findings | 5 × Z104 FILE_NOT_FOUND (8.0 pts each) |
| Structural raw penalty | 40 pts |
| Structural cap | 30 pts |
| Expected DQS | **70/100** |
| Expected exit code | **0** (score ≥ `fail_under = 0`; no cap breach) |

`zenzic check all` exits 1 because Z104 is an error-level finding.

## Setup

`zensical.toml` declares an explicit nav (`index.md`, `orphan.md`).  All nav
pages are REACHABLE — no Z402 ORPHAN_PAGE findings.

`docs/index.md` contains five links to files that do not exist on disk:

```text
[Alpha Reference](missing-alpha.md)    → Z104 FILE_NOT_FOUND (8.0 pts)
[Beta Reference](missing-beta.md)      → Z104 FILE_NOT_FOUND (8.0 pts)
[Gamma Reference](missing-gamma.md)    → Z104 FILE_NOT_FOUND (8.0 pts)
[Delta Reference](missing-delta.md)    → Z104 FILE_NOT_FOUND (8.0 pts)
[Epsilon Reference](missing-epsilon.md)→ Z104 FILE_NOT_FOUND (8.0 pts)
```

## Score Arithmetic

| Tier | Issues | Raw penalty | Cap | cat\_pts |
| :--- | ---: | ---: | ---: | ---: |
| structural | 5 × Z104 | 5 × 8.0 = **40 pts** | 30 pts | **0 pts** |
| navigation | 0 | 0 pts | 25 pts | **25 pts** |
| content | 0 | 0 pts | 20 pts | **20 pts** |
| governance | 0 | 0 pts | 25 pts | **25 pts** |

```text
S_base     = 0 + 25 + 20 + 25 = 70
ω_debt     = 0 (no suppressions)
S_final    = max(0, 70 − 0) = 70
```

Without the cap: `100 − 40 = 60`.  The cap discards the 10-pt excess and
floors the Structural bucket at 0, restoring 10 pts to the final score.

## Validated Output

```console
$ zenzic score

✨ Quality Score: 70/100

                 Quality Breakdown
╭──────┬────────────────┬────────┬────────┬───────╮
│  •   │ Category       │ Issues │ Weight │ Score │
├──────┼────────────────┼────────┼────────┼───────┤
│  ✘   │ structural     │      5 │    30% │  0.00 │
│  ✔   │ navigation     │      0 │    25% │  0.25 │
│  ✔   │ content        │      0 │    20% │  0.20 │
│  ✔   │ brand          │      0 │    25% │  0.25 │
╰──────┴────────────────┴────────┴────────┴───────╯
```

Exit code: **0**.

## Cap Invariant

The raw Structural penalty (40 pts) exceeds the Structural cap (30 pts).  The
scorer clamps the Structural contribution to 0 and discards the overflow.
Adding more broken links cannot reduce the score below 70 — the tier is already
floored.

Conversely, fixing one link reduces the raw penalty to 32 pts — still above the
cap — so the score remains 70.  Only when raw penalty falls below 30 pts (four
or fewer Z104 findings at 8.0 pts each) does the structural bucket contribute
positively to the score.

## ADR-031 Gate Paradox

`docs/orphan.md` documents the three codes (Z103, Z111, Z113) that were
CI-blocking (`error` SARIF level) yet carried 0 DQS penalty before v0.8.0,
creating a "gate paradox": a project could score 100/100 while failing CI.
(Historical snapshot as of v0.8.0 — `Z111` has since been reassigned to a
different meaning, and `Z113` has been removed entirely.)

ADR-031 introduced `CodeDefinition` as a Single Source of Truth.  Since
v0.8.0, a single Z103 ORPHAN_LINK occurrence deducts **2.0 pts** (Structural).
A project with only Z103 findings now scores **98/100**, not 100/100.

> **Implementation note:** `zenzic score` reaches Z103 via the `validate_links`
> path in `validator.py`, which reports ORPHAN_BUT_EXISTING links as Z101
> UNREACHABLE (8.0 pts) rather than Z103 (2.0 pts).  Z103 is emitted by
> `VSMBrokenLinkRule.check_vsm` in the rules engine, which is invoked by
> `zenzic check links` (not by `zenzic score`).  The cap invariant demonstrated
> here holds under both codes: 40 pts raw > 30 pt cap in either case.
