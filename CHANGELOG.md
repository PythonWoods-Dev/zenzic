<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to Zenzic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

Upcoming changes for the next release.

### Changed (Breaking)

- **Taxonomic Refactoring (Z118 → Z620)**: Renamed finding code `Z118` (`STALE_GLOBAL_SUPPRESSION`) to `Z620` to align its identifier with its semantic DQS category (Governance & Brand, Z6xx namespace). This is a **breaking change** for users with `ignore = ["Z118"]` in `.zenzic.toml` or Z118-based SARIF/JSON parsers. Update all references from `Z118` to `Z620`.

### Added

- **Policy-as-Code Link & Topology Governance (`Z614`, `Z615`, `Z616`)**: Introduced Zero-Trust external domain whitelist (`Z614: UNAPPROVED_DOMAIN_REFERENCE`), URL scheme whitelist enforcement (`Z615: FORBIDDEN_URL_SCHEME`), and Virtual Site Map (VSM) cross-namespace boundary control (`Z616: CROSS_NAMESPACE_LINK_FORBIDDEN`) under `[policies]` in `.zenzic.toml`.
- **Policy-as-Code Metadata Governance (`Z612`, `Z613`)**: Introduced `Z612` (`FORBIDDEN_FRONTMATTER_KEY`) and `Z613` (`FRONTMATTER_SCHEMA_MISMATCH`) into the Policy-as-Code engine (`[policies]` configuration in `.zenzic.toml`), allowing project maintainers to forbid specific frontmatter keys and enforce RE2 regex schemas on frontmatter values.
- **Ecosystem Dependency Strategy & DQS Integrity Rules**: Codified Governance Rules 10 & 11 in `.gemini/governance/rules` enforcing strict pinning (`==`) for `zenzic-action`, minimum versioning (`>=`) for `zenzic-vscode`, and 100% mathematical category-to-escalation parity in `scorer.py`.
- **8-Step Finding Code Protocol**: Enriched developer guidelines in `docs/developers/how-to/write-a-check.md` with the mandatory 8-step protocol for adding or modifying diagnostic codes across the core engine, scoring algorithms, and documentation surfaces.

### Fixed

- **DQS Governance Escalation Parity (`Z620`)**: Included `Z620` (`STALE_GLOBAL_SUPPRESSION`) in `_Z6XX_CODES` in `src/zenzic/core/scorer.py`, eliminating a mathematical inconsistency where stale global suppressions were omitted from exponential penalty amplification.
- **Documentation & Mirror Law Parity**: Synchronized DQS category weights, penalty tables, and finding catalogs across `docs/reference/scoring-algorithm.md`, `docs/explanation/scoring-system.md`, and `docs/reference/finding-codes.md`.

## Historical Releases

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
