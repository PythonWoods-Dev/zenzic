---
sidebar_label: "CI/CD Integration"
description: "GitHub Actions workflows, pre-commit hooks, and CI pipeline integration."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CI/CD Integration

Zenzic is automation-ready out of the box. The `--format json` flag and `--save` option expose machine-readable output that any CI/CD system can consume to drive dynamic badges, quality gates, and regression detection.

---

## JSON Output

Every check command supports `--format json`:

```bash
# Aggregated report for all checks
zenzic check all --format json

# Individual checks
zenzic check links --format json
zenzic check references --format json

# Scoring and regression
zenzic score --format json
zenzic diff --format json
```

### `zenzic check all --format json`

```json
{
  "links":         ["guides/setup.md:12 — Link target 'install.md' not found"],
  "orphans":       ["old-page.md"],
  "snippets":      [{"file": "api/ref.md", "line": 5, "message": "Snippet target not found"}],
  "placeholders":  [{"file": "index.md", "line": 1, "issue": "TODO", "detail": "Fix this"}],
  "unused_assets": ["images/old-logo.png"],
  "references":    [],
  "nav_contract":  []
}
```

### `zenzic score --format json`

```json
{
  "project": "zenzic",
  "score": 100,
  "threshold": 0,
  "status": "success",
  "timestamp": "2026-03-24T12:00:00+00:00",
  "categories": [
    {"name": "structural", "weight": 0.30, "issues": 0, "category_score": 30.0, "contribution": 30.0},
    {"name": "content",    "weight": 0.20, "issues": 0, "category_score": 20.0, "contribution": 20.0},
    {"name": "navigation", "weight": 0.25, "issues": 0, "category_score": 25.0, "contribution": 25.0},
    {"name": "brand",      "weight": 0.25, "issues": 0, "category_score": 25.0, "contribution": 25.0}
  ]
}
```

### Individual commands (`check links`, `check orphans`, etc.)

Each individual check command returns a uniform findings structure:

```json
{
  "findings": [
    {"rel_path": "guides/setup.md", "line_no": 42, "code": "Z104", "severity": "error", "message": "guides/setup.md:42: 'install.md' not found in docs"}
  ],
  "summary": {
    "errors": 1, "warnings": 0, "info": 0,
    "security_incidents": 0, "security_breaches": 0,
    "elapsed_seconds": 0.042
  }
}
```

!!! danger "Exit Code Contract (ADR-075)"
    - **Exit 0**: Clean run (or warnings only without `--strict`).
    - **Exit 1**: Quality gate errors or hard link failures.
    - **Exit 2**: Credential scanner breach (Z201 — non-suppressible).
    - **Exit 3**: Path traversal security violation (Z202/Z203 — non-suppressible).

Exit codes are preserved in JSON and SARIF modes, maintaining strict contract parity between terminal and CI/CD pipelines.


---

## GitHub Actions: Zenzic Credential Gate {#github-actions-zenzic-credential-gate}

The simplest integration — fails the build on any documentation error.

### uvx (zero-setup)

No Python setup required. `uvx` fetches and runs Zenzic in a throwaway
environment on every run. Ideal for documentation-only repositories or
teams that do not otherwise need a Python environment in their CI:

```yaml title=".github/workflows/zenzic.yml"
name: Documentation Quality

on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']

jobs:
  zenzic:
    runs-on: ubuntu-latest
    steps:

      - uses: actions/checkout@v6

      - name: Lint documentation
        # --ci automatically applies --strict, --no-header, and --format github-annotations
        # for inline PR feedback
        run: uvx zenzic check all --ci

      - name: Check references and credentials

        run: uvx zenzic check references
```

### astral-sh/setup-uv (pinned version)

Use [`astral-sh/setup-uv`](https://github.com/astral-sh/setup-uv) when you need a pinned Zenzic version,
faster installs on repeated runs (cached wheel), or when your project
already uses uv for dependency management:

```yaml title=".github/workflows/zenzic.yml"
name: Documentation Quality

on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']

jobs:
  zenzic:
    runs-on: ubuntu-latest
    steps:

      - uses: actions/checkout@v6

      - name: Setup uv

        uses: astral-sh/setup-uv@v8
        with:
          enable-cache: true

      - name: Lint documentation

        run: uvx zenzic check all --ci

      - name: Check references and credentials

        run: uvx zenzic check references
```

The `enable-cache: true` option reuses uv tool cache data across runs,
reducing repeated dependency downloads.

Exit code `2` means a credential was detected in a reference URL. Exit code `3` means a link resolves to an OS system path (path traversal guard). Both require immediate investigation — rotate any exposed credential and remove the offending link.

### zenzic-action (recommended)

The official [`PythonWoods/zenzic-action`](https://github.com/PythonWoods/zenzic-action) composite action
installs `uv`, runs Zenzic, validates SARIF integrity, and uploads findings to GitHub Code Scanning — all
in one step. Findings are published to **Security → Code Scanning** and can surface as PR annotations when
GitHub Code Scanning annotations are enabled for the repository:

```yaml title=".github/workflows/zenzic.yml"
name: Documentation Quality

on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']
  pull_request:
    branches: [main]

jobs:
  zenzic:
    name: Documentation Quality Gate
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write        # required for SARIF upload
    steps:

      - uses: actions/checkout@v6

      - name: Run Zenzic

        uses: PythonWoods/zenzic-action@<version>
        with:
          version: "0.15.0"          # pin to a stable release
          format: sarif             # emit SARIF for Code Scanning
          upload-sarif: "true"
          fail-on-error: "true"
```

Security incidents (exit 2 and 3) are never suppressed by `fail-on-error: "false"` — the
[Exit Code Contract](https://github.com/PythonWoods/zenzic-action) is enforced by the action itself.

### Action inputs reference

| Input | Default | Description |
| :--- | :---: | :--- |
| `version` | action pin | Zenzic version to install. Uses the pinned default declared in the action manifest; any explicit value uses `uvx "zenzic==X.Y.Z"`. **Pin in production.** |
| `ci` | `false` | Run with `--ci` to enable `--strict` and inline GitHub PR annotations. Note: Not recommended when using `format: sarif` as annotations are handled by Code Scanning. |
| `only` | `""` | Comma-separated list of Z-Codes (e.g. "Z104,Z402") to restrict checks to specific issues. |
| `format` | `sarif` | Output format: `text`, `json`, `github-annotations`, or `sarif`. Use `sarif` for GitHub Code Scanning. |
| `sarif-file` | `zenzic-results.sarif` | Path for the generated SARIF file (only when `format: sarif`). |
| `upload-sarif` | `true` | Upload SARIF to GitHub Code Scanning via `github/codeql-action/upload-sarif` delegated by the wrapper. |
| `strict` | `false` | Treat warnings as errors (passes `--strict` to Zenzic). |
| `fail-on-error` | `true` | Fail the workflow step on quality findings (exit 1). **Does not affect exit 2 or 3.** |
| `config-file` | `""` | Optional path to a `.zenzic.toml` file inside the workspace. |
| `audit` | `false` | Run sovereign audit mode to bypass inline and file-level suppressions. |
| `diff-base` | `""` | Use a JSON baseline file for `zenzic diff` quality-gate comparisons. |
| `guard-scan` | `false` | Run `zenzic guard scan` before the main gate as a Defense-in-Depth check. |
| `check-stamp` | `true` | Run `zenzic score --check-stamp` after the audit and fail on stale badge stamps. |

### Action outputs

| Output | Description |
| :--- | :--- |
| `sarif-file` | Generated SARIF file path in the workspace (set when `format: sarif`) |
| `findings-count` | Total number of findings reported in the SARIF run |
| `score` | Documentation Quality Score (0–100). Empty when format is not `json` or `sarif`. |
| `suppression-debt-pts` | Debt points deducted from score due to active suppressions. |
| `cap-exceeded` | `true` when suppression CAP is exceeded and blocks the build. |

### Reading results in GitHub

After the workflow runs, Zenzic findings appear in three places:

1. **Security → Code Scanning** — each finding listed with file, line, severity, and `Zxxx` code.
2. **Pull Request → Files changed** — inline annotations on the exact line where the issue was detected.
3. **Checks tab** — the step name appears as failed if `fail-on-error: "true"` and exit 1 or higher.

The `findings-count` output can be consumed by downstream steps to drive custom badge updates or
Slack notifications without re-parsing the SARIF file:

```yaml title=".github/workflows/zenzic.yml"

      - name: Run Zenzic

        id: zenzic
        uses: PythonWoods/zenzic-action@<version>
        with:
          version: "0.15.0"

      - name: Post finding count

        run: echo "Zenzic found ${{ steps.zenzic.outputs.findings-count }} issues"
```

### Progressive Adoption {#progressive-adoption}

For large legacy repositories, fixing hundreds of warnings at once is impossible. The `only` parameter allows teams to adopt Zenzic progressively by enforcing only critical checks (e.g., Broken Links and Credential Leaks) while ignoring structural debt until the team is ready.

By setting `ci: "true"`, the action natively injects the `--ci` flag under the hood, enabling inline PR annotations for the selected violations without requiring GitHub Code Scanning (SARIF) integration.

```yaml title=".github/workflows/zenzic.yml"
      - name: Zenzic Progressive Gate
        uses: PythonWoods/zenzic-action@<version>
        with:
          version: "0.15.0"
          ci: "true"              # Native inline PR annotations (no SARIF required)
          only: "Z101,Z201"       # Gate ONLY fails on broken links and leaked secrets
          fail-on-error: "true"
```

!!! warning "Security incidents are always fatal"
    `fail-on-error: "false"` suppresses exit 1 (quality findings) only. Exit 2 (credential scanner — credential
    detected) and exit 3 (path traversal guard — path traversal) are **never suppressible** by any input.
    The action enforces this unconditionally. See the
    [Exit Code Contract](../reference/cli#exit-codes).

---

## Zenzic Quality Gate — The Diff Protocol {#diff-protocol}

The Zenzic Quality Gate uses `zenzic diff` to compare the current score against a saved baseline. Teams can wire the resulting verdict as a blocking or observational gate in workflow policy.

### How it works

1. **On `main`**: Zenzic runs, saves the score as `.zenzic-score.json`, and uploads it as a CI artifact.
2. **On every PR**: The artifact from `main` is downloaded as the baseline. Zenzic runs on the PR branch and calls `zenzic diff --base <baseline>` to compare.
3. **Verdict**: The workflow reads regression signals from `zenzic diff` and applies the repository's chosen merge policy.

```yaml title=".github/workflows/zenzic-quality-gate.yml"
name: Zenzic Quality Gate

on:
  push:
    branches: [main]
  pull_request:

jobs:
  # On main: save the authoritative baseline
  baseline:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6

      - name: Run Zenzic and save baseline
        uses: PythonWoods/zenzic-action@<version>
        with:
          version: "0.15.0"
          format: json          # triggers .zenzic-score.json snapshot
          upload-sarif: "false"

      - name: Upload baseline artifact
        uses: actions/upload-artifact@v4
        with:
          name: zenzic-baseline
          path: .zenzic-score.json
          retention-days: 90

  # On PRs: compare against main baseline
  quality-gate:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v6

      - name: Download main baseline
        uses: actions/download-artifact@v4
        with:
          name: zenzic-baseline
          path: .zenzic-baseline/
        continue-on-error: true   # first PR on a new repo has no baseline yet

      - name: Zenzic — Quality Gate
        uses: PythonWoods/zenzic-action@<version>
        id: zenzic
        with:
          version: "0.15.0"
          format: sarif
          upload-sarif: "true"
          diff-base: ".zenzic-baseline/.zenzic-score.json"

      - name: Report quality score
        if: always()
        run: |
          echo "Score: ${{ steps.zenzic.outputs.score }}"
          echo "Suppression debt: ${{ steps.zenzic.outputs.suppression-debt-pts }} pts"
          echo "Findings: ${{ steps.zenzic.outputs.findings-count }}"
```

!!! info "Quality Regression via `zenzic diff`"
    When a score regression is detected, the workflow receives a non-zero diff verdict and can enforce either blocking or observational behavior, depending on policy.

---

## GitHub Branch Protection: Required Checks {#branch-protection-required-checks}

Protect `main` and enable **Require status checks to pass before merging**.

### Operational Profile: `zenzic-doc`

Required checks:

- `Build`
- `Audit`
- `Lint PR Title`
- `Check DCO`

Operational rule:

- The `Build` check must run on **every** pull request.
- Do not use `paths` filters on the `pull_request` trigger in `.github/workflows/ci.yml` for `zenzic-doc`.
- Keep `paths` filters on `push` to `main` if you want to optimize post-merge CI minutes.

Rationale:

- `Build` is the structural integrity gate for Markdown and site compilation.
- If `Build` is required but skipped on PR, merge can be blocked in expected/pending state.
- If `Build` is not required, a fatal docs regression can merge and break the live site.

### Operational Profile: `zenzic` (core)

Recommended required checks:

- `Audit (ubuntu-latest, 3.10)`
- `Audit (ubuntu-latest, 3.14)`
- `Lint PR Title`
- `Check DCO`

Why these checks:

- `Audit` enforces tests, quality gate, and badge freshness in CI.
- `Lint PR Title` enforces the PR title convention.
- `Check DCO` enforces `Signed-off-by` for every commit.

Important: every required check must run on `pull_request`. If a required workflow is skipped (for example due to path filters), the PR can remain blocked in expected/pending state.

---

## Audit Mode in CI — Sovereign Audit {#audit-mode}

The `audit: "true"` input forces a sovereign audit: all active `zenzic:ignore` inline comments and all `governance.per_file_ignores` entries are bypassed. Every finding that would normally be hidden by a suppression is surfaced.

Use audit mode in:

- **Nightly builds** — weekly sanity check that suppressed debt remains intentional.
- **Security Review workflows** — before a release, verify the unfiltered documentation state.
- **Debt reduction sprints** — see the full scope of what is being suppressed before raising or lowering `suppression_cap`.

```yaml title=".github/workflows/zenzic-audit.yml"
name: Zenzic Sovereign Audit

on:
  schedule:
    - cron: "0 3 * * 1"  # every Monday at 03:00 UTC
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v6

      - name: Sovereign Audit (suppressions bypassed)
        uses: PythonWoods/zenzic-action@<version>
        with:
          version: "0.15.0"
          format: sarif
          upload-sarif: "true"
          audit: "true"           # bypass all zenzic:ignore and per_file_ignores
          fail-on-error: "false"  # audit is observational, not blocking
```

Results appear in the **Security → Code Scanning** tab. Every suppressed finding is visible alongside active ones. This is the unfiltered truth of your documentation.

---

## Defense-in-Depth: Secret Guard {#guard-scan}

The `guard-scan: "true"` input runs `zenzic guard scan` as a standalone step **before** the main quality gate. Use this in repositories where contributors may bypass pre-commit hooks with `git commit --no-verify`:

```yaml title=".github/workflows/zenzic.yml"
      - name: Run Zenzic Documentation Quality Gate
        uses: PythonWoods/zenzic-action@<version>
        with:
          version: "0.15.0"
          guard-scan: "true"   # zenzic guard scan runs before check all
          format: sarif
          upload-sarif: "true"
```

If `guard scan` detects a hardcoded credential or forbidden pattern, it exits non-zero and terminates the job. `fail-on-error: "false"` does not suppress this — the guard scan is always fatal, consistent with the Exit 2 security contract.

---

## Native Badge Freshness Gate {#dynamic-score-badge}

The legacy dynamic badge workflow is deprecated. Use native badge stamping and
freshness checks:

```bash
zenzic score --stamp
zenzic score --check-stamp
```

Recommended CI behavior: run `zenzic score --check-stamp` after `zenzic check`
to enforce freshness of stamped badges without external badge plumbing.

### The Badge Freshness Gate {#badge-freshness-gate}

`zenzic score --check-stamp` compares the badge URL embedded in your
`README.md` (or any file listed in `badge_stamp_files`) against the score
Zenzic computes at that moment. If they differ, the command exits 1 and
prints an actionable message:

```text
[FAILED] Badge (score) in README.md is stale.
Run 'zenzic score --stamp' locally and commit the updated files to resolve this.
```

The gate is **read-only by default**. Auto-fixing is an explicit, opt-in operation protected by atomic file writes. It only validates what is
already committed.

#### Optional: automate with pre-commit

Zenzic operates zero-config out of the box — the CI gate alone is sufficient.
If you use [pre-commit integration](#pre-commit) and want to automate badge stamping so you
never have to run `--stamp` manually, you can optionally add this hook:

```yaml title=".pre-commit-config.yaml"
  - repo: local
    hooks:
      - id: zenzic-score-stamp
        name: Zenzic Score Badge (stamp)
        entry: zenzic score --stamp --no-header
        language: system
        stages: [pre-commit]
        pass_filenames: false
        always_run: true
```

With this hook, the badge is updated automatically on every `git commit`. If
the score changed, pre-commit fails and reports that `README.md` was modified —
stage the file and run `git commit` again to proceed.

#### Without pre-commit

Run the stamp manually before pushing:

```bash
zenzic score --stamp
git add README.md README.it.md   # or whichever files are in badge_stamp_files
git commit --amend --no-edit     # or a new commit
git push
```

If you skip this step and CI finds a stale badge, the workflow fails with the
error above. Follow the message instructions, stamp locally, and push again.

#### CI configuration (read-only gate)

In GitHub Actions, use only `--check-stamp` — **never `--stamp`**. CI is an
immutable validator, not a file editor:

```yaml title=".github/workflows/zenzic.yml"
      - name: Check badge freshness
        run: uvx zenzic score --check-stamp --no-header
```

When using `zenzic-action`, the badge freshness gate is enabled by default —
no additional configuration needed:

```yaml
      - name: Run Zenzic
        uses: PythonWoods/zenzic-action@v1
```

---

## Regression Detection {#regression}

`zenzic diff` compares the current score against the saved `.zenzic-score.json` baseline and fails if the score dropped:

```yaml title=".github/workflows/zenzic.yml"
- name: Detect score regression
  run: |
    uvx zenzic score --save        # update snapshot
    uvx zenzic diff --threshold 5  # fail if score drops > 5 points
```

For the full Zenzic Quality Gate setup with PR blocking and baseline artifact upload, see the Diff Protocol section above.

---

## Exit Codes Reference

| Code | Meaning | Badge action |
|:---:|---|---|
| `0` | All checks passed | Keep badge green |
| `1` | One or more checks failed | Set badge to `failing` / `ef4444` |
| **`2`** | **Credential scanner: credential detected** | **Rotate credential immediately** |
| **`3`** | **Path traversal guard: path traversal detected** | **Remove offending link immediately** |

> For the full badge copy-paste reference, see [Official Badges](./add-badges.md).

---

## Credential Recovery — When a Credential Is Detected {#credential-recovery}

A credential detection (exit code 2) is not a failed build. It is a **security incident**.
The recovery playbook is short and non-negotiable:

### Step 1 — Identify the exposure

The Zenzic Report tells you everything you need:

```text
 ✘  Z201  docs/how-to/configure.md:4    Secret detected (aws-access-key)
          Credential: AKIA************MPLE
          → Exit code 2 — rotate immediately.
```

Note the file, the line, and the credential type. The credential is always masked in the
report — Zenzic never prints the full value.

### Step 2 — Rotate the credential

**Before doing anything else** — rotate the key in your cloud provider’s console. Do not
commit the fix first. A rotated key is inert even if it remains briefly in your git history.

### Step 3 — Remove from source

Delete or replace the secret in the file Zenzic flagged. Commit the fix.

### Step 4 — Rewrite history if necessary

If the credential appeared in a previous commit that has already been pushed:

```bash
# Interactive rebase to the commit that introduced the secret
git rebase -i <commit-before-secret>^

# Or use git-filter-repo (preferred over BFG for new projects)
git filter-repo --path docs/how-to/configure.md --force
```

!!! warning "Force-push requires coordination"
    Rewriting published history requires a force-push. Coordinate with your team before doing this
    on a shared branch. If the repository is public, assume the credential is already compromised
    regardless of history rewriting — rotation is mandatory.

### Step 5 — Verify no credentials are detected

```bash
uvx zenzic check all
# Expected: exit 0, no credentials detected
```

Only exit 0 means the recovery is complete.

!!! info "Why Zenzic saves you from BFG Repo Cleaner"
    BFG Repo Cleaner is an irreversible tool for purging secrets from git history.
    Its use is a symptom of a process failure: the secret reached the repository undetected.
    Zenzic prevents this by catching credentials **before** they enter the CI pipeline
    — ideally via a pre-commit hook. See [pre-commit integration](#pre-commit) to add Zenzic
    as a local gate that runs on every `git commit`.

---

## Pre-commit Integration {#pre-commit}

The credential scanner in CI is your last line of defence. The pre-commit hook is your first:

```yaml title=".pre-commit-config.yaml"
repos:

  - repo: local

    hooks:

      - id: zenzic-credentials

        name: Zenzic Credentials
        language: system
        entry: uvx zenzic check all
        pass_filenames: false
        stages: [pre-commit]
```

With this hook, `git commit` will refuse to proceed if Zenzic detects a credential,
a broken link, or any exit-1 quality finding. The feedback is instant, the fix is local,
and the secret never touches the remote.

---

## Doc-Code Parity {#doc-code-parity}

Every Zxxx finding code documented in `docs/` must have a registered entry in
`src/zenzic/core/codes.py` in the core package — and vice versa. This bidirectional
invariant is enforced by the `verify-codes-parity` Nox session:

```bash
# Run standalone
nox -s verify-codes-parity

# Runs automatically as part of the full local gate
just verify
```

The session uses **Sovereign Resolution (Fail-Closed)** to locate `codes.py`:

| Condition | Strategy | Command used |
|:----------|:---------|:-------------|
| `ZENZIC_CORE_PATH` set, or `../zenzic` exists | **Core Maintainer** — uses local source tree | `uv run --project <path> python scripts/verify_codes_parity.py` |
| Local core not found | **Fail-Closed** — no fallback allowed | Session fails with core path error |

External contributors must provide a local core checkout (`ZENZIC_CORE_PATH`,
`./_zenzic_core`, or `../zenzic`) to run `nox -s verify-codes-parity`.
