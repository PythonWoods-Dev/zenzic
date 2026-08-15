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

### Added

- **Semantic Linting & Accessibility Rules (Epic 2)**: Implemented 5 native AST-based semantic and accessibility (a11y) rules in `zenzic.core`:
  - `Z513` (`DUPLICATE_HEADING`): Detects duplicate headings within the same document (case/whitespace/anchor invariant), preventing ambiguous anchor collisions. Penalty: 2.0 pts (Content).
  - `Z514` (`GENERIC_IMAGE_ALT_TEXT`): Detects generic filler words in image alt text (`![]()` and `<img>`), enforcing accessibility standards. Penalty: 2.0 pts (Content).
  - `Z515` (`BARE_URL_USED`): Detects raw HTTP/HTTPS URLs in prose that are not enclosed in angle brackets or Markdown links. Supports automated fix (`zenzic fix --apply`). Penalty: 1.0 pt (Content).
  - `Z516` (`MULTIPLE_H1_HEADINGS`): Enforces a single top-level `#` or `<h1>` heading per document for structural hierarchy. Severity: `error`, Penalty: 5.0 pts (Content).
  - `Z517` (`HEADING_PUNCTUATION`): Detects invalid trailing punctuation (`.`, `:`, `;`) on headings. Supports automated fix (`zenzic fix --apply`). Penalty: 1.0 pt (Content).
- **AST Mutator Extensions**: Added `BareUrlMutation` and `HeadingPunctuationMutation` to the core AST `Mutator` engine, enabling atomic auto-remediation via `zenzic fix`.
- **Ecosystem & Mirror Law Integration**: Added dedicated rule cards `docs/rules/Z513.md` through `docs/rules/Z517.md`, registered codes in `CODE_DEFINITIONS` and SARIF export metadata, and added interactive scenarios in `zenzic lab` (`z513`–`z517`).

### Removed

- **Legacy Custom Rule API v2**: Removed deprecated `BaseASTRule` stub from `src/zenzic/rules/base.py` as scheduled in the v0.30.0 debt eradication milestone. All custom rules must use Custom Rule SDK v3 (`zenzic.sdk.ZenzicRuleV3`).

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
