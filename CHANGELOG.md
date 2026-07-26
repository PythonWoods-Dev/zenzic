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

- **CLI `--json` Shorthand Alias (`ECOSYSTEM-FEAT-002`)**: Added `--json` flag to `zenzic score` as an ergonomic shorthand for `--format json`. Emits a single deterministic `ScoreReport` JSON object on `stdout` without rich terminal formatting, designed for programmatic consumers and editor integrations.

### Documentation

- **CLI Reference Mirror Law Realignment (`ADR-020`)**: Updated `docs/reference/cli.md` with `--json` flag specifications, complete `zenzic score` flag table, and JSON Output Schema documentation.
- **Roadmap Realignment (`ROADMAP-ALIGN-004`)**: Realigned `ROADMAP.md` to establish `[v0.26]` as *DQS Workspace UI*, shifting subsequent platform milestones (`v0.27`–`v0.30`).

## [0.25.4] - 2026-07-26

### Fixed

- **LSP DQS Determinism & Severity Parity (`LSP-FIX-014`)**: Deprecated misleading DQS Status Bar notification emission in `server.py` to preserve the Determinism invariant between incremental LSP mode (which observes topological findings only) and CLI batch mode. Filtered `INFO`-level findings (e.g. Z106) at the transport boundary in `incremental.py` to prevent PROBLEMS panel pollution.

## [0.25.3] - 2026-07-26

### Added

- **AST Reference Link Definition Extraction (`CORE-FIX-001`)**: Upgraded `PolyglotExtractor` to natively extract Markdown Reference Link Definitions (`[label]: dest`) with CommonMark §4.7 first-definition-wins semantics and full code fence masking (`_mask_fences`), eliminating false-positive `Z405` (Unused Asset) findings.
- **Zensical Framework Feature Parity (`ADAPTER-002`/`ADAPTER-003`)**: Upgraded `ZensicalAdapter` with preserved static asset URL mapping, route classification for root/directory index pages (`index.md`) and dynamic blog routes (`<blog_dir>/posts/`), and theme asset metadata extraction (`favicon`, `logo`, `extra_css`, `extra_javascript`).

## [0.25.2] - 2026-07-26

### Fixed

- **Path Traversal Security Parity (`LSP-FIX-012`)**: Hardened `Z202`/`Z203` path traversal evaluation in `IncrementalAnalysisEngine._run_urp_checks()` by replacing absolute OS filesystem depth checks (`len(path.parents)`) with `docs_root`-boundary escape detection (`os.path.normpath` + `is_relative_to(resolved_docs_root)`). This guarantees 100% security parity between CLI and LSP mode.

## [0.25.1] - 2026-07-26

### Added

- **Adapter-Level `material/blog` Plugin Recognition (`LSP-FIX-011`)**: Extended `MkDocsAdapter` to automatically detect the `material/blog` plugin and classify all posts under `<blog_dir>/posts/` as `REACHABLE` routes in the Virtual Site Map (VSM).
- **Directory Nav Path Resolution (`LSP-FIX-011`)**: Updated `MkDocsAdapter.get_nav_paths()` to expand trailing-slash directory entries (e.g. `blog/`) to their implicit `index.md` target (`blog/index.md`), eliminating false-positive `Z402` (Unlisted Page) findings for plugin index pages.

### Fixed

- **Inline HTML Suppression LSP Parity (`LSP-FIX-011`)**: Updated `IncrementalAnalysisEngine._run_urp_checks()` to pass the active `SuppressionTracker` when evaluating Polyglot Extractor nodes. Suppressed HTML elements (`data-zenzic-ignore`) are now correctly marked as consumed, eliminating spurious `Z603` (Dead Suppression) warnings in editor sessions.

## [0.25.0] - 2026-07-25

### Added

- **Adapter-Driven Config Hot-Reloading (`LSP-FIX-009`)**: Added `@property watched_config_files` to `BaseAdapter` contract. The LSP server now dynamically watches framework configuration files (e.g. `mkdocs.yml`, `zensical.toml`) and hot-reloads the Virtual Site Map (VSM) on changes without requiring an LSP server restart.
- **Consolidated Developer & User Troubleshooting (`DOCS-IA-004`)**: Created dedicated Diátaxis-compliant troubleshooting guides in `docs/how-to/troubleshooting.md` and `docs/developers/how-to/troubleshooting.md`.

### Fixed

- **Centralized Core Governance (`LSP-FIX-009`)**: Extracted `directory_policies` and `per_file_ignores` filtering into `zenzic.core.governance` and integrated them directly into `IncrementalAnalysisEngine._analyze_file`, achieving 100% diagnostic determinism between CLI and VS Code.

## [0.24.5] - 2026-07-25

### Fixed

- **Exclusion Path Normalization (`LSP-FIX-008`)**: Hardened the `LayeredExclusionManager` to correctly normalize absolute URIs from the LSP server into repo-relative paths before evaluating `.gitignore` and `.zenzic.toml` exclusion rules. This eradicates false-positive diagnostics on user-excluded directories (e.g., `docs/tutorials/examples`) when opened in VS Code.

## [0.24.4] - 2026-07-24

### Fixed

- **LSP User Exclusion Enforcement (`LSP-FIX-007`)**: Strictly enforced `LayeredExclusionManager` filtering across full workspace sync and incremental file events in the LSP server and `IncrementalAnalysisEngine`, eliminating false-positive diagnostics on user-excluded directories (e.g. `excluded_dirs`).

## [0.24.3] - 2026-07-24

### Fixed

- **Windows Path Parity (CLI & Core)**: Fixed test suite regressions on Windows by ensuring strictly POSIX path comparisons (`.as_posix()`) in CLI JSON report rendering (`_shared.py`) and topological graph traversal (`cycle_registry`).
- **LSP `docs_root` Fallback**: Centralized `docs_root` resolution in the LSP server to safely fall back to the repository root when the configured `docs/` directory is missing, fixing a silent failure (DQS 100/100) on Zero-Config repositories.
- **Zero-Config System Guardrails**: Elevated common build directories (`out`, `.vscode-test`) to Layer 1 `SYSTEM_EXCLUDED_DIRS` to ensure safety across VS Code extension codebases regardless of `.gitignore` state.
- **LSP Memory Leak**: Implemented missing `didClose` handler to explicitly purge documents from `VirtualBufferOverlay`, avoiding unbounded memory growth during long-lived VS Code sessions.
- **LSP Windows URI Parity**: Replaced naive string slicing with robust `urllib.request.url2pathname` for cross-platform deterministic parsing of `file://` URIs, preventing drive-letter corruption on Windows.

## [0.24.2] - 2026-07-24

### Fixed

- **LSP Layered Exclusion & Asset Resolution (`LSP-FIX-002`)**: Enforced `LayeredExclusionManager` filtering in `LanguageServer._is_within_domain()` and `_build_vsm_sync()` so configured `excluded_dirs` are respected in editor sessions. Registered static HTML and media assets in VSM during initialization to eliminate false-positive `Z101` broken link errors on asset references.
- **LSP Workspace Initialization Sync (`LSP-FIX-003`)**: Added initial workspace analysis and `zenzic/dqsUpdate` JSON-RPC broadcast upon receiving the `initialized` notification, ensuring editor DQS widgets reflect repository quality state prior to explicit `textDocument/didOpen` events.

## [0.24.1] - 2026-07-24

### Fixed

- **URI Normalization & Link Resolution (`LSP-FIX-001`)**: Resolved false-positive `Z101` findings in LSP mode by extending `VSMBrokenLinkRule._to_canonical_url` to resolve all relative links (without `".."` requirement) relative to `source_dir`, and adding `urllib.parse.unquote()` percent-decoding to `file://` URIs.

### Added

- **Release Announcement Blog Post (`DOCS-BLOG-001`)**: Added official Zenzic v0.24.0 (*Interactive Intelligence*) release announcement blog post.

## [0.24.0] - 2026-07-24

### Added

- **LSP Code Actions Support (`LSP-FEAT-001-CODE-ACTIONS`)**: Enabled `codeActionProvider` in ZLS server capabilities and implemented `textDocument/codeAction` to expose in-memory Quick Fixes for fixable Z-Codes (e.g. `Z121`, `Z603`).
- **LSP DQS Real-Time Notification (`LSP-FEAT-002-DQS-UI`)**: Added custom `zenzic/dqsUpdate` JSON-RPC notification channel to stream global DQS scores and penalties to editor clients.

### Changed

- **Governance Alignment (`GOVERNANCE-001-DUAL-TIER-ALIGNMENT`)**: Synchronized internal prompt table (`0. Priority Table.md`) with public `ROADMAP.md` and added state tracking.

## Historical Releases

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
