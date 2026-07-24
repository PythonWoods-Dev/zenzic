<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Release Procedure — Zenzic Core

> **[MAINTAINER SOP]** *This document contains the Standard Operating Procedure for Core Maintainers to cut and publish a new release. If you are an end-user looking for new features, please see the [CHANGELOG](./CHANGELOG.md).*

## Release Metadata

| Field    | Value      |
| :------- | :--------- |
| Version  | v0.24.2     |
| Codename | Magnetite   |
| Date     | 2026-07-24 |
| Status   | Stable |

## Release Checklist

Before tagging, every item must be green:

- [ ] `just verify` — exits 0 (pre-commit hooks → pytest → `zenzic score --stamp` → badge freshness → `zenzic check all --strict`)
- [ ] `zenzic lab all` — all 20 scenarios exit with expected code
- [ ] `zenzic score --stamp` committed — badge in README.md reflects current score
- [ ] `zenzic check all .` — zero findings in the repo root
- [ ] `pyproject.toml` version matches the tag (`0.24.2`)
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
git tag v0.24.2
git push origin main --tags
```

- [ ] Create GitHub Release from the tag, using the `## [0.24.2]` CHANGELOG section as the release body.

## Changelog Reference

For a detailed list of changes, see [CHANGELOG.md](./CHANGELOG.md).
For full history, see [Historical Archives](./changelogs/README.md).
