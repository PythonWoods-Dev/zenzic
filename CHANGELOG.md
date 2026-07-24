<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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
