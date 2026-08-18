<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD041 -->

## Description
<!-- Describe the architectural intent of the changes and provide context. -->
Fixes #

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature breaking backward compatibility)
- [ ] Documentation / D.I.A. update
- [ ] Refactoring / Tech Debt removal
- [ ] Performance optimization

## Governance & Compliance Checklist

- [ ] **DCO & Signatures:** All commits are signed with DCO (`git commit -s`) and GPG/SSH (`git commit -S`).
- [ ] **Issue-First:** This PR addresses an explicitly approved Issue.
- [ ] **Changelog:** I have updated `CHANGELOG.md` under the `## [Unreleased]` section.
- [ ] **Commit Standards:** Commit messages strictly follow the Conventional Commits specification.
- [ ] **Absolute Ownership:** I have verified and can architecturally justify every single line of code. No unreviewed AI-generated code is included.

## Architectural Quality Gates (Core Python)

- [ ] **Mirror Law:** I have updated the finding codes catalog, scoring matrices, rule cards, and reference documentation if adding or modifying a rule.
- [ ] **Local Quality Pipeline:** `just verify` (or `pytest tests/` + `zenzic check all --strict`) passes with 100% test pass rate and no DQS regression.
- [ ] **Zero Subprocess & Determinism:** No unauthorized subprocess executions, shell wrappers, or non-deterministic file I/O are introduced into the core analysis engine.
- [ ] **Custom Rule SDK v3:** If modifying the SDK or rule extensions, changes maintain backward compatibility with `ZenzicRuleV3`.
