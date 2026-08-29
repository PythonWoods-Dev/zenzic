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

set shell := ["bash", "-c"]

runner     := "uv run --active"
nox_runner := "uv run nox -s"
# Keep BUILD_DATE deterministic across Ubuntu and Git Bash on Windows runners.
export BUILD_DATE := `date -u +'%Y/%m/%d'`
# ZENZIC_EXTRA_ARGS: allow runtime flag injection (e.g. --no-external)
ZENZIC_EXTRA_ARGS := env_var_or_default("ZENZIC_EXTRA_ARGS", "")

# ─── Workflow ─────────────────────────────────────────────────────────────────

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

# Final Guard: atomic verification invoked by pre-push hook + GHA.
# Sequence: pre-commit (all hooks) → pip-audit → pytest tests/ (coverage enforced) → structural audit → score + stamp.
verify: _check-hooks release-contracts check-pinning docs-build
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

_check-hooks:
    #!/usr/bin/env bash
    _missing=0
    if [ ! -f .git/hooks/pre-commit ]; then
        echo -e "\033[33m⚠️  WARNING: pre-commit hook is not installed.\033[0m"
        echo "Without it, static checks and type-checks will NOT run automatically on git commit."
        echo "👉 Fix it by running: uv run --active pre-commit install"
        echo ""
        _missing=1
    fi
    if [ ! -f .git/hooks/pre-push ]; then
        echo -e "\033[33m⚠️  WARNING: pre-push hook is not installed.\033[0m"
        echo "Without it, you might accidentally push broken code to GitHub and fail the remote CI."
        echo "👉 Fix it by running: uv run --active pre-commit install -t pre-push"
        echo ""
        _missing=1
    fi

# Enforce release contracts: dirty allowed only in release-dry.
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
