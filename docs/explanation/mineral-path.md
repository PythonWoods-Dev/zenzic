---
sidebar_position: 8
sidebar_label: "Release Codenames"
description: "Mapping of Zenzic SemVer versions to their official release codenames and engineering focus areas."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Release Codenames

Each Zenzic release cycle is assigned a codename derived from a geological mineral.
Codenames are always in English, are never translated, and serve as stable architectural
bookmarks in documentation, changelogs, and migration guides.

## Codename Registry

| Version | Codename | Key Properties | Engineering Focus |
|---------|----------|----------------|-------------------|
| **v0.6.x** | **Obsidian** | Volcanic glass — formed under extreme pressure, exceptionally sharp edge | Credential scanner (Z2xx), path traversal guard, first SARIF output, Exclusion Zone model |
| **v0.7.x** | **Quartz** | Piezoelectric — precise, self-oscillating, frequency standard | Finding codes (`Zxxx`), exit code contract, Virtual Site Map, SARIF platform compatibility |
| **v0.8.x** | **Basalt** | Dense volcanic rock — high-tensile structural reinforcement | Plugin SDK, adapter protocol stabilisation, performance at scale |
| **v0.9.x** | **Graphite** | Highly conductive — enables current between systems | Third-party integrations, public API, ecosystem expansion |
| **v0.10.x** | **Magnetite** | Naturally magnetic — aligns with external fields | Native CI/CD integration, Progressive Adoption, Async Network I/O |
| **v1.0.0** | **Diamond** | Hardest natural material — maximum structural integrity | Long-Term Support, stability guarantees, full API maturity |
| **v1.1.x** | **Corundum** | Hardness 9 — highly resistant to abrasion | Advanced rule customization, ecosystem hardening |
| **v1.2.x** | **Beryl** | Hexagonal crystal — structural purity | AST parsing optimization, memory footprint reduction |

## Usage Convention

Codenames appear in:

- `CHANGELOG.md` section headings (e.g., `## [0.8.0] — Basalt`)
- `RELEASE.md` and `CITATION.cff` `version-note` fields
- Migration guides and breaking-change announcements

Codenames **do not** appear in:

- Tutorial or how-to guide text (use agnostic prose)
- Error messages or CLI output (use the version number instead)
- Translations (codenames are proper nouns — always written in English)

If you want to contribute to a specific milestone, the Engineering Ledger *(Maintainer Only)* contains the active
sprint context and architectural decisions in progress.


## See Also

- [Migrating Engines](../how-to/migrate-engines.md)
