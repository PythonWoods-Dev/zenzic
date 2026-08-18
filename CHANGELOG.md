<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

*Upcoming changes for the next release.*

## [0.30.0] - 2026-08-18

### Added

- **Semantic List Heuristics & Auto-Fix**:
  - `Z520` (`MALFORMED_LIST_DETECTED`): Detects paragraphs formatted as pseudo-lists using hard newlines and semicolons/commas without Markdown list markers. Supports atomic automated fix (`zenzic fix --apply`). Penalty: 2.0 pts (Content).
  - Added `MalformedListMutation` to the core AST `Mutator` engine, automatically transforming malformed paragraph lists into structured Markdown bullet lists.
  - Added rule card `docs/rules/Z520.md`, updated `mkdocs.yml` navigation, scoring references, and added interactive lab scenario `z520` (`examples/z520-malformed-list/`).
- **Editorial Style & Prose Quality Rules**: Added 5 advanced editorial style and policy-as-code linting rules:
  - `Z518` (`PASSIVE_VOICE_DETECTED`): Detects passive voice constructs in technical prose via non-backtracking RE2 regex heuristic (opt-in via `[policies].enable_passive_voice_check`). Penalty: 1.0 pt (Content).
  - `Z519` (`WEASEL_WORDS`): Detects vague or weakening qualifiers (e.g., "clearly", "simply", "obviously") in technical prose (opt-in via `[policies].weasel_words`). Penalty: 1.0 pt (Content).
  - `Z617` (`FORBIDDEN_CONTENT_PATTERN`): Enforces organizational terminology standards by detecting forbidden regex patterns in prose (opt-in via `[policies].forbidden_content_patterns`). Penalty: 2.0 pts (Governance).
  - `Z618` (`REQUIRED_HEADING_PATTERN`): Enforces structural document templates by ensuring required heading patterns exist in each document (opt-in via `[policies].required_heading_patterns`). Penalty: 3.0 pts (Governance).
  - `Z619` (`MAX_DOCUMENT_COMPLEXITY`): Restricts cognitive load and document bloat based on prose word count, heading depth, and link density (opt-in via `[policies].max_document_complexity`). Penalty: 4.0 pts (Governance).
- **Policy-as-Code Configuration Enhancements**: Added 5 new declarative policy keys to the `[policies]` table in `PoliciesConfig` (`forbidden_content_patterns`, `required_heading_patterns`, `max_document_complexity`, `weasel_words`, `enable_passive_voice_check`), complete with `zenzic config explain` introspection table and `zenzic init` template integration.
- **Mirror Law Parity for Editorial Style**: Added dedicated rule cards `docs/rules/Z518.md` through `docs/rules/Z619.md`, updated `mkdocs.yml` navigation, synchronized scoring algorithm/explanation matrices, registered finding reference entries, and added interactive lab acts (`z518`, `z519`, `z617`, `z618`, `z619`).
- **Semantic Linting & Accessibility Rules**: Implemented 5 native AST-based semantic and accessibility (a11y) rules in `zenzic.core`:
  - `Z513` (`DUPLICATE_HEADING`): Detects duplicate headings within the same document (case/whitespace/anchor invariant), preventing ambiguous anchor collisions. Penalty: 2.0 pts (Content).
  - `Z514` (`GENERIC_IMAGE_ALT_TEXT`): Detects generic filler words in image alt text (`![]()` and `<img>`), enforcing accessibility standards. Penalty: 2.0 pts (Content).
  - `Z515` (`BARE_URL_USED`): Detects raw HTTP/HTTPS URLs in prose that are not enclosed in angle brackets or Markdown links. Supports automated fix (`zenzic fix --apply`). Penalty: 1.0 pt (Content).
  - `Z516` (`MULTIPLE_H1_HEADINGS`): Enforces a single top-level `#` or `<h1>` heading per document for structural hierarchy. Severity: `error`, Penalty: 5.0 pts (Content).
  - `Z517` (`HEADING_PUNCTUATION`): Detects invalid trailing punctuation (`.`, `:`, `;`) on headings. Supports automated fix (`zenzic fix --apply`). Penalty: 1.0 pt (Content).
- **Silent-on-Success Unix Philosophy (`--quiet`, `--no-header`)**: Added `--quiet` (`-q`) and `--no-header` across all subcommands (`guard scan`, `score`, `check all`, `check links`, `check orphans`, `check placeholders`, `check references`, `check structure`, `check snippets`), muting all headers, banners, and footers to emit exactly 0 bytes when checks pass (Exit Code 0).
- **Dogfooding Pre-Commit Secret Guard**: Added native `zenzic-guard` hook to `.pre-commit-config.yaml` and updated `.pre-commit-hooks.yaml` to pass `--quiet --no-header` by default for sub-50ms commit-stage validation.

### Performance

- **Sequential Parsing ~3x Speedup**: Eliminated four O(N) redundant passes across the scan pipeline. Baseline on the Zenzic docs corpus (256 files): from ~13 s to ~4.5 s on standard developer hardware.

  | Root cause | Fix | Savings |
  | :--- | :--- | :--- |
  | `CredentialScannerRule` ran `scan_line_for_secrets()` per-line as a rule after `harvest()` had already scanned the same lines via `scan_lines_with_lookback()` | Removed from rule engine; Z201 findings injected directly from `security_findings` | ~829 ms |
  | `directory_policies` compiled `re.compile(translate_glob_to_re2(pattern))` per file × per pattern | Patterns compiled once, cached on the config object as `_compiled_dir_policies` | ~300 ms |
  | `cross_check()` re-opened each file from disk via `_iter_content_lines(file_path)` | New `_iter_content_lines_text(text)` + optional `text` parameter on `cross_check()` | ~302 ms |
  | Four heading rules each did a full `text.splitlines()` + line iteration pass (Z510, Z513, Z516, Z517) | Replaced with `CombinedHeadingRule` — single pass; anchors collected as zero-cost side effect, skipping `anchors_in_file()` in VSM | ~415 ms |

- **Z201 single-pass**: LSP path (`_analyze_file`) now performs the credential scan explicitly via `scan_lines_with_lookback()` — consistent with the CLI path where `harvest()` handles it.
- **`_SECRETS` per-pattern quick prefix**: Added `tuple[str, ...]` of distinctive token prefixes per pattern entry; the credential scanner skips RE2 evaluation when the line does not contain the specific prefix.

### Fixed

- **Z620 false positives** (`directory_policies` tracking): cached compiled patterns now carry the original glob string, restoring correct `GlobalUsageTracker.mark_directory_policy_used(pattern, code)` invocations. Regression introduced in the `_compiled_dir_policies` caching patch.

- **Full Telemetry Disclosure & Unified Progress Telemetry**: Unified all analysis and environment phases (Environment & VSM Init, Parsing, Link Validation, IPC Teardown, Orphans, Snippets, Assets) under a single cohesive Rich `Progress` context, providing uniform determinate progress bars and explicit millisecond timing telemetry across all stages.
- **External URL Exclusion Pre-filtering & Baseline Debt UX**: Added deterministic prefix exclusion filtering in `_check_external_links()` and `LinkValidator.register()`, preventing unwanted HTTP requests for URLs matching `excluded_external_urls` or CLI `--exclude-url`. Refined baseline UX to display an encouraging notification upon massive technical debt resolution (> 50 issues resolved) without new findings.
- **Batched IPC Work Chunking in Hybrid Adaptive Engine**: Partitioned multiprocessing file tasks into dynamically sized chunks (`chunksize = max(4, N // (2 * cpu))`), drastically reducing inter-process serialization overhead and worker queue contention while preserving ADR-020 Parallel Fail-Fast security guarantees on security breach detection.
- **$O(1)$ Navigation Tree Memoization**: Pre-computed navigation paths as an immutable `frozenset[str]` during `MkDocsAdapter` initialization, eliminating over 350,000 redundant recursive dictionary walks and accelerating cross-check topological validation.
- **Single-Pass Fused Lexer & Pre-Masked Buffers**: Refactored `PolyglotExtractor` in `validator.py` to reuse pre-masked text buffers across HTML, reference definitions, and inline Markdown link extractors, eliminating redundant RE2 tokenization and cutting millions of intermediate string allocations.
- **Hybrid Adaptive Engine Multiprocessing Bugfix**: Fixed `workers: int | None = None` default in `scan_docs_references()`, added `RuleFinding.__reduce__()` for safe multiprocessing pickle serialization, and aggregated `consumed_global_patterns` across parallel worker reports into `config._global_tracker`. Restores 7x parallel speedup on workspaces with $\ge 50$ documents.
- **Single-Pass CLI Architecture**: Refactored `_collect_all_results()` to pass precomputed integrity reports directly to `validate_links_structured()`, eliminating redundant second-pass scans and restoring strict $O(N)$ execution.
- **RE2 Configuration Error Trapping**: Added comprehensive regex pattern validation with explicit user diagnostics detailing Google RE2 limitations (prohibiting lookaround assertions `(?=...)` and backreferences `\1`) in `CustomRuleConfig`, `PoliciesConfig`, and `ZenzicConfig`.

### Removed

- **Legacy Custom Rule API v2**: Removed deprecated `BaseASTRule` stub from `src/zenzic/rules/base.py` as scheduled in the v0.30.0 debt eradication milestone. All custom rules must use Custom Rule SDK v3 (`zenzic.sdk.ZenzicRuleV3`).

### Governance

- **Comprehensive Bump Coverage Invariant**: Mandated and registered complete version search/replace coverage across all repository files (`docs/`, `README.md`, `.github/`, `.pre-commit-hooks.yaml`) in `.bumpversion.toml` to guarantee zero-debt release automation.

### Ecosystem

- **VS Code Extension — Zero-Config Auto-Provisioning**: The companion `zenzic-vscode` extension now automatically provisions an isolated Zenzic engine if the CLI is not found on the user's system, using `uv` or `python3 -m venv`. This milestone eliminates the last remaining manual setup friction for new adopters and positions Zenzic as a truly frictionless, "install-and-forget" documentation quality platform.

## Historical Releases

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
