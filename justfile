# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
#
# just — interactive developer workflow (Standard Documentation Workflow).
#
# Single source of truth for the quality pipeline. `just verify` is the
# atomic entry-point invoked by the pre-push hook AND by GitHub Actions:
# locale ≡ remote, no drift.
#
# Nox is reserved for isolated environments (multi-version compat).
#
# Quick reference:
#   just sync        — install / update all dependency groups
#   just check       — self-lint: run Zenzic on its own documentation
#   just test        — fast inner loop (pytest -n auto, NO coverage)
#   just test-cov    — audit run (serial pytest with coverage XML)
#   just test-full   — thorough Hypothesis profile (ci, multi-version via nox)
#   just verify      — Final Guard (pre-commit + test-cov + check)
#   just clean       — remove generated artefacts

# Optional local recipes live in .justfile.local, gitignored and absent on a
# fresh clone -- every recipe below still works without it.
import? '.justfile.local'

set shell := ["bash", "-c"]

runner     := "uv run --active"
nox_runner := "uv run nox -s"
# Keep BUILD_DATE deterministic across Ubuntu and Git Bash on Windows runners.
export BUILD_DATE := `date -u +'%Y/%m/%d'`
# ZENZIC_EXTRA_ARGS: allow runtime flag injection (e.g. --no-external)
ZENZIC_EXTRA_ARGS := env_var_or_default("ZENZIC_EXTRA_ARGS", "")

# ─── Workflow ─────────────────────────────────────────────────────────────────

# The hook install is deliberately part of setup rather than a separate step a
# developer has to know about -- three of the four ecosystem repositories were
# once found running with no hooks installed at all, a precondition this now
# blocks on. Running this makes that precondition self-healing.
#
# Bootstrap a fresh clone: install dependencies and git hooks.
setup:
    uv sync --all-groups
    uvx pre-commit install -t pre-commit -t pre-push
    @echo "Setup complete. Run 'just verify' to check everything passes."

# Install or update all dependency groups
sync:
    uv sync --all-groups

# Self-linting: run Zenzic on its own documentation (core integrity check).
# ZRT-010 — Sovereign Parity: Pre-Launch Guard inlined; local == CI.
# Pass extra flags directly: just check --no-external
check *args:
    #!/usr/bin/env bash
    set -euo pipefail
    {{ runner }} zenzic check all --strict {{ ZENZIC_EXTRA_ARGS }} {{ args }}

# Inner loop: ultra-fast, parallel, no coverage (TDD feedback).
# Pillar 3 (Pure Functions) guarantees pytest-xdist worker isolation.
# Excludes `slow` markers (e.g. ZRT-002 60s deadlock guard) — opt-in via `just test-slow`.
test *args:
    {{ runner }} pytest -n auto -m "not slow" {{ args }}

# Opt-in: run slow tests (deadlock guards, long Hypothesis runs, etc.)
test-slow *args:
    {{ runner }} pytest -m "slow" {{ args }}

# Audit: serial, deterministic, with coverage XML (pre-push gate + CI).
# Excludes @pytest.mark.slow — use test-cov-full for the complete suite.
# Coverage threshold (fail_under=80) enforced via pyproject.toml.
test-cov *args:
    {{ runner }} pytest -m "not slow" --cov=src/zenzic --cov-report=term-missing --cov-report=json:coverage.json {{ args }}

# Mutation gate for the credential scanner (Z201/Z204/Z205 path).
# Ratchet, not the Tier-0 target: see scripts/mutation_gate.py for why the floor
# is the measured score and not the documented 90%.
mutation:
    {{ runner }} python scripts/mutation_gate.py

# The expanded four-module set (credentials, scanner, validator, exclusion).
# ~90 minutes, ~4,800 mutants -- deliberately NOT in CI: it ran there once by
# oversight and cost 2h50m per Linux job before failing, because the 95.7% floor
# belongs to the one-module set above and means nothing against four.
#
# Reports the score; does not gate on it. There is no measured floor for this
# population yet, and inventing one would repeat the mistake that put this on
# demand in the first place.
#
# mutmut 3 reads `source_paths` from pyproject.toml and has no CLI override, so
# the list is swapped in for the duration and restored by a trap -- including on
# Ctrl-C or failure, because leaving the expanded list in place would silently
# turn the next CI run back into a three-hour job.
mutation-expanded:
    #!/usr/bin/env bash
    set -euo pipefail
    cp pyproject.toml pyproject.toml.mutbak
    trap 'mv -f pyproject.toml.mutbak pyproject.toml; echo "pyproject.toml restored"' EXIT
    # mutmut reuses whatever mutant/test mapping `mutants/` already holds. After a
    # `just mutation` (credentials only) that mapping covers one module, and an
    # expanded run inherits it: the three added modules come back as 4,380 "no
    # tests" and the run reports 4822/4822 having measured nothing. The output
    # looks complete, which is what makes it dangerous. Regenerate from scratch.
    rm -rf mutants .mutmut-cache
    python3 - <<'PY'
    import pathlib, tomllib
    p = pathlib.Path("pyproject.toml"); t = p.read_text(encoding="utf-8")
    expanded = tomllib.loads(t)["tool"]["mutmut"]["mutmut_expanded_source_paths"]
    body = ",\n    ".join(f'"{m}"' for m in expanded)
    t = t.replace('source_paths = ["src/zenzic/core/credentials.py"]',
                  f"source_paths = [\n    {body},\n]", 1)
    p.write_text(t, encoding="utf-8")
    print(f"expanded set active: {len(expanded)} modules")
    PY
    {{ runner }} mutmut run || true
    {{ runner }} mutmut results

# Full audit: includes slow tests (deadlock guards, 1k-file torture, Hypothesis ci).
# Run on Ubuntu only; reserved for pre-release validation.
test-cov-full *args:
    {{ runner }} pytest --cov=src/zenzic --cov-report=term-missing --cov-report=json:coverage.json {{ args }}

# Run the test suite with the thorough Hypothesis profile (ci — 500 examples)
test-full *args:
    HYPOTHESIS_PROFILE=ci {{ nox_runner }} tests {{ args }}

# ─── Quality Gates (4-Lifecycle-Gates model) ──────────────────────────────────

# Fast static check pass: run all pre-commit hooks without the full test suite.
lint:
    {{ runner }} pre-commit run --all-files

# Optional repository-local checks. They are defined only in the gitignored
# `.justfile.local`, so they cannot be static dependencies of `verify` -- a
# fresh clone without that file must still parse and run `verify` cleanly
# rather than fail with an unknown-dependency error at parse time.
#
# The outcomes below are deliberately different, because they are different
# failures. A clone with no local recipe file is ordinary: nothing is wrong,
# and the skip is announced rather than hidden. A clone that has *opted in* to
# local tooling and then lost its recipe file is a half-installed setup, where
# the checks the operator believes are running silently are not -- that fails
# hard, because a control absent from the execution path is indistinguishable
# from one that was never written.
#
# The opt-in marker is a local git config key, deliberately not a file or
# directory name. `.git/config` is never cloned, pushed or forked, so this
# cannot be inherited by accident: a fork that creates a directory this
# project also happens to use is a legitimate fork, not a broken install, and
# must behave exactly like a plain clone. Opt in with:
#     git config --local zenzic.local-tooling true
_local-checks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -f .justfile.local ]; then
        just _local-gates
        exit 0
    fi
    if git config --local --get zenzic.local-tooling >/dev/null 2>&1; then
        echo -e "\033[31mBLOCKED: this clone opts in to local tooling, but '.justfile.local' is missing.\033[0m" >&2
        echo "  The local checks cannot run, so this would verify less than it appears to." >&2
        echo "  Restore '.justfile.local', or opt out with:" >&2
        echo "    git config --local --unset zenzic.local-tooling" >&2
        exit 1
    fi
    if [ -d .claude ] || [ -d .human ]; then
        echo -e "\033[31mBLOCKED: a governance tree is present, but this clone is not opted in.\033[0m" >&2
        echo "  '.claude/' and/or '.human/' exist here, so this is a maintainer clone —" >&2
        echo "  but '.justfile.local' is absent and 'zenzic.local-tooling' is unset, so" >&2
        echo "  every private gate is being skipped while 'just verify' reports success." >&2
        echo "  That is the failure this check exists to make visible: a green run that" >&2
        echo "  verified less than it appeared to." >&2
        echo "  Fix — restore the private recipes, then opt this clone in:" >&2
        echo "    git config --local zenzic.local-tooling true" >&2
        echo "  A genuine contributor fork has neither directory and never reaches this." >&2
        exit 1
    fi
    echo "note: '.justfile.local' not present — repository-local checks skipped (expected for a fresh clone)."

# Final Guard: atomic verification invoked by pre-push hook + GHA.
# Sequence: pre-commit (all hooks) → pip-audit → pytest tests/ (coverage enforced) → structural audit → score + stamp.
verify: _check-hooks release-contracts check-pinning docs-build
    @just _local-checks
    @echo "==> [1/5] Pre-commit hooks (lint, type-check, flake8-bandit, REUSE)..."
    {{ runner }} pre-commit run --all-files
    @echo "==> [2/5] Dependency vulnerability audit (pip-audit)..."
    {{ runner }} pip-audit
    @echo "==> [3/5] Test suite (coverage enforced, fail_under=80 via pyproject.toml)..."
    {{ runner }} pytest tests/ --cov=src/zenzic --cov-report=term-missing --cov-report=json:coverage.json
    @{{ runner }} python -c "import json; d=json.load(open('coverage.json'))['totals']; pct=d['percent_covered']; print(f'  Coverage: {pct:.2f}%  (gap to 80%: {max(0.0, 80 - pct):.2f} pts)')"
    @echo "==> [4/5] Structural audit (zenzic check all --strict)..."
    {{ runner }} zenzic check all --strict --no-header {{ ZENZIC_EXTRA_ARGS }}
    @echo "==> [5/5] Score computation and badge stamp (zenzic score --stamp)..."
    {{ runner }} zenzic score --stamp --ci --no-header

# Badge freshness gate for non-mutating CI pipelines
check-badges: docs-build
    @echo "==> Validating badge freshness (zenzic score --check-stamp)..."
    {{ runner }} zenzic score --check-stamp --ci --no-header

# ADR-089 — Immutable Infrastructure guard on local hooks (internal CI policy,
# not a public Zenzic rule). Pre-commit `rev:` keys must be 40-char
# commit SHAs, not mutable tags. Regex anchored to line-start so the
# `# vX.Y.Z` annotation comment is safe.
check-pinning:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Validating Immutable Infrastructure (ADR-089)..."
    if grep -E '^[[:space:]]*rev:[[:space:]]*v?[0-9]+\.[0-9]+' .pre-commit-config.yaml >/dev/null 2>&1; then
        echo "[ADR-089] FATAL: Unpinned tag detected in pre-commit config. Zenzic internal policy requires SHA-256 pinning." >&2
        grep -nE '^[[:space:]]*rev:[[:space:]]*v?[0-9]+\.[0-9]+' .pre-commit-config.yaml >&2
        echo "👉 Update via: uvx pre-commit autoupdate --freeze" >&2
        exit 1
    fi
    echo "✓ ADR-089: all pre-commit hooks pinned to immutable commit hashes."

# Blocking gate, not a warning. A pre-commit hook that is merely declared in
# .pre-commit-config.yaml runs nothing: the hook has to be installed into
# .git/hooks for the commit-time gate to exist at all. Three of the four
# ecosystem repositories were found with no hook installed, so every commit
# in them bypassed markdownlint, REUSE and the formatter silently.
#
# A missing pre-commit hook cannot block its own commit -- there is nothing
# installed to run -- so this check fails `just verify` instead, which is the
# pre-push path and what CI runs. Exit 1, never a warning: the previous
# version of this recipe printed the same diagnosis and let the work proceed.
# Blocking gate, not a warning. A pre-commit hook that is merely declared in
# .pre-commit-config.yaml runs nothing: the hook has to be installed into
# .git/hooks for the commit-time gate to exist at all. Three of the four
# ecosystem repositories were found with no hook installed, so every commit
# in them bypassed markdownlint, REUSE and the formatter silently.
#
# A missing pre-commit hook cannot block its own commit -- there is nothing
# installed to run -- so this check fails `just verify` instead, which is the
# pre-push path and what CI runs. Exit 1, never a warning: the previous
# version of this recipe printed the same diagnosis and let the work proceed.
_check-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    # CI checks out a bare working tree and never commits from it, so git hooks
    # are meaningless there -- and requiring them would fail every run for a
    # condition no CI job can or should fix. The gate exists for the machine
    # where commits are actually authored.
    if [ -n "${CI:-}" ]; then
        echo "CI environment: git-hook check skipped (hooks gate local commits only)"
        exit 0
    fi
    _missing=0
    # commit-msg is listed because a hook declared in .pre-commit-config.yaml is
    # not an installed hook: `pre-commit install` writes pre-commit only, and the
    # commit-msg stage needs `-t commit-msg`. Without this line the
    # breaking-change marker check would be declared, uninstalled, and silent --
    # indistinguishable from a clean run.
    for _h in pre-commit pre-push commit-msg; do
        if [ ! -f ".git/hooks/${_h}" ] || ! grep -qi "pre-commit" ".git/hooks/${_h}"; then
            echo -e "\033[31mBLOCKED: the ${_h} hook is not installed (or is not pre-commit's).\033[0m"
            echo "  Without it the ${_h} gate does not run, and defects reach the remote."
            echo "  Fix: uvx pre-commit install -t ${_h}"
            _missing=1
        fi
    done
    if [ "${_missing}" -ne 0 ]; then
        echo ""
        echo "Refusing to continue with an uninstalled git hook."
        exit 1
    fi
    echo "git hooks installed (pre-commit, pre-push, commit-msg)"

release-contracts:
    #!/usr/bin/env bash
    set -euo pipefail
    grep -qE '^version:' justfile
    grep -qE '^release part:' justfile
    grep -qE '^release-dry part' justfile
    grep -q -- '--dry-run --allow-dirty --verbose' justfile
    if sed -n '/^release part:/,/^[^[:space:]].*:/p' justfile | tail -n +2 | grep -q -- '--allow-dirty'; then
        echo "release-contracts failed: release part must not use --allow-dirty"
        exit 1
    fi
    if sed -n '/^release part:/,/^[^[:space:]].*:/p' justfile | tail -n +2 | grep -qE 'git[[:space:]]+tag'; then
        echo "release-contracts failed: release part must not create tags"
        exit 1
    fi
    if ! grep -q 'git commit -S -s' justfile; then
        echo "release-contracts failed: all git commits must use DCO (-s) and GPG signing (-S)"
        exit 1
    fi

# Release orchestration: explicit, transparent, and lockfile-first.
release part: release-contracts
        #!/usr/bin/env bash
        set -euo pipefail
        case "{{ part }}" in
            patch|minor|major) ;;
            *) echo "Invalid part '{{ part }}'. Use patch|minor|major"; exit 2 ;;
        esac
        uv run --active bump-my-version bump {{ part }}
        uv sync
        version="$(uv run --active bump-my-version show current_version)"
        git add -u
        git commit -S -s -m "release: bump version to ${version}"

# Show the current project version
version:
    @uv run --active bump-my-version show current_version

# Simulate a release bump without modifying any files
# Usage: just release-dry patch|minor|major [--short]
release-dry part *args:
    #!/usr/bin/env bash
    set -euo pipefail
    _short=false
    for _arg in {{args}}; do [[ "$_arg" == "--short" ]] && _short=true; done
    if $_short; then
        uv run --active bump-my-version bump {{part}} --dry-run --allow-dirty --verbose 2>&1 \
            | grep -E 'current version|New version will be|Dry run'
    else
        uv run --active bump-my-version bump {{part}} --dry-run --allow-dirty --verbose
    fi

# ─── Cleanup ──────────────────────────────────────────────────────────────

# Remove generated artefacts (.nox is kept — reuse avoids reinstalling deps)
clean:
    rm -rf dist/ .pytest_cache/ .hypothesis/ .zenzic-score.json coverage.json


# Serve the documentation site locally
docs-serve +args="":
    uv run --extra docs mkdocs serve {{args}}

docs-build:
	uv run --extra docs mkdocs build --strict

# Report which staggered-publication blog links are ready to paste back in
# (target now live) vs still pending (target still draft). Always exits 0 --
# this is a report to run before each day's publish action, not a gate. The
# gate itself is scripts/check_blog_link_schedule.py's default mode, wired
# into pre-commit and CI.
blog-link-schedule:
	uv run python3 scripts/check_blog_link_schedule.py --schedule

# Optimize blog images and animated GIFs for web performance
optimize-assets:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "==> Optimizing animated GIFs with gifsicle..."
    find docs/assets/images -name "*.gif" -exec gifsicle -O3 --colors 128 --lossy=80 {} -o {} \;
    echo "✓ Assets optimized successfully."

# Run the "Power Triad" sandbox for a landing-page terminal screenshot (broken
# link, path traversal, leaked credential) — output is meant to be captured
# manually, not asserted on
screenshot-hero:
    cd tests/sandboxes/hero_specimen && {{runner}} zenzic check all --strict

# Run the circular-link sandbox for a terminal screenshot demonstrating Z106
# CIRCULAR_LINK detection — output is meant to be captured manually
screenshot-circular:
    cd tests/sandboxes/screenshot_circular && {{runner}} zenzic check all --show-info
