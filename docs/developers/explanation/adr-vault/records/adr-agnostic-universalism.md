---

description: "ADR 005: Z404 CONFIG_ASSET_MISSING extended to all supported engines — not just Docusaurus."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 005: Agnostic Universalism — Z404 for All Engines

> This ADR's core decision — universal Z404 coverage across all supported engines — remains
> active and current for the engines Zenzic supports today: MkDocs, Zensical, and Standalone.
> Docusaurus was removed as of `v0.14.0` (see [ADR 006](./adr-unified-perimeter.md)); the table
> below keeps its row, marked accordingly, since it illustrates the pre-universalization state
> this ADR's own Context section describes.

**Status:** Active
**Decider:** Architecture Lead
**Date:** 2026-04-20

---

## Context

Z404 (`CONFIG_ASSET_MISSING`) was originally implemented exclusively for the
Docusaurus adapter. It detected when a file declared in `docusaurus.config.ts`
(favicon, Open Graph image, custom CSS) did not exist on disk.

This created a structural contradiction: Zenzic's public claim is that it is a
**Privacy Gate for all documentation engines**. Offering a config-asset integrity
check only to Docusaurus users violated this claim. An MkDocs project declaring
a `theme.favicon` that pointed to a non-existent file would receive no
diagnostic — a silent gap in the safety boundary.

---

## Decision

Z404 was extended from a Docusaurus-only check to a **universal check** covering
all supported engines. Each adapter’s config-asset check is implemented as a
module-level function. The CLI pipeline dispatches it per engine type after the
main scan pass.

| Engine | Assets checked |
|--------|---------------|
| Docusaurus *(removed v0.14.0, historical)* | `customCss`, `favicon`, Open Graph `image`, social card paths in `themeConfig` |
| MkDocs | `theme.favicon`, `theme.logo` (resolved relative to `docs_dir/`) |
| Zensical | `[project].favicon`, `[project].logo` |
| Standalone | — (no engine config file; check is a no-op) |

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.

### 1. Privacy Gate Is a Universal Contract

A Privacy Gate that applies only to Docusaurus is not an Exclusion Zone — it is a
**scoped feature with an undocumented engine assumption**. The moment a check is engine-specific
without a technical reason, it signals to contributors that engine parity is
optional. That signal compounds over releases.

### 2. The Adapter Protocol Already Provides the Hook

The universalism decision extended an existing pattern — module-level per-adapter
validation — to all supported engines, not just Docusaurus.

### 3. Preventing the "Trusted Config" Assumption

The implicit assumption that engine configuration files contain valid asset paths
is the same category of trust error that Zenzic was designed to eliminate. A
`theme.favicon: assets/icon.png` that doesn't exist is a broken link — it just
happens to live in a YAML file rather than a Markdown document.

---

## Implementation

Each engine’s config-asset check reads the engine config file, resolves declared
asset paths against `docs_root`, and emits a `Finding` with code `Z404` for each
path that does not exist on disk. The CLI dispatches these checks after the main
scan pass, ensuring Z404 findings appear in the same SARIF report and exit-code
accounting as all other findings.

---

## Consequences

- MkDocs and Zensical users gain asset integrity validation without any config change.
- Adding a new engine adapter requires implementing `check_config_assets()` — the

  protocol now enforces this explicitly (a `NotImplementedError` is raised for
  adapters that skip it).

- Z404 is now classified as a **universal quality check**, not an engine-specific

  feature, in `reference/finding-codes.md`.
