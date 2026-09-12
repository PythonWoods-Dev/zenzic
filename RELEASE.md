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

- [ ] `just verify` — exits 0. It runs, in order: the git-hook and release-contract checks, `docs-build`, the eleven private gates, `pre-commit --all-files`, `pip-audit`, `pytest` with coverage, `zenzic check all --strict`, and `zenzic score --stamp`. Roughly **2m40s** on a warm cache (measured 2:37 on a 2026-era 8-core Linux laptop); budget more on a cold one.
- [ ] `zenzic lab all` — all gallery scenarios exit with expected code (`zenzic lab all` now exits non-zero if any scenario fails, so this check is enforceable in CI, not just visual — see CHANGELOG.md)
- [ ] `zenzic score --stamp` committed — badge in README.md reflects current score
- [ ] `zenzic check all .` — zero findings in the repo root
- [ ] `pyproject.toml` version matches the tag (`0.30.0`)
- [ ] `CITATION.cff` version and date updated
- [ ] `CHANGELOG.md` — `[Unreleased]` section moved to the new version heading
- [ ] Update SECURITY.md support table (Add new release, demote previous to Critical/EOL).
- [ ] Satellite release documents updated to match this version: `zenzic-vscode`, `zenzic-action`. **Not** `zenzic-doc` — it is archived and unmaintained, and this checklist named it until 2026-09-12. **Not** `zenzic-mcp` either: it has no release document and no release yet, which is deliberate — see its entry below.
- [ ] Verification of `zenzic init` atomic protection (`EXIT 1` on existing config)
- [ ] Verification of `zenzic init` template didactic comments and Z601 empty baseline

## The Sequence

Six steps, in this order. Steps 3 and 4 exist because `main` cannot be pushed to
directly — measured, not assumed: its ruleset carries a `pull_request` rule with
**zero bypass actors**, and GitHub's "rules that apply to you" endpoint lists it
for the maintainer account. So the bump commit reaches `main` the same way every
other commit does.

```bash
# 1. Merge the feature pull request(s) into main.
#    Nothing to label; the full CI matrix runs on every pull request.

# 2. Cut a bump branch from main. The bump cannot be made on main itself.
git switch main && git pull origin main
git switch -c chore/bump-v0.31.0

# 3. Bump. Edits the version files and commits, signed. Creates no tag.
just release minor          # patch | minor | major

# 4. Open the bump pull request, wait for CI, merge it.
git push -u origin chore/bump-v0.31.0
gh pr create --fill --base main
#    ...CI green, then merge. main now carries the bump commit.

# 5. Tag main. Never `git tag` on its own — see below.
git switch main && git pull origin main
just release-tag            # verifies annotated + signed, does not push
git push origin v0.31.0     # this is what starts the release workflow

# 6. Create the GitHub Release from the tag, using the CHANGELOG section as body.
```

### Why the tag has a recipe

`just release` deliberately creates **no tag**: by the time there is something to
tag, the branch the bump was made on is behind `main`, so tagging there would tag
the wrong commit.

And the wrong tag form is accepted by everything. A lightweight `git tag v0.31.0`
produces an object GitHub reports as type `commit`, with no signature of its own —
and no repository here has a ruleset targeting `refs/tags/*`, so nothing rejects
it, while it still triggers the release workflow. `just release-tag` always uses
`-s` and verifies its own output — annotated, signed — before anything is pushed.
`release.yml` re-checks the same three properties (annotated, signed, verified by
GitHub against a registered key) before it builds anything, so a bad tag fails
before it can publish.

### Local prerequisites

Signing is per-machine. Without these, `-s` either fails or produces a signature
GitHub reports as unverified:

```bash
git config user.signingkey   # must be set
git config gpg.format        # ssh (this project signs with SSH keys)
git config commit.gpgsign    # true
```

The public half of that key must be registered on the GitHub account as a
**signing** key. A key registered only for authentication produces a signature
that verifies locally and reads `unverified` on GitHub.

### Publishing is the workflow's job, not yours

Do not run `uv build` or `uv publish` by hand. Pushing the tag starts
`Zenzic Core Release`, which builds the wheel and sdist, generates the build
provenance attestation, and publishes. Running it locally as well produces a
second artifact for the same version with no attestation.

Distribution target: **PyPI** — `pip install zenzic` / `uvx zenzic`.

### `zenzic-mcp` is deliberately different

It has no `RELEASE.md` and no `CONTRIBUTING.md`, because it has never been
released. It also has **no ruleset and an unprotected default branch**, so unlike
every sibling a direct push to its `main` would succeed. Two of those three are
gaps rather than differences: the missing contributor document and the missing
ruleset. The missing release document is genuinely premature and becomes required
the first time a version of it ships.

## Changelog Reference

For a detailed list of changes, see [CHANGELOG.md](./CHANGELOG.md).
For full history, see [Historical Archives](./changelogs/README.md).
