---
description: "Complete reference for the Zenzic GitHub Action — inputs, outputs, exit codes, and the Zenzic Quality Gate protocol."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Zenzic GitHub Action Reference

The `PythonWoods/zenzic-action` action is the official CI enforcement point for the Zenzic documentation quality system. In non-audit mode it executes a three-stage validation pipeline: `zenzic check all` (structural findings), `zenzic score` (DQS governance: `fail_under` + `suppression_cap`), and `zenzic score --check-stamp` (badge freshness, enabled by default). Findings are surfaced in GitHub Code Scanning, and quality regression gating is handled via `zenzic diff` when a baseline is configured.

Source: [github.com/PythonWoods/zenzic-action](https://github.com/PythonWoods/zenzic-action)

---

## Inputs {#inputs}

| Input | Default | Required | Description |
| :--- | :--- | :---: | :--- |
| `working-directory` | `.` | No | Directory to run Zenzic in, relative to the workspace root. |
| `version` | `<version>` | No | Zenzic version to install (`latest` or an exact version pin). Pin to a specific version for reproducible CI. |
| `format` | `sarif` | No | Output format: `text`, `json`, or `sarif`. |
| `sarif-file` | `zenzic-results.sarif` | No | SARIF output path. Must be a **relative** path inside the workspace. Absolute paths and `..` traversal sequences are rejected by the wrapper. |
| `upload-sarif` | `true` | No | Upload SARIF to GitHub Code Scanning. Requires `security-events: write` permission. |
| `strict` | `false` | No | Treat warnings as errors — promotes all `warning`-severity findings to `error`. |
| `fail-on-error` | `true` | No | Fail the workflow step on exit 1 (quality findings). Does **not** suppress exit 2 or 3. |
| `config-file` | *(unset)* | No | Explicit path to a Zenzic TOML config file, relative to the workspace. When omitted, `zenzic` falls back to its own normal discovery chain (`.zenzic.toml` at the repository root, then `pyproject.toml [tool.zenzic]`) — the same chain a local run uses, with no GitHub-Action-specific auto-discovery layered on top. A specified file that doesn't exist always fails the step. |
| `audit` | `false` | No | Sovereign audit mode — bypasses all `zenzic:ignore` inline comments and `governance.per_file_ignores` entries. Reveals the true, unfiltered documentation state. |
| `diff-base` | *(snapshot)* | No | Path to a JSON baseline file for `zenzic diff` comparison. When set, the action compares the current score against this file instead of the saved `.zenzic-score.json`. Use an artifact from `main` to implement the Zenzic Quality Gate. |
| `guard-scan` | `false` | No | Run `zenzic guard scan` as a Defense-in-Depth step **before** the main quality gate. Catches hardcoded credentials and forbidden patterns that bypassed pre-commit hooks. Failure is always fatal — not governed by `fail-on-error`. |
| `check-stamp` | `true` | No | Run `zenzic score --check-stamp` after governance scoring. Fails the workflow when badge markers in `badge_stamp_files` are stale. Set to `false` to opt out. |
| `generate_audit_report` | `false` | No | Generate a formal compliance audit report (`zenzic-audit.json`) and upload it as a workflow artifact. |

The wrapper always passes `--ci` to every `zenzic` invocation — there is no input to opt out of it; there is no `only`/Z-code-filter input.

---

## Outputs {#outputs}

| Output | Description |
| :--- | :--- |
| `sarif-file` | Path to the generated SARIF file. |
| `findings-count` | Total number of findings reported. Security findings (exit 2/3) force a minimum of 1. |
| `score` | Documentation Quality Score (0–100). Populated whenever the DQS Governance Gate runs (any `format`, not just `json`) — skipped only in audit mode or after a security exit (2/3). |
| `suppression-debt-pts` | Technical Debt points deducted from the score due to active suppressions. `0` when no suppressions are active or when audit mode is enabled. |
| `cap-exceeded` | `"true"` when the suppression CAP was exceeded and blocked the build; `"false"` otherwise. CAP detection only runs for `format: sarif` — always `"false"` for `text`/`json` output, even if the CAP was genuinely exceeded. |

---

## Exit Code Contract {#exit-codes}

| Code | Name | Meaning | Suppressible? |
| :---: | :--- | :--- | :---: |
| `0` | Clean | All checks passed — score at or above `fail_under` | — |
| `1` | Quality | One or more findings; score may be below `fail_under` | Yes (`fail-on-error: "false"`) |
| **`2`** | **Credential** | **Z201 CREDENTIAL_SECRET detected — scan aborted** | **Never** |
| **`3`** | **Path Traversal (fatal)** | **Z203 PATH_TRAVERSAL_FATAL detected — scan aborted** | **Never** |

Exit codes 2 and 3 are **never suppressed** by `fail-on-error: "false"`, `--exit-zero`, or any other flag. The wrapper enforces this unconditionally — security findings are facts, not findings to be negotiated.

---

## The Zenzic Quality Gate {#quality-gate}

The Zenzic Quality Gate is the recommended PR enforcement setup. It combines structural checks, governance scoring, optional badge freshness, and regression comparison to block merges that decrease documentation quality.

**Implementation:** see [CI/CD Integration → Diff Protocol](../how-to/configure-ci-cd.md#diff-protocol) for the full `zenzic-quality-gate.yml` workflow.

### Gate Logic

```text
PR opened
  └─ zenzic check all → exit 0/1/2/3 (findings)
  └─ zenzic score → exit 0/1 (fail_under + suppression_cap)
  └─ zenzic score --check-stamp (default: true) → exit 0/1 (freshness)
  └─ zenzic diff --base <main-baseline>
       ├─ score stable or improved → exit 0 ✅ PR can merge
```

The suppression debt is included in the score used for comparison. A PR that adds suppressions to hide findings will show a lower score. Security exits (2/3) remain non-suppressible and always fail the run.

---

## Sovereign Audit Mode {#audit}

When `audit: "true"` is set, the action runs with the `--audit` flag, which bypasses:

- All inline `<!-- zenzic:ignore ZXXX -->` comments
- All `[governance.per_file_ignores]` entries in `.zenzic.toml`

Exclusion zones (`excluded_dirs`, `excluded_file_patterns`) are **not** bypassed by audit mode — they define the scan perimeter, not the suppression policy.

**Use cases:**

- **Nightly builds** — verify suppressed debt remains intentional.
- **Security Review** — surface all Z2xx findings regardless of suppression.
- **Pre-release audit** — measure the true (unfiltered) documentation state before shipping.

> Note: `fail-on-error: "false"` is available for observational audit workflows where findings should not block the run.

---

## Configuration Discovery {#config-discovery}

The action itself implements no GitHub-Action-specific configuration discovery:

| `config-file` | Behaviour |
| :--- | :--- |
| Unset | No `--config` flag passed to `zenzic` — `zenzic`'s own normal discovery chain applies (`.zenzic.toml` at the repository root, then `pyproject.toml [tool.zenzic]`), identical to a local run |
| Set, file exists | `--config <path>` passed; that file governs the run |
| Set, file missing | The step fails unconditionally (`::error` + exit 1) — confirmed directly against the wrapper source, no `strict`-mode branching |

A specified `config-file` is a deliberate declaration of intent: the wrapper never silently falls back to discovery or to built-in defaults once a specific file has been named, regardless of `strict`. This is the design as originally built — `config-file` had no fallback branching at any point in the wrapper's history — not a later restriction of a once-more-permissive behavior. See [GitHub Action Internals: a missing `config-file` is always fatal](../explanation/github-action-internals.md#config-file-missing) for the full rationale.

---

## Security Architecture {#security}

| Guard | What it blocks |
| :--- | :--- |
| SARIF Jailbreak guard | `sarif-file` with absolute path or `..` traversal — rejected before execution |
| Config Jailbreak guard | `config-file` with absolute path or `..` traversal — rejected before execution |
| diff-base Jailbreak guard | `diff-base` with absolute path or `..` traversal — rejected before execution |
| SARIF integrity check | Truncated SARIF JSON (from SIGKILL/runtime abort) — emits `::warning`, uploads anyway |
| Exit Code Contract | Exit 2/3 always propagate — cannot be silenced by any input or env var |

---

## Permissions {#permissions}

Minimum permissions required for the most common configurations:

| Scenario | Permissions |
| :--- | :--- |
| SARIF upload to Code Scanning | `contents: read`, `security-events: write` |
| Artifact upload (baseline) | `contents: read` |
| Audit only (no upload) | `contents: read` |

---

## Environment Variables (Advanced) {#env}

The `ZENZIC_EXTRA_ARGS` environment variable passes additional flags directly to the Zenzic CLI without modifying action inputs:

```yaml
- uses: PythonWoods/zenzic-action@<version>
  with:
    version: "<version>"
  env:
    ZENZIC_EXTRA_ARGS: >-
      --exclude-url https://staging.example.com
      --exclude-url https://example.com/blog/unreleased-post
```

Word-split is intentional (each `--exclude-url <url>` pair becomes separate `argv` elements). Glob expansion is disabled in the wrapper before constructing the argument array.

---

## See Also {#see-also}

- [CI/CD Integration](../how-to/configure-ci-cd.md) — Full workflow examples including the Zenzic Quality Gate.
- [Handle Technical Debt](../how-to/handle-technical-debt.md) — How to audit and reduce suppression debt.
- [Suppression Policy](./suppression-policy.md) — The three suppression levels and the debt cost formula.
- [Scoring Algorithm](./scoring-algorithm.md) — How the quality score is computed.
- [Finding Codes](./finding-codes.md) — Full catalog of all Zxxx codes.
