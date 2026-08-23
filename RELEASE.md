<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Release Procedure — Zenzic Core

> **[MAINTAINER SOP]** *This document contains the Standard Operating Procedure for Core Maintainers to cut and publish a new release. If you are an end-user looking for new features, please see the [CHANGELOG](./CHANGELOG.md).*

## Release Metadata

| Field    | Value      |
| :------- | :--------- |
| Version  | v0.30.0     |
| Codename | Magnetite   |
| Date     | 2026-08-15 |
| Status   | Stable |

## v0.30.0 — Epic Summary

This release concludes **Epic 2: Semantic Linting Supremacy**, the second major quality pillar of the Zenzic engine, and delivers a complete performance, design-system, and accessibility overhaul of the documentation site.

### Core Engine — Semantic Linting (Epic 2)

| Feature | Finding Codes | Description |
| :--- | :--- | :--- |
| **Semantic Linting & A11y** | `Z513–Z517` | Duplicate headings, excessive sentence length, empty sections, generic alt text, bare URLs |
| **Editorial Style & Policy-as-Code** | `Z518–Z519`, `Z617–Z619` | Passive voice detection, weasel words (opt-in), forbidden content patterns, required heading patterns, max document complexity |
| **Semantic List Heuristics** | `Z520` | Malformed list detection with deterministic AST heuristics |

### Performance — Extreme Speed Optimizations

- **O(1) Navigation Memoization**: Navigation graph is computed once and cached; subsequent topology queries are `O(1)` dictionary lookups.
- **Batched IPC**: Inter-process communication between LSP server and Core engine is batched to eliminate per-finding round-trips.
- **Fused Lexer**: Token scanning and rule matching fused into a single O(n) pass, eliminating redundant AST walks.

### Documentation Site — Design System & Accessibility

- **Engineered Frame Image System** (`extra.css`): Standard images receive `border-radius`, multi-layer `box-shadow`, and hover lift with brand glow. Cover images use `.hero-cover` with elevated glow treatment.
- **WCAG 2.1 AA Contrast Fixes**: Tailwind classes `text-zinc-400/500`, `text-rose-400`, `text-amber-400/500` overridden via `extra.css` using calibrated `--zz-*` semantic tokens. All contrast ratios now ≥ 4.5:1 (AA).
- **PageSpeed Optimization** (`V030_FRONTEND_PERFORMANCE_OPTIMIZATION`): KaTeX loaded on-demand only on pages containing `.arithmatex` elements, with SHA-384 Subresource Integrity (SRI) hashes and `crossorigin="anonymous"`. Homepage transfers 0 bytes of KaTeX.
- **Technical SEO & Sitemap Hygiene** (`V0.30-14-SEO-REDIRECT-HYGIENE`): Removed obsolete `scoring-design.md`, excluded `includes/*` from sitemap, corrected broken 301 redirect.

## Release Checklist

Before tagging, every item must be green:

- [ ] `just verify` — exits 0 (pre-commit hooks → pytest → `zenzic score --stamp` → badge freshness → `zenzic check all --strict`)
- [ ] `zenzic lab all` — all gallery scenarios exit with expected code (`zenzic lab all` now exits non-zero if any scenario fails, so this check is enforceable in CI, not just visual — see CHANGELOG.md)
- [ ] `zenzic score --stamp` committed — badge in README.md reflects current score
- [ ] `zenzic check all .` — zero findings in the repo root
- [ ] `pyproject.toml` version matches the tag (`0.30.0`)
- [ ] `CITATION.cff` version and date updated
- [ ] `CHANGELOG.md` — `[Unreleased]` section moved to the new version heading
- [ ] Update SECURITY.md support table (Add new release, demote previous to Critical/EOL).
- [ ] `zenzic-doc` and `zenzic-action` RELEASE.md updated to match this version
- [ ] Verification of `zenzic init` atomic protection (`EXIT 1` on existing config)
- [ ] Verification of `zenzic init` template didactic comments and Z601 empty baseline

## Build & Distribute

```bash
# Bump version
uv run bump-my-version bump patch

# Build wheel + sdist
python -m build

# Publish to PyPI
uv publish
```

Distribution target: **PyPI** — `pip install zenzic` / `uvx zenzic`.

## Tag & Push

```bash
# 1. Merge the release branch into main via PR first!
# 2. Switch to main and pull latest
git checkout main
git pull origin main

# 3. Tag the main branch and push
git tag -s -m "Release v0.30.0" v0.30.0
git push origin main --tags

```

- [ ] Create GitHub Release from the tag, using the `## [0.30.0]` CHANGELOG section as the release body.

## Changelog Reference

For a detailed list of changes, see [CHANGELOG.md](./CHANGELOG.md).
For full history, see [Historical Archives](./changelogs/README.md).
