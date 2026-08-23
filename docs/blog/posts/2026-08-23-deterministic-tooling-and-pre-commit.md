---
title: "Deterministic Tooling & The Pre-Commit Distribution Model"
slug: deterministic-tooling-and-pre-commit
date: 2026-08-23
authors:
  - pythonwoods
description: >
  Why global tool installation fails in professional documentation engineering,
  and how Zenzic's canonical 3-track distribution hierarchy guarantees zero environment
  contamination, lockfile reproducibility, and sub-50ms local verification.
categories:
  - Architecture
  - Best Practices
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

> **Global tools create global collisions. Pinned environments guarantee deterministic quality.**

If your documentation quality tool is installed globally on each engineer's machine — `pip install --user`, `brew install`, or a bare `uv tool install` — you don't actually have a quality gate. You have a suggestion that happens to run on whichever version each person installed, whenever they last remembered to update it.

In documentation engineering, static analysis tools are frequently recommended as global system binaries. While convenient for an initial 10-second evaluation, floating global installations create severe architectural liabilities when scaling across engineering teams and CI pipelines.

With Zenzic v0.31.0, we formalize our **Canonical 3-Track Distribution Hierarchy**: prioritizing isolated pre-commit hooks and project-locked dependencies over floating global binaries.

<!-- more -->

---

## The Root Cause: Why Floating Tools Break Quality Gates

Modern documentation sites are not just folders of static text; they are sophisticated static applications with complex dependency trees (`pydantic`, `google-re2`, `mkdocs`, `material`).

When team members execute linters installed globally:
1. **Dependency Hell & Version Drift**: Developer A runs an outdated binary with older regex rules, while Developer B runs a cutting-edge version that flags newly introduced Policy-as-Code violations.
2. **Environment Contamination**: Shared Python environments suffer from library version collisions (e.g., conflicting Pydantic v1 vs v2 dependencies between linters and build tools).
3. **CI/CD Asymmetry**: Local builds succeed on developer laptops but fail remotely in GitHub Actions due to differing CLI versions and baseline signatures.

---

## The Canonical 3-Track Hierarchy

To resolve these failure modes, Zenzic defines three distinct distribution tracks in order of operational priority:

```text
  ┌────────────────────────────────────────────────────────────────────────┐
  │  Track 1: Pre-commit (Recommended)  ──> Isolated, Pinned, Zero-Drift   │
  │  Track 2: Project Dependency        ──> Docs-as-Code, uv/pip lockfile │
  │  Track 3: Global / Ephemeral         ──> One-Off Audits, Non-Python   │
  └────────────────────────────────────────────────────────────────────────┘
```

---

### Track 1: Pre-Commit Hooks (Recommended)

Pre-commit provides complete virtual environment isolation. The `pre-commit` framework creates and manages a dedicated, isolated sandbox for Zenzic, ensuring zero interference with your project's runtime dependencies while pinning the exact version tag.

<!-- Publication gate: do not publish before the v0.31.0 tag exists on GitHub. -->

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      # Sub-50ms secret and forbidden pattern check on staged files
      - id: zenzic-guard

      # Optional: full repository graph audit during pre-push
      # - id: zenzic-verify
      #   stages: [pre-push]
```

#### Dogfooding: We Run Track 1 on Ourselves

We do not merely recommend Track 1 to users; **Zenzic dogfoods this exact pre-commit architecture internally**. In our own repository's `.pre-commit-config.yaml`, the `zenzic-guard` hook executes on every commit to block leaked API credentials and path traversal before any git commit is recorded, while `just-verify` orchestrates the full graph audit on `pre-push`.

---

### Track 2: Project Dependency (Docs-as-Code)

For Python repositories maintaining a unified toolchain (`uv`, `poetry`, `pdm`, or `pip-tools`), declaring Zenzic as a development dependency binds its lifecycle to your project lockfile:

```toml title="pyproject.toml"
[project.optional-dependencies]
docs = [
    "zenzic>=0.31,<0.32",
]
```

Using compatible-release ranges (`>=0.31,<0.32`) allows minor patch updates while preventing breaking API changes. 

**Key Benefits of Track 2:**
- **Lockfile Reproducibility**: `uv sync` ensures every engineer and CI runner uses bit-exact bytecode.
- **VS Code Extension Auto-Discovery**: The Zenzic VS Code Extension automatically locates the virtualenv binary (`.venv/bin/zenzic`) without requiring manual path configuration.

---

### Track 3: Global & Ephemeral Execution (One-Off Audits)

Track 3 is demoted from default status but remains essential for specific scenarios:

```bash title="Ephemeral Execution via uvx"
# Audit any repository instantly without installing dependencies
uvx zenzic@0.30.0 check all
```

As with `rev:` in Track 1, pin `uvx zenzic@X.Y.Z` to a specific tagged release rather than leaving it unpinned or copy-pasting an old version indefinitely.

Track 3 is ideal for:
- One-off security audits of unfamiliar repositories.
- Non-Python projects (Node.js, Go, Rust) that do not use `pre-commit`.
- Ad-hoc debugging of documentation graph topology.

---

## Conclusion: Determinism Starts at the Commit Boundary

Quality gates must be deterministic, isolated, and frictionless. By shifting quality enforcement to pinned pre-commit hooks and lockfile-managed dependencies, teams eliminate "works on my machine" friction and ensure their documentation graphs remain mathematically verifiable from the first commit to production deployment.

For the specification-level failure modes this distribution model exists to guard against — missing table columns, invalid cell values, scrambled heading order, and broken traceability — see [Zenzic v0.31.0: Specification-Driven Development & AI Knowledge Graph Integrity](2026-08-22-zenzic-v0310-specification-driven-development.md).
