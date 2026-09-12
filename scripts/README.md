<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# `scripts/` — hand-run maintenance tooling

Nothing here is wired into `just`, `nox`, pre-commit, or CI. That is deliberate,
not neglect: these are tools a maintainer runs by hand when a specific need
arises. An audit confirmed every file in this directory is invoked by no
automated entry point, so "not referenced" is not on its own evidence that a
script is dead — check this table first.

| Script | Status | When to run it |
| :--- | :--- | :--- |
| `generate_blog_headers.sh` | **Active** | Regenerates the six Foundations header images from real fixtures. See [`BLOG_HEADERS.md`](BLOG_HEADERS.md). |
| `benchmark.py` | Hand-run | Performance harness for scan throughput; run when investigating a regression. |
| `sync_rule_card_badges.py` | Hand-run | Synchronises rule-card badges after a finding-code change. |
| `sweep_rule_card_badges_v2.py` | Hand-run | Bulk badge sweep across rule cards. |
| `sweep_rule_card_examples.py` | Hand-run | Bulk example sweep across rule cards. |
| `build-assets.js` | Hand-run | Node-side asset build for brand/logo artefacts. |
| `pre-commit-zenzic.sh` | Hand-run | Standalone pre-commit wrapper, kept for environments not using the `.pre-commit-config.yaml` hook. |

`generate_docs_assets.py` was **removed** (2026-08-31): it wrote SVGs via Rich's
export into `static/assets/terminal/`, a Docusaurus-era path that no longer
exists, and its own docstring instructed running it "from the zenzic-doc root" —
a repository layout already superseded. The mechanism it used was replaced by
the `freeze` captures documented in `BLOG_HEADERS.md`.
