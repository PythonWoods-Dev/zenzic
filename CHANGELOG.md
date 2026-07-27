<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [0.26.1] - 2026-07-27

### Added

- **Adapter API Contract (`CORE-FIX-005`)**: Added the `use_directory_urls` property to the `BaseAdapter` contract. This allows adapters to explicitly declare their URL routing mode, eradicating encapsulation violations in the incremental engine.

### Fixed

- **VSM URL Route Parity (`CORE-FIX-003`)**: Updated `VSMBrokenLinkRule._to_canonical_url()` to preserve asset file routes across query/fragment links and to respect flat URL mode (`use_directory_urls=False`) for `.html`/`.htm` targets.

- **MkDocs Static Asset Route Parity (`CORE-FIX-002`)**: Hardened `MkDocsAdapter._map_url()` to preserve exact canonical paths for non-document assets (`.jpg`, `.png`, `.css`, etc.) by bypassing `use_directory_urls` for files whose suffix is outside `DOC_SUFFIXES`. This eliminates false-positive `Z101` findings for linked static assets in MkDocs repositories.
- **Score JSON Purity (`CLI-FIX-001`)**: Routed `fail_under` and suppression-cap failure diagnostics to `stderr` when `zenzic score --json` is active, preserving a pure JSON payload on `stdout` for programmatic consumers such as the VS Code CLI bridge.

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
