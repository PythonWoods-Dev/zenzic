---

sidebar_position: 9
description: "ADR 008: Atomic filesystem parity between the English source tree and its Italian mirror — the Symmetry Guardrail."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 008: Bilingual Structural Invariant — The Symmetry Guardrail

> **DEPRECATED:** This ADR is superseded by [ADR-022](./adr-022-english-only-governance.md).
>
> **[HISTORICAL ARCHIVE]**
> As of `v0.14.0`, the Docusaurus adapter has been permanently eradicated from the Zenzic ecosystem due to the ontological limits of static analysis on runtime-generated React ASTs. This ADR is retained strictly for historical context. See the blog post *Why We Dropped Docusaurus* for the full post-mortem.

**Status:** Deprecated (Superseded by ADR-022)
**Decider:** Architecture Lead
**Date:** 2026-04-20 (D045 — Diátaxis Migration)

---

## Context

Zenzic.dev is a bilingual documentation site. English (`docs/`) is the
authoritative source; Italian (`i18n/it/docusaurus-plugin-content-docs/current/`)
is the translation mirror. Docusaurus's language switcher resolves Italian pages
by **mirroring the English filesystem path**: a user on
`/docs/reference/finding-codes` switches to `/it/docs/reference/finding-codes` —
and Docusaurus serves the file at the corresponding path in the `i18n/it/` tree.

During the Diátaxis migration, 29 English files were renamed and
moved to align with the four-quadrant structure. Several Italian files were not
moved atomically in the same commit. The result: the language switcher produced
**404 errors** on pages where the English file had been moved but the Italian
mirror had not.

This class of bug is particularly insidious because:

1. **No build-time error is produced.** `onBrokenLinks: 'throw'` only detects

   internal `[text](link)` references — it does not validate language switcher
   paths.

2. **The bug is invisible in development mode.** `npm run start` serves a single

   locale. The switcher is inactive. The 404 only appears in `just build` output
   when both locales are built simultaneously.

3. **The time-to-detection window is long.** A missing IT file discovered three

   commits after the EN rename requires a forensic git blame to trace — the
   coupling between the two moves is no longer visible in the history.

---

## Decision

> **Every structural change to `docs/` must be applied atomically to
> `i18n/it/docusaurus-plugin-content-docs/current/` in the same commit.**

This is not a recommendation — it is a hard invariant. Three specific rules
follow from it:

### Rule 1 — Atomic Moves

Any file move or rename applied to a file in `docs/` must be accompanied by a corresponding move or rename in the Italian mirror in the same commit.

### Rule 2 — Slug Parity

If a `slug:` value is changed in an English file, it must be changed identically in the corresponding Italian file. A diverged `slug:` causes the language switcher to produce a 404.

### Rule 3 — Symmetry Validation

Before committing any change that touches the filesystem structure, structural symmetry must be verified.

> **Deprecated (v0.14):** The bilingual symmetry check procedure and the `docs-it/` tree were removed when Italian support was eradicated (ADR-022). This rule is retained for historical context only.

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.

### 1. Italian is a First-Class Citizen

The Italian documentation is not a secondary asset or a "nice to have". It is
part of the Privacy Gate contract. A link that works in English but 404s in
Italian is a **structural failure** of the documentation system — equivalent to
a broken internal link in the English tree.

### 2. The Language Switcher Has No Safety Net

Docusaurus's `onBrokenLinks: 'throw'` does not cover language switcher paths.
This means the only safeguard is the contributor discipline enforced by this ADR.
There is no build-time backstop.

### 3. Git History Coherence

An atomic commit that moves both EN and IT files creates a **coherent history
unit**: the rename is a single, reversible step. Split commits create
history noise and make bisect unreliable when investigating regressions.

---

## Invariants (Non-Negotiable)

- The symmetry `diff` command must exit 0 before any commit that modifies the

  filesystem structure of `docs/` or `i18n/it/`.

- New files added to `docs/` must have a corresponding placeholder added to `i18n/it/`

  **in the same commit** — even if the Italian content is a copy of the English
  until a translation is provided.

- The pre-commit hook (`pre-commit-config.yaml`) enforces symmetry at the gate.

  Bypassing it with `--no-verify` on a structural commit is a Class 1 violation
  (Technical Debt).

---

## Consequences

- Every contributor who renames or moves a documentation file must be aware of

  the Italian mirror — this is a non-optional part of the contribution workflow
  documented in `CONTRIBUTING.md`.

- The `just lint-all` recipe (`uvx pre-commit run --all-files`) enforces this

  check in CI. A PR that breaks structural symmetry will fail at the gate.

- The symmetry invariant applies to **directory structure** only. Italian

  *content* may lag behind English during active development cycles, as long as the file
  is present (even as a placeholder). A 404 is worse than a stale translation.
