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
  - Formally expanded the Mirror Law protocol to 10 mandatory targets, elevating the `zenzic init` template (`templates.py`) and the VS Code IntelliSense JSON Schema (`zenzic.schema.json`) alongside core codes, scorer, scoring algorithm, scoring system, finding codes encyclopedia, rule cards, mkdocs nav, and lab fixtures.
- **CLI Init Configuration Template Remediation**:
  - Synchronized `zenzic init` templates (`templates.py`) across `.zenzic.toml`, `.zenzic.local.toml`, and `pyproject.toml` with all 16 Policy-as-Code fields including the 4 new SDD policies, updated GitHub Action snippets to `pythonwoods/zenzic-action@v2`, purged obsolete `Z120-Z124` polyglot comments, and added topological rule codes (`Z410`, `Z411`, `Z412`, `Z620`) to default `directory_policies` examples.

### Removed

- **`Z113` (`AUTHOR_KEY_COLLISION`) and `Z114` (`LARGE_PAGINATION_SET`) — BREAKING**:
  - Both codes are removed entirely from `codes.py`'s `CODE_DEFINITIONS`/`CODE_NAMES` registry, their rule cards, `finding-codes.md`, `cli.md`, `scoring-algorithm.md`, `scoring-system.md`, and the `zenzic inspect capabilities` "Blog Integrity Guard" scanner listing. Neither code ever had live detection logic since introduction — confirmed by exhaustive grep across the engine (no emission site in `scanner.py`, `validator.py`, `rules.py`, or any adapter) — so `zenzic inspect capabilities` was presenting an always-active scanner that in fact never ran. Removed rather than retained as an unimplemented placeholder, consistent with this project's existing precedent for a fully-superseded code identity (`Z118` → `Z620`): no stub, no deprecated-but-present marker. `docs/rules/Z113.md` and `Z114.md` are deleted; `docs/_redirects` now sends both URLs (and their historical `/docs/`-prefixed crawl variants) to the `rules/` index rather than a specific successor page, since none exists. Any external tooling, saved baseline, or custom rule configuration referencing `Z113`/`Z114` by name should be updated — these identifiers no longer exist in the registry.

### Fixed

- **`check links`/`check placeholders` Never Detected Credential Leaks — Security-Behavior Change**:
  - `zenzic check links` and `zenzic check placeholders` now correctly detect credential/secret leaks (`Z201`) and forbidden terms (`Z204`) and exit `2`, matching `check all`'s existing Tier-0 "Exit 2: Credential Scanner Breach — Never suppressible" contract. **Previously, both subcommands silently discarded credential-scanner results**: the underlying scan already ran on every file (as part of the same `scan_docs_references()` pipeline `check_all` uses), but neither subcommand ever read `IntegrityReport.security_findings` — a leaked AWS key or forbidden term in a file scanned via `check links`/`check placeholders` alone produced zero signal and an ordinary exit `0`/`1`. **If you run `zenzic check links` or `zenzic check placeholders` in isolation (e.g. as a narrower pre-commit hook than `check all`) and your script or CI job only expects exit codes `0`/`1` from these two commands, it may now receive exit `2` (or `3`, for a fatal path-traversal finding) where it previously would not have — this is the fix taking effect, not a new false positive.** No performance impact: the credential scan already ran; this only surfaces results that were already computed.
- **Z205 Exit-Code/Severity Contract (Tier-0)**:
  - `Z205` (`FORBIDDEN_SCHEME`) now maps to `security_breach` severity in `_finding_severity()`, restoring the Tier-0-mandated Exit 2 and non-suppressible behavior it shares with `Z201`/`Z204`. Previously fell through to its raw catalog severity (`error`, Exit 1) since it never passes through the credential-scanner bridge that sets `security_breach` for `Z201`/`Z204`.
- **`check links` Exit-Code Gap for Security Breaches**:
  - `zenzic check links` now exits 2 (and honors `security_breach` severity) in every output format (text, JSON, SARIF, GitHub annotations), matching `check all`'s existing behavior. Previously it only checked `security_incident` (Exit 3) and `error` (Exit 1) — a `Z205`-class finding fell through to Exit 1 instead of the Tier-0-mandated Exit 2.
- **`check all --format json` Missing Security-Breach Marker**:
  - The `checkAllReport` JSON payload now includes `security_breaches` and `security_incidents` integer count fields, so a JSON consumer can detect a breach without parsing link-error message text or relying solely on the process exit code. `zenzic-output.schema.json` updated to match.
- **`zenzic lab` Exit Code Now Reflects Scenario Pass/Fail**:
  - `zenzic lab <code>`/`zenzic lab all` now exit 1 if any scenario does not meet its expectation, and 0 otherwise — previously always exited 0 regardless of the printed PASS/FAIL verdict, which defeated `lab all`'s use as a regression gate (e.g. in CI).
- **`check <file>` VSM Scoping Bug for Files Outside `docs_dir`**:
  - `zenzic check all <file>` (and other single-file `check` invocations) on a file outside the configured `docs_dir` (e.g. `CHANGELOG.md`, `README.md`) now preserves the full site's VSM instead of rebuilding one scoped to just that file's parent directory. Previously this produced false `Z103`/`Z410`-style "unreachable" findings for links to the rest of the real site. Matches the Language Server's existing behavior (`_resolve_docs_root()` always resolves the full workspace, never re-scoped per file).
- **Z107 False Positive on Same-Page Cross-References**:
  - Two same-page cross-reference links in `docs/reference/finding-codes.md` whose visible text collided with their target anchor's slug (tripping `Z107 CIRCULAR_ANCHOR`'s same-text-as-fragment heuristic even though they correctly pointed to a different section) were reworded. `Z107`'s underlying rule logic — it should compare a link's position against its target's heading location, not just text-vs-fragment slug equality — remains a known false-positive source, tracked separately.
- **LSP Code Action UX Determinism for Topological Findings (ADR-093)**:
  - The Language Server Protocol server (`src/zenzic/lsp/server.py`) now recognizes `NON_INLINE_SUPPRESSIBLE_CODES` (`Z401`, `Z402`, `Z404`, `Z405`, `Z406`, `Z410`, `Z411`, `Z412`, `Z620`).
  - Instead of offering an ineffective inline comment QuickFix edit, the LSP emits a standard `disabled` CodeAction explaining: *"Zxxx is a topological finding. Configure suppression in .zenzic.toml via [directory_policies] or [per_file_ignores]."*, eliminating misleading edits and protecting the TOML Root Key Law.
- **`check <file>` DQS Score No Longer Silently Mixes File and Project Scope**:
  - The suppression/technical-debt penalty in `zenzic check all <file>`'s DQS score (and the `suppression_count`/`suppression_debt_pts`/`debt_status` fields in its `--format json` payload) is now scoped to the target file when one is given, matching the Z-code finding penalties, which were already file-scoped. Previously, a single-file scan's score correctly excluded findings from other files but still applied the *whole project's* suppression debt, producing a hybrid number that was neither a true per-file score nor a true project score, undocumented either way. The suppression CAP fail-hard gate and the `🔒 Suppression Audit` text footer remain intentionally project-wide (the CAP is a project-level governance ceiling, not a per-file concept).
- **`check <file>` Text Output Now Labels the Suppression Audit Footer's Scope**:
  - The `🔒 Suppression Audit: N/cap` footer now appends `(project-wide)` when `check all <file>` is given a single-file target, since the DQS score line directly above it is file-scoped (see above) but this footer's number deliberately stays project-wide (the suppression CAP is a project-level governance ceiling, not a per-file concept). Previously the two adjacent lines showed silently different, unstated scopes. A full-project scan (no target) is unaffected — no label is added since there is no scope mismatch to disambiguate.
- **`check <file>` on a Target Outside `docs_dir` Never Ran the Rule Engine On It At All**:
  - `zenzic check all <file>` for a target outside the configured `docs_dir` (e.g. `CHANGELOG.md`, `README.md` at repo root) now correctly runs the rule engine (all `Z1xx`-`Z6xx` content/editorial rules) on that target file. Previously, no code path ever added an out-of-tree target into the scan's file set, so such a target silently received zero rule-engine findings and a falsely perfect score, with no crash or warning. Verified against the real repository's own `CHANGELOG.md`: previously 0 findings / `DQS 98/100`; now correctly reports `Z512` (a genuine empty-heading-section finding) / `DQS 99/100`.
- **`check <file>` No Longer Runs the Full Rule Engine on Every Project File**:
  - `zenzic check all <file>` now skips the rule-engine pass (AST parsing + all `Z1xx`-`Z6xx` rules) on every file except the target — previously it ran unconditionally on the entire project (e.g. all 262+ files) regardless of the single-file target, then discarded all but the target's findings after the fact. Measured ~90% of the rule-engine's own cost eliminated (2.45s → 0.03s in a profiled run). Full VSM construction and Pass 1-3 (security/link/reference) scanning still run project-wide by design — required for correct topology, credential scanning, and link resolution — so overall wall-clock time remains roughly proportional to project size, not target-file size (measured ~18-26% total reduction, not an order of magnitude). True near-instant single-file checking would require a persistent process sharing a cache across invocations, the way the Language Server already does — not achievable as a CLI-only fix; tracked as part of the open CLI/LSP shared-analysis-primitive architectural decision (see Known Limitations below).
- **`check all --format json`'s `references` Field Was Missing Rule-Engine Findings and All Warnings** (non-breaking enrichment, not a removal):
  - The `checkAllReport` JSON payload's `references` array now includes rule-engine findings (`Z1xx`-`Z6xx` content/editorial rules, e.g. `Z502` SHORT_CONTENT, `Z512` HEADING_SECTION_EMPTY) — previously these lived on a separate `IntegrityReport.rule_findings` attribute that `_output_check_all_json_findings` never read, so they were always silently absent from this field even when text/SARIF output correctly reported them. The pre-existing filter that excluded warning-severity reference findings (Z1xx/Z3xx) from this field was also removed for internal consistency: the field is named `references`, not `reference_errors`, and text/SARIF output already report both severities. Existing consumers reading `references` as an array of strings are unaffected — the schema shape (`zenzic-output.schema.json`) is unchanged; only the array's contents grow to match what other output formats already reported. `zenzic-mcp` does not consume this payload (its `check_document` tool is built against `IncrementalAnalysisEngine` directly, precisely to avoid depending on this CLI-private JSON shape) — the real consumers are external CI integrations and third-party tooling invoking `zenzic check all --format json` directly.
- **`nox -s mutation`'s Working-Copy Staging Was Missing Every Non-`src/` File the Build and Test Suite Require**:
  - `[tool.mutmut] also_copy` (`pyproject.toml`) now includes `README.md` and `examples/` (required by the hatchling build backend's `[project].readme` and `[tool.hatch.build.targets.wheel.force-include]`) alongside `zenzic-baseline.schema.json` and `zenzic-output.schema.json` (required by schema-compliance tests) — previously only `src/` was staged, so `mutmut run`'s pre-flight baseline collection failed immediately (0 of 2,338 mutants ever tested) with a missing-file error, silently making the Core's entire mutation-testing gate non-functional. Enumerated by reading the build backend's own config sections directly, not by trial and error.
- **Z110 Code-Identity Collision (BREAKING for existing baselines)**:
  - `Z110` used to be emitted by two independent, semantically unrelated code paths: `src/zenzic/models/config.py` for `CONFIG_SYNTAX_ERROR` (a non-suppressible pre-scan TOML-syntax guard) and `src/zenzic/core/scanner.py` for `STALE_ALLOWLIST_ENTRY` (a suppressible warning about an unused `absolute_path_allowlist` entry). `codes.py`'s own schema docstring — self-described as "the single source of truth for code assignments" — still documented the old `STALE_ALLOWLIST_ENTRY`/`VIRTUAL_ROUTE_BROKEN` meanings for `Z110`/`Z111` while its `CODE_DEFINITIONS`/`CODE_NAMES` dicts a few hundred lines below had already moved on to `CONFIG_SYNTAX_ERROR`/`CONFIG_SCHEMA_ERROR`, self-contradicting within the same file. Because `Z110` is in `NON_SUPPRESSIBLE_CODES`, and the DQS security override collapses the score to 0/100 for *any* finding under a non-suppressible code, a stale allowlist entry — an ordinary configuration-hygiene nit — silently zeroed a project's entire document quality score exactly like a genuine credential leak would.
  - `STALE_ALLOWLIST_ENTRY` is now emitted as **`Z112`** (the previously-reserved, unused slot), leaving `Z110` = `CONFIG_SYNTAX_ERROR` untouched. `Z111` was investigated and confirmed dead code — `VIRTUAL_ROUTE_BROKEN` had no live emission site anywhere in the engine (only in stale docs and the schema docstring); no renumbering was needed for it, only a documentation/docstring correction to `CONFIG_SCHEMA_ERROR`, its actual current live meaning.
  - **Action required**: if your saved `.zenzic-score.json` baseline (or any historical SARIF/JSON output you diff against) was generated before this release and counts `Z110` for a stale-allowlist condition, that count now belongs under `Z112` instead. Run `zenzic score --save` (or your project's equivalent baseline-update command) after upgrading to avoid a false `zenzic diff` regression report against a baseline keyed on the old code assignment.

### Known Limitations

- **CLI/LSP Topology Model Divergence**: the CLI's `check_all` pipeline and the Language Server's `IncrementalAnalysisEngine` do not share a common analysis primitive. Most steps (file discovery, rule engine construction/execution, config loading, adapter resolution) genuinely are shared; the two areas that are not are per-file content caching within a single CLI run (partially addressed this release — see below) and, more significantly, orphan/topology detection: the CLI's `Z402` (nav-membership-based) and the LSP's `Z410`/`Z411` (VSM-graph-reachability-based) are two independent algorithms for related-but-not-identical concepts. Formally tracked as an open architectural decision, not silently accepted — see the forthcoming ADR in `docs/developers/explanation/adr-vault/`.
  - This release's caching fix: `_to_findings` no longer re-reads a file's content twice within a single call when that file appears in both `snippet_errors` and `reference_reports`. This addresses only the redundant read *inside* `_to_findings` — the seven independent sub-checks in `_collect_all_results` (`find_orphans`, `find_unused_assets`, `validate_snippets`, etc.) still walk and read files independently of each other; deduplicating across those would require `scanner.py`/`validator.py` to expose raw file content on their result objects, which is a larger change than this release's scope.
- **`check <file>` Is Still Not Near-Instant**: `zenzic check all <file>` now skips the rule-engine pass on non-target files (~18-26% faster overall; ~90% of the rule engine's own cost eliminated); full VSM construction and Pass 1-3 security/topology scanning still run project-wide by design, so overall time remains proportional to project size, not target-file size. True near-instant single-file checking requires a persistent process (see the LSP) — this is not planned for the CLI without a broader architectural change, tracked alongside the CLI/LSP topology-model divergence noted above as the same underlying gap: no shared, persistent analysis primitive between the two.

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
