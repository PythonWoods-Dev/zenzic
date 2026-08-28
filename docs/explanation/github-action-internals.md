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
    The Config Jailbreak Guard applies **only to explicit overrides** — values supplied via the `config-file` input. Auto-discovered paths (`.zenzic.toml`, `.github/.zenzic.toml`) are hardcoded in the wrapper source and cannot be injected by an attacker. Guarding them would be security theatre, not security.

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

Zenzic defines four exit codes. The wrapper propagates them **without remapping**:

| Code | Meaning | Suppressible? |
|:---:|---|:---:|
| `0` | Clean — all checks passed | — |
| `1` | Documentation findings (broken links, orphans, dead refs, etc.) | ✅ via `fail-on-error: false` |
| `2` | **SECURITY** — credential pattern, forbidden term, or forbidden URL scheme (Z201/Z204/Z205) | ❌ Never |
| `3` | **SECURITY** — path traversal targeting an OS system directory (Z203 only — ordinary boundary violations, Z202, stay a plain exit 1) | ❌ Never |

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

The guard scan uses the same `version` pin as the main check. It reads `forbidden_patterns` and built-in credential signatures from the repository's `.zenzic.toml`. If it detects a credential or forbidden term, it exits non-zero and terminates the job immediately — the main `check all` never runs.

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

## Root-First Discovery — Configuration Cascade {#cascade}

The wrapper implements a **hierarchical auto-discovery** for the Zenzic configuration file. The search order reflects the conventional placement in real-world repositories:

```text
Priority 1  →  Explicit override   (config-file input is set)
Priority 2  →  .zenzic.toml         (repository root)
Priority 3  →  .github/.zenzic.toml (hidden config directory)
Priority —  →  (no file found)     → Zenzic uses built-in defaults
```

This order guarantees **parity between local runs and CI**: a developer who runs `zenzic check all` locally picks up `.zenzic.toml` from the root, and so does the action in CI.

The discovered path is passed to the CLI via `--config` using a Bash array — never a string — so paths containing spaces are handled correctly:

```bash
CONFIG_ARGS=(--config "${CANDIDATE_CONFIG}")
# ...
uvx "${PKG}" check all --format sarif "${CONFIG_ARGS[@]}" ...
```

### Sovereign Intent Contract {#sovereign-intent}

When a caller explicitly sets `config-file`, they are expressing **sovereign intent** — a deliberate declaration that this specific file governs the run. If the file does not exist, the wrapper does **not** silently fall through to auto-discovery. Silent fallthrough would be operational deception: the developer believes they are testing with custom rules, but the system is secretly using a different configuration.

The response depends on `strict` mode:

| `strict` | File specified | File exists | Outcome |
|:---:|:---:|:---:|---|
| any | no | — | Auto-discovery runs normally |
| any | yes | yes | `--config <file>` passed to CLI |
| `false` | yes | **no** | `::warning` emitted; Zenzic uses built-in defaults |
| `true` | yes | **no** | `::error` + `exit 1` (fatal) |

When the warning path is taken, auto-discovery is **suppressed** — `CONFIG_ARGS` remains empty, and the run continues without any configuration file. This is intentionally more conservative than falling back to a discovered file, because the caller has declared a specific intent that cannot be honoured.

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
