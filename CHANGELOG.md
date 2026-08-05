<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [0.27.2] - 2026-08-05

### Added
- **Environment Diagnostics CLI (`zenzic env`)**: Added a transport-agnostic CLI command (`zenzic env` and `zenzic env --json`) that outputs core runtime diagnostics (Zenzic version, Python executable path, Zenzic module path, working directory, and active configuration file path) to streamline debugging path resolution issues without coupling to specific editors or LSP clients (**ADR-075 Radical Unawareness**).

### Fixed
- **LSP Event Coalescing & Uniform Debouncing**: Applied a uniform 300ms debounce buffer to watched file notifications (`workspace/didChangeWatchedFiles`). Directory events now flag pending full syncs rather than executing synchronous rebuilds, eliminating $O(M \cdot N)$ redundant AST parses, execution latency, and memory spikes during bulk directory copies.
- **Ghost Diagnostics Fix & Directory Eviction**: Implemented atomic cache pruning in `IncrementalAnalysisEngine.process_changes()` and directory-level buffer/document eviction in `LanguageServer._handle_file_changes()`. Deleting a directory now automatically evicts all contained child buffers from `overlay.buffers` and broadcasts `[]` empty diagnostic arrays to immediately clear the editor's PROBLEMS panel (**LSP-FIX-017 State Hygiene**).
- **LSP Server Version Reporting**: Replaced static `"0.21.0"` string in LSP `initialize` response with dynamic `__version__` from `zenzic`.

## [0.27.1] - 2026-08-05

### Fixed

- **LSP Execution Parity**: Restored real-time diagnostic emission for `Z110` and `Z111` by enabling in-memory buffer validation for `.zenzic.toml` and `pyproject.toml` via `content_override`.
- **Topological Delta Optimization**: `IncrementalAnalysisEngine` now computes graph changes using XOR set operations (`old_orphans ^ new_orphans`), ensuring `Z410` and `Z411` diagnostics are updated in strictly $O(K)$ time during hot-reload.
- **Dogfooding & Documentation**: Fixed internal `Z503` syntax errors in rule documentation and integrated all `v0.27.0` rule cards into the `mkdocs.yml` navigation tree to resolve `Z402` false positives.

## [0.27.0] - 2026-08-02

### Added

- **Smart Link Graph (`V0.27-01`)**: Transformed the Virtual Site Map (VSM) into a Smart Link Graph that tracks deterministic adjacency lists for outgoing links across document nodes.
- **Configuration Validation Engine (`V0.27-04`)**: Introduced formal validation for `.zenzic.toml` with graceful degradation and non-suppressible diagnostic findings:
  - `Z110` (CONFIG_SYNTAX_ERROR): Emitted on TOML syntax errors (`TOMLDecodeError`) with line-number extraction.
  - `Z111` (CONFIG_SCHEMA_ERROR): Emitted on schema type mismatches and validation failures (`ValidationError`).
  - Halts Markdown document graph scanning on fatal config errors to prevent false-positive cascades and protect LSP stability.
- **Baseline & Regression Tracking (`V0.27-02`)**: Added deterministic snapshot baseline capability (`.zenzic-baseline.json`) via `--update-baseline` and `--baseline` CLI options. Computes line-shift invariant SHA-256 signatures for finding matching, tags baselined findings without dropping them (`Radical Unawareness`), and enforces DQS anti-regression exit rules in CI/CD.
- **Mirror Law Parity (`ADR-020`)**: Authored 41 dedicated, deep-dive Rule Specification Cards (`docs/rules/ZXXX.md`) and updated `docs/reference/finding-codes.md` to achieve 100% Mirror Law documentation parity. Each card provides technical rationale, Bad/Good Markdown examples, and `.zenzic.toml` configuration options.
- **Topological Connectivity Restoration**: Resolved `Z411` dead-end node findings across active documentation namespaces by injecting semantic `## See Also` navigation links within the AST graph.

### Fixed

- **Readability Sentence Boundary Parser (`Z511`)**: Fixed sentence length calculation in `zenzic.core.content` by recognizing bulleted lists, numbered items, and blockquotes as hard sentence boundaries, eliminating false-positive readability warnings on long lists.
- **CLI Flag Input Validation**: Enforced strict input validation for the `--only` CLI option in `zenzic check`, triggering an immediate fatal exit (`Exit 1`) when an invalid or unknown finding code is supplied.
- **Topological Directory-Policy Tracking (`Z118`)**: Fixed a Core Engine governance bug where topological suppressions (`Z410`/`Z411`) could leave false-positive dead-policy findings by ensuring canonical tracker rebinding in scanner passes and paired topology policy consumption in `GlobalUsageTracker`.

### Changed

- **Zero-DBT Technical Debt Cleanup**: Reverted unauthorized configuration suppressions in `.zenzic.toml`, structurally resolved 48 empty section (`Z512`) findings across 35 Markdown files, and eliminated stale global suppressions (`Z118`).

## Historical Releases

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
