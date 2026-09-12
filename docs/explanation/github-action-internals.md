---
description: "How zenzic-action enforces security: Path Traversal Guard protocol, Exit Code Contract, Root-First discovery cascade, and Sovereign Intent."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GitHub Action Internals

This page is for **engineers who need to understand what `zenzic-action` does under the hood** — security reviewers, platform teams integrating Zenzic into shared infrastructure, and contributors to the action itself.

For day-to-day usage (copy-paste YAML, input reference), see the [CI/CD Integration guide](../how-to/configure-ci-cd) and the [action README](https://github.com/PythonWoods/zenzic-action).

---

## Architecture Overview

`zenzic-action` is a **composite GitHub Action** built on a strict two-layer architecture:

```text
action.yml            ← public contract (inputs, outputs, env injection)
    │
    ├─▶  uv tool install --isolated --force --quiet zenzic   ← provisioned once per run
    │
    └─▶  zenzic-action-wrapper.sh   ← enforcement layer (security, exit codes, SARIF)
              │
              └─▶  zenzic check all       ← Zenzic Core (analysis engine, invoked from PATH)
```

`action.yml` injects caller-supplied values as environment variables. The wrapper validates, sanitises, and orchestrates the execution. It **never trusts raw inputs** — every path is guarded before it reaches the filesystem or the CLI.

---

## Path Traversal Guard Protocol

The wrapper enforces two independent *Jailbreak Guards* — one for the SARIF output path, one for the configuration file path. Both use the same `case`-based pattern, ensuring identical policy at every read/write boundary.

### SARIF Jailbreak Guard

`sarif-file` is a write path. A malicious workflow could attempt to write outside the checkout directory:

```bash
# Rejected: absolute path
sarif-file: /tmp/evil.sarif

# Rejected: path traversal
sarif-file: ../../etc/evil.sarif
```

The wrapper rejects both patterns before any file I/O occurs:

```bash
case "${ZENZIC_SARIF_FILE}" in
  /*)
    echo "::error title=Zenzic — SARIF Jailbreak::..." >&2; exit 1 ;;
  *../*|*/..|..)
    echo "::error title=Zenzic — SARIF Jailbreak::..." >&2; exit 1 ;;
esac
```

### Config Jailbreak Guard

`config-file` is a read path. An attacker attempting to read `/etc/passwd` or a file outside the workspace via path traversal is blocked by the same pattern:

```bash
case "${ZENZIC_CONFIG_FILE}" in
  /*)   exit 1 ;;
  *../* | */..) exit 1 ;;
esac
```

!!! note "Guard scope"
    The Config Jailbreak Guard applies **only to explicit overrides** — values supplied via the `config-file` input. When `config-file` is left unset, the wrapper passes no `--config` flag at all, and `zenzic` itself falls back to its own normal discovery chain (`.zenzic.toml` at the repository root, then `pyproject.toml [tool.zenzic]`) — the same chain a local run uses. There is no GitHub-Action-specific auto-discovery path to guard.

### SARIF Integrity Check

A `SIGKILL` or Python runtime crash during Zenzic's execution can truncate the SARIF file mid-write. An incomplete SARIF produces a cryptic GitHub API error during upload rather than a meaningful message in the step log.

The wrapper validates the SARIF as JSON before handing it to `codeql-action/upload-sarif`:

```python
import json, os

json.load(open(os.environ["ZENZIC_SARIF_FILE"]))
```

If the file is not valid JSON, a `::warning` annotation is emitted — the upload proceeds so GitHub surfaces its own precise error — and `findings-count` is left at `0` to avoid false positives.

---

## Exit Code Contract {#exit-code-contract}

> Zenzic defines four exit codes, which the wrapper propagates **without remapping**. See
> [Zenzic GitHub Action Reference — Exit Code Contract](../reference/zenzic-action.md#exit-codes)
> for the full table.

Exits `2` and `3` terminate the job unconditionally. Neither `fail-on-error: "false"` nor any other input can suppress them. This is enforced in the wrapper's exit logic, not in `action.yml`, so it cannot be circumvented by overriding action inputs.

### Coherent findings-count for security exits

When a security breach is detected, Zenzic may abort before producing a complete SARIF file. In this case the SARIF contains zero results, even though a real incident occurred.

The wrapper handles this by forcing `findings-count` to `1` when `EXIT_CODE` is `2` or `3` and the parsed count is `0`:

```bash
if [ "${EXIT_CODE}" -eq 2 ]; then
  [ "${FINDINGS}" -eq 0 ] && FINDINGS=1
  echo "findings-count=${FINDINGS}" >> "${GITHUB_OUTPUT}"
  exit 2
fi
```

This ensures downstream steps that read `findings-count` never see `"0 findings, exit 2"` — an incoherent UX that would imply the build failed for no reason.

---

## Secret Guard Step {#guard-scan}

When `guard-scan: "true"` is set, the action runs `zenzic guard scan` as a standalone composite step **before** the main quality gate. This implements Defense-in-Depth for teams where contributors may bypass pre-commit hooks with `git commit --no-verify`.

The guard scan uses the same `version` pin as the main check. It loads config the same way `check all` does — `.zenzic.toml`/`pyproject.toml` overlaid with `.zenzic.local.toml` when present — and checks built-in credential signatures plus any configured `forbidden_patterns`. In practice `forbidden_patterns` is typically empty in CI: `.zenzic.local.toml` is git-ignored by design, and `actions/checkout` never restores it. `zenzic-action` has no built-in mechanism to inject it either — the guard scan only picks up `forbidden_patterns` if a workflow explicitly writes `.zenzic.local.toml` from a secret in an earlier step. That's an opt-in pattern documented in [Configure the Privacy Gate](../how-to/configure-privacy-gate.md#ci-integration), not something this action provides automatically. Built-in credential signatures always apply regardless. If it detects a credential or a configured forbidden term, it exits non-zero and terminates the job immediately — the main `check all` never runs.

> For the full `guard-scan` input reference and workflow examples, see [Zenzic GitHub Action Reference — Inputs](../reference/zenzic-action.md#inputs).

!!! note "Guard scan is always fatal"
    `fail-on-error` does not govern the guard scan step. If secrets are found, the job stops. This mirrors the Exit 2 security contract: security findings are facts, not findings to negotiate.

---

## Sovereign Job Summary {#job-summary}

The wrapper writes a structured Markdown table to `$GITHUB_STEP_SUMMARY` for every non-zero exit. The summary appears in the **GitHub Actions → job → Summary** tab and in PR check details — without requiring the developer to open the step log.

| Exit | Summary title | Content |
|:---:|---|---|
| `1` + CAP | **❌ Suppression CAP Exceeded** | Active/CAP counts, Playbook link |
| `1` generic | **❌ Documentation Findings** | Findings count, Quality Score |
| `2` | **❌ Security Breach** | Z201 rule, action guidance |
| `3` | **❌ Boundary Breach** | Z202/Z203 rules, action guidance |

The **CAP Exceeded** summary is constructed by parsing the SARIF output for a result with `ruleId: "SUPPRESSION_CAP_EXCEEDED"`. No second invocation of Zenzic is required — the CAP-exceeded SARIF contains exactly one result with governance properties embedded in `properties.governance`.

The `cap-exceeded` output (`"true"` / `"false"`) is available to downstream steps for conditional logic (e.g. dashboard automation, PR labeling).

---

## Explicit Config Override {#config-override}

The wrapper does not implement any GitHub-Action-specific configuration discovery of its own. There are exactly two states:

```text
config-file unset  →  no --config flag passed; zenzic's own discovery chain applies
                       (.zenzic.toml at repo root, then pyproject.toml [tool.zenzic])
config-file set    →  validated (see Config Jailbreak Guard above), then the file
                       must exist — if it doesn't, the run fails unconditionally
```

This guarantees **parity between local runs and CI** for the unset case: a developer who runs `zenzic check all` locally picks up `.zenzic.toml` from the root via the exact same discovery logic the action relies on — nothing GitHub-Action-specific is layered on top.

The path is passed to the CLI via `--config` using a Bash array — never a string — so paths containing spaces are handled correctly:

```bash
CONFIG_ARGS=(--config "${ZENZIC_CONFIG_FILE}")
# ...
uvx "${PKG}" check all --format sarif "${CONFIG_ARGS[@]}" ...
```

### A missing `config-file` is always fatal {#config-file-missing}

When a caller explicitly sets `config-file`, a missing file **always** terminates the job with `::error` + `exit 1`. There is no `strict`-mode branching here: `strict` governs how the analysis itself treats findings, not how the action treats a missing configuration file, and the wrapper never silently falls back to `zenzic`'s own discovery chain or to built-in defaults once a specific file has been named.

This is the safe default. A config file typically carries security-relevant settings — `forbidden_patterns`, `suppression_cap`, policy thresholds — so a silent fallback to weaker settings on a missing or mistyped path would be operational deception, with no visible signal a different config quietly took over. Failing loudly surfaces a misconfigured path immediately, rather than letting a silently-substituted policy run unnoticed indefinitely.

Silent fallthrough would be operational deception: the developer believes a specific config — with its own `forbidden_patterns`, `suppression_cap`, and policy thresholds — governs the run, while the system quietly falls back to different, possibly much weaker settings with no visible signal anything is wrong. A misconfigured path (a typo, a moved file) is a common, easy mistake. Failing loudly surfaces it immediately at the point of misconfiguration, rather than letting a silently-substituted policy run unnoticed for however long it takes someone to notice the wrong rules are being enforced. This matches the same fail-loud posture as the CLI's own Exit Code Contract — a security-adjacent setup failure warrants a hard stop, not a quiet downgrade.

---

## Glob-Safe Argument Passing {#glob-safe}

The `ZENZIC_EXTRA_ARGS` environment variable allows callers to pass additional flags (e.g. `--exclude-url`) to the Zenzic CLI at runtime. Because this variable is a plain string that must be word-split into argv tokens, unprotected expansion would trigger Bash glob expansion — a `*` or `?` inside a URL could be expanded against the CI filesystem.

The wrapper disables globbing around the array construction:

```bash
set -f                         # disable glob expansion
EXTRA_ARGS=(${ZENZIC_EXTRA_ARGS:-})   # intentional IFS word-split
set +f                         # restore glob expansion
```

`set -f` / `set +f` is scoped to exactly this one assignment so nothing else in the wrapper is affected. The subsequent expansion uses `"${EXTRA_ARGS[@]}"` — quoted, so no further splitting or globbing occurs when the array is passed to `uvx`.

---

## Related Resources

| Resource | Description |
|---|---|
| [action README](https://github.com/PythonWoods/zenzic-action) | Quick Start, inputs/outputs reference, Sovereign Override usage |
| [CI/CD Integration](../how-to/configure-ci-cd) | Workflow recipes, SARIF badge, score badge |
| [Architecture](./architecture) | Zenzic Core two-pass pipeline, credential scanner middleware, adapter protocol |
| [Architectural Decisions](https://zenzic.dev/developers/explanation/adr-vault) | Architectural decisions behind the exit code contract and path traversal guard |
