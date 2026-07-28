<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Fixed
- **Extensionless Asset Resolution**: Fixed a bug in `VSMBrokenLinkRule._to_canonical_url` where extensionless files (e.g., `LICENSE`, `Makefile`) incorrectly received a trailing slash when `use_directory_urls` was active, causing false-positive `Z101` findings.

## [0.26.1] - 2026-07-27

### Added

- **Adapter API Contract (`CORE-FIX-005`)**: Added the `use_directory_urls` property to the `BaseAdapter` contract. This allows adapters to explicitly declare their URL routing mode, eradicating encapsulation violations in the incremental engine.

### Fixed
- **URP Unification (`CORE-REFACTOR-003`)**: Eradicated the legacy CLI link validation pipeline (`validate_links_async`). Both CLI and LSP now evaluate broken internal links exclusively via `VSMBrokenLinkRule.check_vsm` and `PolyglotExtractor`, achieving 100% true validation parity.
- **Asset Indexing Parity (`CORE-REFACTOR-006`)**: Upgraded the Virtual Site Map (VSM) builder to explicitly index non-Markdown static assets (e.g., `.png`, `.webp`, `.html`). This eradicates hardcoded directory workarounds and eliminates false-positive `Z101` and `Z104` findings for static assets across all adapters.
- **JSON Purity (`CLI-FIX-001`)**: Enforced absolute JSON purity when the `--json` flag is active by routing `fail_under` and `suppression_cap` failure messages to `stderr`. This prevents `JSON.parse()` failures in programmatic consumers.
- **MkDocs Asset URLs (`CORE-FIX-002`)**: Eradicated false-positive `Z101` findings for static assets in MkDocs repositories by preventing the `MkDocsAdapter` from appending trailing slashes to non-Markdown files during VSM route generation.

### Documentation

- **Blog Hero Image Standardization**: Added named hero assets for existing release posts, converted launch media from JPEG to WebP, and normalized hero-image alt text to a title-aligned editorial pattern across the blog.
- **Editor Trilogy Article**: Added `docs/blog/posts/2026-07-27-editor-trilogy-v0240-v0260.md`, a Hostile Precision architectural synthesis of the v0.24.0 → v0.26.0 editor sequence, using the previously policy-exempt trilogy hero asset as an in-site referenced image.

## [0.26.0] - 2026-07-26

### Added

- **CLI `--json` Shorthand Alias (`ECOSYSTEM-FEAT-002`)**: Added `--json` flag to `zenzic score` as an ergonomic shorthand for `--format json`. Emits a single deterministic `ScoreReport` JSON object on `stdout` without rich terminal formatting, designed for programmatic consumers and editor integrations.

### Documentation

- **CLI Reference Mirror Law Realignment (`ADR-020`)**: Updated `docs/reference/cli.md` with `--json` flag specifications, complete `zenzic score` flag table, and JSON Output Schema documentation.
- **Roadmap Realignment (`ROADMAP-ALIGN-004`)**: Realigned `ROADMAP.md` to establish `[v0.26]` as *DQS Workspace UI*, shifting subsequent platform milestones (`v0.27`–`v0.30`).

## Historical Releases

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
