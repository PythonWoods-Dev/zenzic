<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added

- **Specification-Driven Development (SDD) Rule Suite**:
  - `Z521` (`REQUIRED_TABLE_COLUMN`): Enforces mandatory table column headers declared under `[policies.required_table_columns]` (globally `*` or section-scoped). Penalty: 2.0 pts (Content).
  - `Z522` (`TABLE_CELL_ENUM`): Restricts table cell values to predefined enum sets declared under `[policies.table_cell_enums]` with case-insensitive matching and precise data-row line reporting. Penalty: 2.0 pts (Content).
  - `Z523` (`HEADING_ORDER_VIOLATION`): Enforces ordered document section templates declared in `[policies].required_heading_order`. Penalty: 2.0 pts (Content).
  - `Z412` (`TRACEABILITY_BROKEN`): Enforces inbound graph link coverage from designated source namespaces to target specification documents declared in `[policies.traceability_targets]`. Penalty: 4.0 pts (Navigation).
- **GFM Table AST & Lossless Parser**:
  - Extended AST in `zenzic.core.ast` with `TableNode`, `TableRow`, and `TableCell` dataclasses fully compliant with the multiprocessing Plugin Pickling Contract.
  - Implemented $O(N)$ native GFM table parser in `zenzic.core.parser` with escaped pipe `\|` support, inline code span protection, and lossless byte-for-byte serialization.
- **Policy-as-Code Configuration Expansion**:
  - Added `required_table_columns`, `table_cell_enums`, `required_heading_order`, and `traceability_targets` to `PoliciesConfig` in `zenzic.models.config`.
- **Smart Build Engine Disambiguation**:
  - Implemented lightweight, allocation-free string inspection in `discover_engine()` (`src/zenzic/core/adapters/_factory.py`) to automatically identify Zensical projects configured via MkDocs YAML (`theme: zensical`) without YAML parser overhead or false positives in nav/comments. Backed by `tests/test_engine_discovery.py`.
- **DQS Mathematical Transparency & CLI `--breakdown`**:
  - Added `--breakdown` flag to `zenzic score` displaying a fully exploded scoring ledger with category deductions, Gravity Cap calculations, and technical debt math. Showcased in root `README.md`.
- **Architectural Decision Records (ADR-093)**:
  - Added [ADR 093](docs/developers/explanation/adr-vault/records/adr-093-topological-suppression-non-inline.md) defining the *Topological Suppression Non-Inline Invariant & LSP UX Determinism*.
- **Documentation & Rule Cards**:
  - Added rule cards `docs/rules/Z521.md`, `docs/rules/Z522.md`, `docs/rules/Z523.md`, `docs/rules/Z412.md`, registered in `mkdocs.yml` and `docs/reference/finding-codes.md`.
  - Added launch blog post `docs/blog/posts/2026-08-22-zenzic-v0310-specification-driven-development.md`.
  - Added interactive lab scenarios `z521`, `z522`, `z523`, `z412` in `examples/` and registered them in `zenzic lab`.

### Changed

- **Ecosystem Positioning Overhaul**:
  - Updated tagline and core value proposition across `zenzic`, `zenzic-action`, and `zenzic-vscode` READMEs: *"Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool."*, focusing on protecting documentation graphs from AI hallucinations.
- **Mirror Law Parity Protocol (10 Mandatory Targets)**:
  - Formally expanded the Mirror Law protocol in `.claude/references/03-dqs-and-mirror-law.md` to 10 mandatory targets, elevating the `zenzic init` template (`templates.py`) and the VS Code IntelliSense JSON Schema (`zenzic.schema.json`) alongside core codes, scorer, scoring algorithm, scoring system, finding codes encyclopedia, rule cards, mkdocs nav, and lab fixtures.
- **CLI Init Configuration Template Remediation**:
  - Synchronized `zenzic init` templates (`templates.py`) across `.zenzic.toml`, `.zenzic.local.toml`, and `pyproject.toml` with all 16 Policy-as-Code fields including the 4 new SDD policies, updated GitHub Action snippets to `pythonwoods/zenzic-action@v2`, purged obsolete `Z120-Z124` polyglot comments, and added topological rule codes (`Z410`, `Z411`, `Z412`, `Z620`) to default `directory_policies` examples.

### Fixed

- **Z205 Exit-Code/Severity Contract (Tier-0)**:
  - `Z205` (`FORBIDDEN_SCHEME`) now maps to `security_breach` severity in `_finding_severity()`, restoring the Tier-0-mandated Exit 2 and non-suppressible behavior it shares with `Z201`/`Z204`. Previously fell through to its raw catalog severity (`error`, Exit 1) since it never passes through the credential-scanner bridge that sets `security_breach` for `Z201`/`Z204`.
- **LSP Code Action UX Determinism for Topological Findings (ADR-093)**:
  - The Language Server Protocol server (`src/zenzic/lsp/server.py`) now recognizes `NON_INLINE_SUPPRESSIBLE_CODES` (`Z401`, `Z402`, `Z404`, `Z405`, `Z406`, `Z410`, `Z411`, `Z412`, `Z620`).
  - Instead of offering an ineffective inline comment QuickFix edit, the LSP emits a standard `disabled` CodeAction explaining: *"Zxxx is a topological finding. Configure suppression in .zenzic.toml via [directory_policies] or [per_file_ignores]."*, eliminating misleading edits and protecting the TOML Root Key Law.

## Historical Releases

- v0.30.x archive: [changelogs/v0.30.x.md](./changelogs/v0.30.x.md)
- v0.29.x archive: [changelogs/v0.29.x.md](./changelogs/v0.29.x.md)
- v0.28.x archive: [changelogs/v0.28.x.md](./changelogs/v0.28.x.md)
- v0.27.x archive: [changelogs/v0.27.x.md](./changelogs/v0.27.x.md)
- v0.26.x archive: [changelogs/v0.26.x.md](./changelogs/v0.26.x.md)
- v0.25.x archive: [changelogs/v0.25.x.md](./changelogs/v0.25.x.md)
- v0.24.x archive: [changelogs/v0.24.x.md](./changelogs/v0.24.x.md)
- v0.23.x archive: [changelogs/v0.23.x.md](./changelogs/v0.23.x.md)
- v0.22.x archive: [changelogs/v0.22.x.md](./changelogs/v0.22.x.md)
- v0.21.x archive: [changelogs/v0.21.x.md](./changelogs/v0.21.x.md)
- v0.20.x archive: [changelogs/v0.20.x.md](./changelogs/v0.20.x.md)
- v0.19.x archive: [changelogs/v0.19.x.md](./changelogs/v0.19.x.md)
- v0.18.x archive: [changelogs/v0.18.x.md](./changelogs/v0.18.x.md)
- v0.17.x archive: [changelogs/v0.17.x.md](./changelogs/v0.17.x.md)
- v0.16.x archive: [changelogs/v0.16.x.md](./changelogs/v0.16.x.md)
- v0.15.x archive: [changelogs/v0.15.x.md](./changelogs/v0.15.x.md)
- v0.14.x archive: [changelogs/v0.14.md](./changelogs/v0.14.md)
- v0.13.x archive: [changelogs/v0.13.md](./changelogs/v0.13.md)
- v0.12.x archive: [changelogs/v0.12.md](./changelogs/v0.12.md)
- v0.11.x archive: [changelogs/v0.11.md](./changelogs/v0.11.md)
- v0.10.x archive: [changelogs/v0.10.md](./changelogs/v0.10.md)
- v0.9.x archive: [changelogs/v0.9.md](./changelogs/v0.9.md)
- v0.8.x archive: [changelogs/v0.8.md](./changelogs/v0.8.md)
- v0.1.x–v0.7.x archive index: [changelogs/README.md](./changelogs/README.md)
