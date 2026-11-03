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
| `verdict_cache.py` | **Active** (`just verify`) | Skips the tree-deterministic half of `verify` when this exact tree already earned a green verdict; never caches `pip-audit`, the structural audit or the score. `ZENZIC_VERDICT_CACHE=0` forces a full run. |
| `check_commit_message_terms.py` | **Active** (pre-commit hook `commit-message-terms`, commit-msg stage, and the suite through `tests/test_check_commit_message_terms.py`) | Refuses a commit message that names a path inside `.claude/`, `.human/` or `.governance/`, or a term of the local, git-ignored list `.commit-message-terms`. `--self-test` checks the instrument alone. |
| `check_third_party_declarations.py` | **Active** (pre-commit hook `third-party-declarations`, `just verify`, and the suite through `tests/test_check_third_party_declarations.py`) | Fails when a file declared as PythonWoods' own (`REUSE.toml`, a `.license` sidecar or an inline SPDX header) carries another holder's marks: a licence banner, an `@license` tag, a foreign copyright line, a foreign JSON `$id`, or a font. `--self-test` checks the instrument alone. |
| `regenerate_fonts.py` | Hand-run (`uvx --from 'fonttools[woff]==4.68.0' python -I scripts/regenerate_fonts.py`) | Rebuilds the ten `docs/assets/fonts/*.woff2` from the pinned Roboto and Roboto Mono releases (each source refused unless its SHA-256 matches), keeping upstream's copyright and OFL name records; deterministic. `tests/test_bundled_fonts_carry_their_licence.py` checks the result. |
| `mutation_gate.py` | **Active** (`just mutation`, CI) | Runs mutmut over the credential scanner, gates the score floor and the survivor count, and writes `mutants/mutmut-results.txt` — the per-mutant fates a triage needs — beside the aggregate stats. |
| `benchmark.py` | Hand-run | Performance harness for scan throughput; run when investigating a regression. |
| `sync_rule_card_badges.py` | Hand-run | Synchronises rule-card badges after a finding-code change. |
| `sweep_rule_card_badges_v2.py` | Hand-run | Bulk badge sweep across rule cards. |
| `sweep_rule_card_examples.py` | Hand-run | Bulk example sweep across rule cards. |
| `build-assets.js` | Hand-run | Node-side asset build for brand/logo artefacts. |
| `pre-commit-zenzic.sh` | Hand-run | Standalone pre-commit wrapper, kept for environments not using the `.pre-commit-config.yaml` hook. |

`generate_docs_assets.py` was **removed** (2026-08-31): it wrote SVGs via Rich's
export into `static/assets/terminal/`, a Docusaurus-era path that no longer
exists, and its own docstring instructed running it "from the zenzic-doc root" —
a repository layout already superseded.
