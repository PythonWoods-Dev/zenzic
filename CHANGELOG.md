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

## [0.28.0] - 2026-08-11

### Added

- **Policy-as-Code Engine (`V0.28-01`)**: Introduced foundational architecture for declarative governance policies via a new `[policies]` table in `.zenzic.toml`. Policies are **opt-in** and fully backward-compatible. When the `[policies]` section is absent or empty, zero behaviour change is observed.
  - `Z610` (REQUIRED_FRONTMATTER_MISSING): Emitted when a Markdown file is missing a frontmatter key declared in `[policies].required_frontmatter_keys`. One finding is emitted per missing key per file. Penalty: 3.0 pts (Governance).
  - `Z611` (FORBIDDEN_DOMAIN_REFERENCE): Emitted when a link — native Markdown `[text](url)` or raw HTML `<a href>` — references an external domain listed in `[policies].forbidden_external_domains`. Domain matching is case-insensitive and covers exact domains and all subdomains. Penalty: 3.0 pts (Governance).
  - `PolicyEvaluator` class in `zenzic.core.governance`: stateless, deterministic, pure-function evaluator. No I/O, no subprocess, no cross-file state (**ADR-075 Radical Unawareness**).
  - `PoliciesConfig` Pydantic model in `zenzic.models.config` with full Zero-DBT documentation. Schema mismatches automatically emit `Z111` via the existing Configuration Validation Engine.
- **Custom Rule SDK v3 (`V0.28-02`)**: Evolved the custom rules framework into a stable, typed SDK (`zenzic.sdk`).
  - `ZenzicRuleV3`: Public base class for custom rules with visitor hooks (`visit_document`, `visit_line`, `visit_link`, `visit_heading`, `visit_code_block`).
  - `RuleMetadata`: Typed Pydantic model enforcing `code`, `title`, `description`, `severity`, `category`, and `penalty` for custom rules.
  - **Hard Deprecation of v2 API**: Removed legacy `BaseASTRule` v2 API. Instantiating or attempting to load v2 rules raises `PluginContractError` fast.
- **SARIF Enterprise Integration (`V0.28-03`)**: Elevated SARIF 2.1.0 output to enterprise-grade compliance status for GitHub Code Scanning.
  - Enriched `runs[0].tool.driver.rules` with `helpUri`, `properties.category`, `properties.penalty`, and `fullDescription` derived dynamically from `CODE_DEFINITIONS` and Custom Rule SDK v3 `RuleMetadata`.
  - Enforced 100% deterministic result and rule sorting order (`(rel_path, line_no, code, message)`).
- **Zenzic Audit Mode (`V0.28-04`)**: Introduced `zenzic audit` CLI command under the Governance panel for generating formal compliance audit reports.
  - Aggregates Executive Summary (workspace coverage, DQS score, pass/fail status), Governance Policies (`[policies]` compliance), Technical Debt Ledger (inline comments, per-file ignores, directory policies), and Architectural State (active build engine, adapter class, custom SDK v3 rules).
  - Supports rich terminal output (`--format text`) and 100% deterministic machine-readable JSON (`--format json`).
- **Mirror Law Parity (`ADR-020`)**: Authored rule specification cards `docs/rules/Z610.md` and `docs/rules/Z611.md`. Registered both codes in `docs/reference/finding-codes.md` and `mkdocs.yml` navigation tree.
- **CHANGELOG Archive**: Moved `v0.27.x` release notes to `changelogs/v0.27.x.md` and reset `CHANGELOG.md` for the `v0.28.x` development cycle.

### Fixed

- **Path Sovereignty Guard (`Z202`)**: Enforced strict Path Sovereignty boundary checks in `walk_files` (`src/zenzic/core/discovery.py`) using `path.resolve(strict=False).is_relative_to(resolved_repo_root)`. Symlinks resolving outside the workspace root boundary are safely skipped with a `Z202 Path Traversal` warning. Legitimate internal symlinks inside the workspace root are preserved and scanned normally.
- **AST Line-Offset Determinism**: Updated `_mask_comments` in `PolyglotExtractor` (`src/zenzic/core/validator.py`) to replace non-newline characters in HTML/MDX comments with spaces while retaining `\n` linebreaks. Prevents line collapse in multiline comments and preserves exact line offsets in AST link diagnostics.

### Changed

- **Brand & Positioning Alignment (`V0.27-13`)**: Realigned product positioning across package descriptions (`pyproject.toml`), READMEs, documentation, landing page components, and social assets to accurately reflect Zenzic as a **Deterministic Document Integrity Engine**. Eradicated misleading "SAST" terminology from all user-facing surfaces (**Mirror Law ADR-020**).

## Historical Releases

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
