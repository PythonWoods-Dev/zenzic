---
sidebar_label: "CLI Commands"
description: "Every Zenzic CLI command, flag, exit code, and output format."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CLI Commands

Complete reference for every Zenzic command, flag, and exit code.

---

## Command Specification Matrix

Select a command tab to view its execution flags, default behaviors, and usage examples:

=== "zenzic check"

    Run full or targeted static analysis checks across the workspace:

    | Flag | Short | Default | Description |
    | :--- | :---: | :---: | :--- |
    | `--strict` | `-s` | `false` | Promotes warnings to blocking errors (Exit 1). Enables external HTTP link verification. |
    | `--ci` | — | `false` | CI pipeline shorthand: applies `--strict`, `--no-header`, and `--format github-annotations`. |
    | `--audit` | `-a` | `false` | Sovereign Audit Mode: ignores inline (`zenzic:ignore`) and per-file suppressions. |
    | `--only` | — | `None` | Discards all findings except specified Z-Codes (e.g. `--only Z104,Z201`). |
    | `--format` | `-f` | `text` | Output format: `text`, `json`, `sarif`, or `github-annotations`. |
    | `--save` | — | `None` | Saves formatted report to specified output path. |
    | `--exit-zero` | — | `false` | Forces Exit 0 exit code (except non-suppressible security findings Z2xx). |
    | `--show-info` | — | `false` | Surfaces info-level structural telemetry findings (e.g. Z106 circular links). |
    | `--quiet` | `-q` | `false` | Minimal output mode for pre-commit and CI hooks. |
    | `--offline` | — | `false` | Forces flat `.html` URL slug resolution for offline/intranet distribution. |

    **Usage Examples:**
    ```bash title="Terminal"
    # Execute full validation suite
    zenzic check all

    # Run sovereign audit mode ignoring suppressions
    zenzic check all --audit

    # Export SARIF results for GitHub Code Scanning
    zenzic check all --format sarif --save zenzic-results.sarif
    ```

=== "zenzic score"

    Compute the weighted Document Quality Score (DQS 0–100) and category breakdown:

    | Flag | Short | Default | Description |
    | :--- | :---: | :---: | :--- |
    | `--fail-under` | — | `0` | Minimum required score. Fails quality gate (Exit 1) if score falls below threshold. |
    | `--stamp` | — | `false` | Updates README.md status badge with the newly computed DQS score. |
    | `--format` | `-f` | `text` | Output format: `text` or `json`. |
    | `--json` | — | `false` | Shorthand for `--format json`. Suppresses all rich/text output and emits a single JSON object on `stdout`. Preferred for programmatic consumers (e.g., editor integrations, shell scripts). |
    | `--strict` | `-s` | `false` | Includes external HTTP link validation in score calculation. |
    | `--breakdown` | — | `false` | Expands category breakdown showing individual Z-Codes and transparent penalty math. |
    | `--save` | — | `false` | Saves score snapshot to `.zenzic-score.json` for use with `zenzic diff`. |
    | `--check-stamp` | — | `false` | Verifies badge stamp files contain the current score URL. Exits 1 if any badge is stale. |
    | `--no-header` | — | `false` | Suppresses the Zenzic banner (set automatically by `--ci`). |
    | `--ci` | — | `false` | CI shorthand: sets `--no-header`. |

    **Usage Examples:**
    ```bash title="Terminal"
    # Compute score and display category breakdown
    zenzic score

    # Enforce score floor in CI
    zenzic score --fail-under 95

    # Stamp status badge into README.md
    zenzic score --stamp

    # Emit machine-readable JSON for programmatic consumers (editor integrations, scripts)
    zenzic score --json

    # Equivalent long form
    zenzic score --format json
    ```

    ??? info "JSON Output Schema (`--json`)"
        When `--json` (or `--format json`) is passed, the command emits a single JSON
        object on `stdout` with no rich/text output. Suitable for piping to `jq` or
        parsing in editor extensions.

        ```json
        {
          "project": "<project-name>",
          "score": 98,
          "threshold": 0,
          "status": "success",
          "timestamp": "2026-07-26T16:49:29+00:00",
          "categories": [
            { "name": "structural", "weight": 0.30, "issues": 0, "category_score": 1.0,
              "contribution": 0.30, "raw_penalty": 0, "is_capped": false },
            { "name": "navigation", "weight": 0.25, "issues": 0, "category_score": 1.0,
              "contribution": 0.25, "raw_penalty": 0, "is_capped": false },
            { "name": "content",    "weight": 0.20, "issues": 0, "category_score": 1.0,
              "contribution": 0.20, "raw_penalty": 0, "is_capped": false },
            { "name": "brand",      "weight": 0.25, "issues": 0, "category_score": 1.0,
              "contribution": 0.25, "raw_penalty": 0, "is_capped": false }
          ],
          "suppression_count": 2,
          "suppression_cap": 30,
          "suppression_debt_pts": 2,
          "debt_status": "MANAGED DEBT"
        }
        ```

        Possible values of `status`: `success`, `failing` (score < `fail_under`),
        `security_breach` (Z2xx finding detected).

=== "zenzic diff"

    Evaluate score delta and finding changes against a stored baseline file:

    | Flag | Short | Default | Description |
    | :--- | :---: | :---: | :--- |
    | `--base` | `-b` | `.zenzic-score.json` | Path to stored baseline score snapshot file. |
    | `--format` | `-f` | `text` | Output format: `text` or `json`. |
    | `--strict` | `-s` | `false` | Promotes warnings to errors during differential audit. |

    **Usage Examples:**
    ```bash title="Terminal"
    # Compare current score against baseline snapshot
    zenzic diff --base .zenzic-score.json
    ```

=== "zenzic explain"

    Inspect finding code details, remediation guides, and configuration origin genealogy:

    | Parameter / Flag | Description |
    | :--- | :--- |
    | `CODE` | Target Z-Code (e.g. `Z101`, `Z201`, `Z601`). |
    | `config` | Explains active `.zenzic.toml` values and file origin genealogy. |

    **Usage Examples:**
    ```bash title="Terminal"
    # Explain rule specification and remediation
    zenzic explain Z104

    # Display active configuration genealogy
    zenzic config explain
    ```

=== "zenzic init"

    Scaffold a new `.zenzic.toml` configuration file:

    | Flag | Default | Description |
    | :--- | :---: | :--- |
    | `--force` | `false` | Overwrites existing `.zenzic.toml` (Atomic safety protection prevents accidental overwrite by default). |

    **Usage Examples:**
    ```bash title="Terminal"
    # Bootstrap configuration scaffold
    zenzic init
    ```

=== "zenzic lsp"

    Start the Language Server Protocol (ZLS) server over `stdio`:

    | Communication Protocol | Client Compatibility | Description |
    | :--- | :--- | :--- |
    | `JSON-RPC 2.0 (stdio)` | VS Code, Neovim, Emacs, Zed | Language server process executed by editor extension infrastructure. |

---

## Shared Execution Flags

## Global flags {#global-flags}

These flags control Zenzic's signal-to-noise profile across routine scans, CI gates,
and incident response workflows.

### `--strict`

**`--strict` controls the pipeline gate, not the display of findings.** Zenzic always
shows every finding it detects — errors and warnings alike — regardless of this flag.
What changes is how warnings affect the **exit code**:

- **Without `--strict`:** warnings → Exit 0 (pipeline passes). Hard errors still cause Exit 1.
- **With `--strict`:** warnings are promoted to blocking errors → Exit 1 (pipeline fails).

When strict mode is active Zenzic prints a `STRICT MODE: Warnings have been promoted to errors.`
line in the report footer, so the CI log is unambiguous even when the same findings would
otherwise be non-blocking.

| Command | Effect |
| :--- | :--- |
| `check links --strict` | Validates external HTTP/HTTPS URLs via concurrent network requests |
| `check all --strict` | Validates external URLs + treats warnings as errors |
| `check references --strict` | Treats Dead Definitions (unused reference links) as hard errors |
| `score --strict` / `diff --strict` | Runs link check in strict mode |

The `--strict` flag enforces rigorous validation: for link checking, it validates external HTTP/HTTPS links via active network requests (which are disabled by default for performance); for references, it treats Dead Definitions as fatal errors instead of warnings.

You can also set `strict = true` in `.zenzic.toml` to make it the permanent default.

### `--ci`

`--ci` is a convenience shorthand designed specifically for GitHub Actions pipelines, available on `check all`, `score`, and `diff`. It acts as an implicit non-interactive mode and suppresses the ASCII art header globally (`no_header = True`).

For `check all`, it forces two additional behaviors simultaneously:

1. Sets `strict = true` (warnings promote to errors).
2. Sets `--format github-annotations` (if no other format is specified).

This flag bypasses `ZenzicReporter` completely, outputting raw `::error::` strings that GitHub Actions parses natively to create inline annotations on pull requests.

```bash
zenzic check all --ci
```

### `--only`

`--only` applies a destructive engine-level filter to the Zenzic findings pipeline. It accepts a comma-separated list of Z-Codes. Any findings that do not match the specified codes are silently discarded *before* being processed by the formatter.

Use this to run highly targeted, isolated checks—for example, if you only want to scan for broken links (`Z104`) and orphans (`Z402`) without running the rest of the validations, or if you want to silence everything except credential leaks (`Z201`).

```bash
zenzic check all --only Z104,Z402
zenzic check links --only Z101,Z104
```

### `--exit-zero`

Always exits with code `0` even when issues are found. All findings are still printed and
scored — only the exit code is suppressed. Useful for observation-only pipelines.

Security events are never downgraded by this flag: Exit 2 (credential scanner breach) and
Exit 3 (path traversal guard system-path incident) always keep priority over ordinary failures.

You can also set `exit_zero = true` in `.zenzic.toml` to make it the permanent default.

### `--show-info`

By default, info-level findings are hidden to keep everyday output focused on actionable
violations. Use `--show-info` to surface structural telemetry — non-blocking measurements that
inform architectural decisions without signalling defects.

The canonical example is `CIRCULAR_LINK` (Z106): documentation Knowledge Graphs naturally
produce link cycles, and the analyzer tracks them as topological metrics rather than errors.
High cycle density on a specific page is a data point for Information Architecture review,
not a quality gate trigger.

Available on all `zenzic check` commands.

```bash
zenzic check links --show-info
zenzic check all --show-info
```

### `--quiet`

`--quiet` is available on `zenzic check all` and is designed for silent builders
(pre-commit and CI hooks) that need minimal output.

- Suppresses the rich analysis panel and per-file verbose report.
- Prints a compact one-line summary for error/warning totals.
- Prints an explicit security one-liner for credential scanner findings (Exit 2).
- Still enforces fatal exit behavior, including security priority (`3 > 2 > 1`).

```bash
zenzic check all --quiet
```

### `--offline`

`--offline` is available on `check all`, `check links`, and `check orphans`. It forces
all adapters (MkDocs and Zensical) to resolve URLs **without**
`use_directory_urls`, producing flat `.html` paths instead of clean directory-based slugs.

Use this flag when linting documentation that will be distributed as static files — for
example, bundled onto a USB drive or served over an intranet without a web server.

```bash
zenzic check all --offline          # flat URL mode: guide/install.md → /guide/install.html
zenzic check links --offline
zenzic check orphans --offline
```

When active, Zenzic banner displays:

```text
NOTICE: [Offline mode: forcing flat URL structure]
```

!!! note "Engine parity"
    The `--offline` flag has **identical behaviour** on MkDocs and Zensical adapters.
    This ensures Zenzic remains a consistent Structural Custodian regardless of your build engine.

### `--no-external`

`--no-external` is available on `check all` and `check links`. Within the link-validator pipeline,
it skips **Pass 3** — concurrent HTTP HEAD validation of external URLs — while keeping Pass 1
(filesystem and target-map resolution) and Pass 2 (internal link validation) active.

Use this flag in air-gapped or offline development environments where external URL reachability
cannot be verified, or as a speed optimisation when external link health is confirmed by other means.

```bash
zenzic check all --strict --no-external   # enforce structural/quality checks; skip external HTTP
zenzic check links --no-external          # internal links only; skip external HTTP checks
```

When active, the report appends a transparency notice:

```text
💡 External link validation skipped (--no-external).
```

!!! warning "Never use in CI"
    `--no-external` is a **developer scope control**, not a CI flag. Omit it in unattended
    CI pipelines — external link failures are legitimate gate failures. The permanent mechanism
    for excluding known-unstable URLs is `excluded_external_urls` in `.zenzic.toml`.

| Concern | Affected by `--no-external`? |
| :--- | :--- |
| Pass 1 — Filesystem and target-map resolution | ❌ Never skipped |
| Pass 2 — Internal link validation | ❌ Never skipped |
| Pass 3 — External HTTP HEAD requests | ✅ Skipped |

Credential scanner and path traversal guard run in dedicated security checks and are not controlled by `--no-external`.

### `--exclude-url` {#exclude-url}

`--exclude-url <PREFIX>` is available on `check all` and `check links`. It bypasses
external URL validation for any URL that starts with the given prefix — **at runtime**,
without touching `.zenzic.toml`. The flag is repeatable.

```bash
# Suppress a domain whose DNS is not yet live
zenzic check all --strict --exclude-url https://staging.example.com/

# Suppress multiple CI/CD paradox URLs in a single invocation
zenzic check all --strict \
  --exclude-url https://my-site.example.com/blog/ \
  --exclude-url https://github.com/org/repo/releases/tag/v<version>
```

Runtime prefixes are **merged** with any `excluded_external_urls` entries already present
in `.zenzic.toml` — the two mechanisms co-exist and accumulate.

!!! tip "CI/CD deployment paradox"
    Use `--exclude-url` in your CI workflow for URLs referencing published artefacts not yet
    reachable at build time (e.g. a GitHub Release page, a staging deployment, or a blog post
    scheduled for future publication). Inject the flag via an environment variable:

    ```yaml
    env:
      ZENZIC_EXTRA_ARGS: >-
        --exclude-url https://my-site.example.com/blog/
        --exclude-url https://github.com/org/repo/releases/tag/v<version>
    run: zenzic check all --strict $ZENZIC_EXTRA_ARGS
    ```

!!! info "Permanent exclusions belong in `.zenzic.toml`"
    For URLs that are **always** unreachable (e.g. GitHub auth pages, rate-limited private APIs),
    use `excluded_external_urls` in `.zenzic.toml` — that list is version-controlled and auditable.
    Reserve `--exclude-url` for **transient** deployment-time paradoxes.

### `--exclude-dir` / `--include-dir`

Available on `zenzic check all` (and individual sub-commands). These flags provide
one-shot directory scope overrides **per invocation** without touching `.zenzic.toml`:

| Flag | Effect |
| :--- | :--- |
| `--exclude-dir DIR` | Skip this directory during the scan (repeatable) |
| `--include-dir DIR` | Force-include a directory even if excluded by config (repeatable) |

`--include-dir` cannot override **system guardrails** (Level 1a/1b exclusions such as
`node_modules/` or adapter metadata files).

```bash
# Exclude a generated folder for this run only
zenzic check all --exclude-dir build/ --exclude-dir .cache/

# Force-include a directory that was excluded in .zenzic.toml
zenzic check all --include-dir legacy-docs/
```

### `--no-color` / `--force-color` {#output-flags}

These global flags (accepted by all commands) control ANSI output independently of TTY detection.

| Flag | Effect |
| :--- | :--- |
| `--no-color` | Strip all ANSI color and style codes from output |
| `--force-color` | Emit ANSI codes even when stdout is not a TTY |

**Environment variables:**

| Variable | Equivalent to |
| :--- | :--- |
| `NO_COLOR` (any value) | `--no-color` |
| `FORCE_COLOR` (any value) | `--force-color` |

`NO_COLOR` conforms to the `NO_COLOR` standard convention (no-color.org).
When both `NO_COLOR` and `FORCE_COLOR` are set, `--no-color` / `NO_COLOR` always wins.

**Default behaviour:** Zenzic uses Rich's TTY auto-detection. Colors are active when
stdout is a terminal; they are stripped automatically when piped or redirected — no flag required.

```bash
# Strip color: CI log aggregators, plain-text files
zenzic check all --no-color
NO_COLOR=1 zenzic check all

# Force color: CI systems that support ANSI but do not report a TTY
zenzic check all --force-color
FORCE_COLOR=1 zenzic check all

# Pair with --format json for fully machine-readable output
zenzic check all --no-color --format json > report.json
```

---

## Initialization

```bash
zenzic init                               # Scaffold .zenzic.toml in the current project
zenzic init ../new-project                # Initialize a remote directory (creates it if needed)
zenzic init --pyproject                   # Write config into pyproject.toml [tool.zenzic]
zenzic init --force                       # Overwrite existing config without prompting
zenzic init --local                       # Scaffold only .zenzic.local.toml (machine-local overlay)
zenzic init --plugin plugin-scaffold-demo # Scaffold a plugin SDK package
```

**Smart detection** — when `pyproject.toml` exists in the project root, `zenzic init`
asks whether to embed the configuration there as a `[tool.zenzic]` table instead of
creating a separate `.zenzic.toml`.  Pass `--pyproject` to skip the prompt and write
directly into `pyproject.toml`.

**Nomad mode** — `zenzic init <path>` treats the given path as the target project root.
The directory is created if it does not exist. The caller's CWD is not affected.

Engine auto-detection is included in both modes: if `mkdocs.yml` or `zensical.toml`
is present, the generated configuration pre-sets the `engine` field accordingly.
When no engine config file is found, standalone (engine-agnostic) defaults apply.

`zenzic init --plugin <name>` generates a Python package skeleton with a ready
`zenzic.rules` entry-point and a `BaseRule` template (`src/<module>/rules.py`).
It also includes a minimal docs fixture so the generated project can immediately
run `zenzic check all` as a smoke test.

### Governance-Ready Blueprint

`zenzic init` generates a Governance-Ready configuration pair:

- `.zenzic.toml` (shared constitution, versioned)
- `.zenzic.local.toml` (machine-local sanctuary, git-ignored)

The global file is not an empty shell: it is a governance-ready blueprint with didactic
comments, active CAP defaults, and a direct playbook pointer.

```toml
# SPDX-FileCopyrightText: 2026 [Your Name] <[Your Email]>
# SPDX-License-Identifier: Apache-2.0

# --- PROJECT IDENTITY ---
# [project]
# name = "My Awesome App" # Used for personalized CLI Governance headers

# --- CORE SETTINGS ---
docs_dir = "docs"
strict = true
fail_under = 100

# --- ENGINE CONTEXT ---
[build_context]
engine         = "zensical" # Supported: mkdocs, zensical, standalone
base_url       = "/"
default_locale = "en"

# --- BRAND INTEGRITY ---
[project_metadata]
release_name = "MyRelease"

[governance]
# Maximum allowed architectural debt (inline + per-file suppressions).
# Default: 30. Build fails if exceeded.
suppression_cap = 30
suppression_cap_fail_hard = true

# Terms that should no longer appear in your documentation.
brand_obsolescence = ["OldProduct", "LegacyTerm"]

# Governance Playbook:
# /developers/how-to/release-governance-protocol

# --- I18N PARITY (Optional) ---
# [i18n]
# enabled = true
# base_lang = "en"
# base_source = "docs"
# strict_parity = true
# [i18n.targets]
# it = "docs-it"

# --- GATE 4: CI/CD (GitHub Actions, Optional) ---
# Add this workflow snippet to .github/workflows/zenzic.yml
#
# name: zenzic
# on: [pull_request, push]
# jobs:
#   zenzic-check:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v4
#       - uses: actions/setup-python@v5
#         with:
#           python-version: '3.12'
#       - run: pipx run zenzic check all --strict
```

When `suppression_cap_fail_hard = true` and active suppressions exceed the CAP,
the GitHub Actions job summary renders:

<CapExceededSummary
  activeSuppressions={43}
  globalCap={30}
  remediationUrl="/developers/how-to/release-governance-protocol"
/>

### Local Sanctuary (`.zenzic.local.toml`)

`zenzic init` also scaffolds a didactic local overlay used for private
workstation overrides. This file is never intended for commit and is
automatically protected via `.gitignore` in Git repositories.

```toml
# --- ZENZIC LOCAL OVERRIDES ---
# This file is machine-local and must stay in .gitignore.
# Values declared here override shared config for your workstation only.

[core]
# docs_dir = "my/custom/path/to/docs"

# Z204 Privacy Gate (local secret terms, literal and case-insensitive).
# forbidden_patterns = ["Project Titan", "internal-api.corp", "staging.acme.io"]
forbidden_patterns = []

[governance]
# suppression_cap = 100
# suppression_cap_fail_hard = false

[secrets]
# Store API tokens here (never in shared .zenzic.toml).
# github_pat = "YOUR_GITHUB_PAT"

[debug]
# log_level = "DEBUG"

[env]
# ZENZIC_FORCE_COLOR = "true"
```

### Best practice

Uncomment `[project].name` in the generated file to personalize Governance headers in CLI output.
If `pyproject.toml` or `package.json` already contains a project name, `zenzic init`
auto-injects that name as the commented hint.

Keep secrets and machine-specific overrides in `.zenzic.local.toml` only. Use
`.zenzic.toml` only for team policy and reproducible CI rules.

After generation, first run:

```bash
zenzic check all
```

You should immediately see your first clean audit badge.

---

## Autofix & Cleanup

```bash
zenzic fix                    # Auto-fix structural violations (e.g. Z108) with a dry-run diff
zenzic fix --apply            # Apply fixes directly to files via atomic file writes
zenzic clean assets           # Delete unused assets interactively (prompt before each)
zenzic clean assets -y        # Delete unused assets immediately (no prompt)
zenzic clean assets --dry-run # Preview what would be deleted without deleting
```

Zenzic is read-only by default. Auto-fixing is an explicit, opt-in operation protected by atomic file writes. The `zenzic fix` command performs a safe, memory-only dry run by default and outputs a unified diff. Explicitly passing `--apply` commits the changes to disk. All modifications use an Atomic Write Barrier to guarantee file integrity (if a crash occurs mid-write, the original file is never corrupted).

Currently, `zenzic fix` supports auto-fixing:

- **Z108 (EMPTY_LINK_TEXT):** Injects a placeholder label for empty link text.
- **Z505 (UNTAGGED_CODE_BLOCK):** Injects default `text` language specifier for untagged fenced code blocks.
- **Z603 (DEAD_SUPPRESSION):** Cleanly extracts dead/unused inline suppression comments (`<!-- zenzic:ignore: Zxxx -->`) and `data-zenzic-ignore` HTML attributes without corrupting the surrounding text.

`zenzic clean assets` respects `excluded_assets`, `excluded_dirs`, and
`excluded_build_artifacts` from `.zenzic.toml` — it will never delete files that match these
patterns.

---

## Exit codes {#exit-codes}

| Code | Meaning |
| :---: | :--- |
| `0` | All selected checks passed (or `--exit-zero` was set) |
| `1` | One or more checks reported issues |
| **`2`** | **SECURITY CRITICAL — credential scanner detected a leaked credential** |
| **`3`** | **SECURITY INCIDENT — Path Traversal Guard: link targets an OS system directory** |

!!! danger "Exit code 2 is reserved for security events"
    Exit code 2 is issued by `zenzic check references` and `zenzic check all` when the credential scanner detects a
    known credential pattern embedded in a reference URL. It is never used for ordinary check
    failures. If you receive exit code 2, treat it as a build-blocking security incident and
    **rotate the exposed credential immediately**.

!!! danger "Exit code 3 — Path Traversal Guard Incident"
    Exit code 3 is issued when the path traversal guard detects a link that resolves to an OS
    system directory (`/etc/`, `/root/`, `/var/`, `/proc/`, `/sys/`, `/usr/`). Unlike exit
    code 1, this is a security incident and takes priority over all other exit codes. It is
    never suppressed by `--exit-zero`. See
    [Checks: Path Traversal Guard](./checks#path-traversal-guard) for details.

Each exit code has a distinct visual signature in the Zenzic Report:

### Exit 0 — Zenzic Audit Badge

<!-- Terminal output: run `uvx zenzic check all` -->

### Exit 1 — Quality findings

<!-- Terminal output: run `uvx zenzic check all` -->

### Exit 2 — credential scanner security breach

<!-- Terminal output: run `uvx zenzic check all` -->

---

## JSON output

All concrete check subcommands support `--format json` for machine-readable output.

### `check all`

The aggregated report groups findings by check:

```bash
zenzic check all --format json | jq '.orphans'
zenzic check all --format json > report.json
```

```json
{
  "links":         [],
  "orphans":       [],
  "snippets":      [],
  "placeholders":  [],
  "unused_assets": [],
  "references":    [],
  "nav_contract":  [],
  "suppression_count": 0,
  "suppression_cap": 30,
  "suppression_debt_pts": 0,
  "debt_status": "CLEAN"
}
```

Each key holds a list of issue strings or objects. An empty list means the check passed.
`nav_contract` validates `extra.alternate` links in `mkdocs.yml` against the Virtual Site Map
— always empty for non-MkDocs projects.

For the authoritative machine contract (including `score --format json` and CAP fail-hard payloads),
see [API JSON Contract](./api-json).

### Individual commands

`check links`, `check orphans`, `check snippets`, `check references`, and `check assets`
each accept `--format json` and return a uniform findings structure:

```bash
zenzic check links --format json
zenzic check references --format json --strict
```

```json
{
  "findings": [
    {
      "rel_path": "guides/setup.md",
      "line_no": 42,
      "code": "Z104",
      "severity": "error",
      "message": "guides/setup.md:42: 'install.md' not found in docs"
    }
  ],
  "summary": {
    "errors": 1,
    "warnings": 0,
    "info": 0,
    "security_incidents": 0,
    "security_breaches": 0,
    "elapsed_seconds": 0.042
  }
}
```

Exit codes are preserved in JSON mode: exit 0 when only warnings are found,
exit 1 on errors (or warnings under `--strict`), exit 2 on credential scanner breaches,
exit 3 on path traversal guard path traversal — the same contract as text output.

---

## SARIF output {#sarif-output}

Concrete check subcommands support `--format sarif` to emit a SARIF-compliant report, ready
for direct upload to [GitHub Code Scanning](https://docs.github.com/code-security/code-scanning).

```bash
zenzic check all --format sarif > zenzic-results.sarif
```

!!! note "Machine Silence — Rule R20"
    When `--format sarif` (or `--format json`) is active, **all Rich banners and informational
    panels are suppressed on `stdout`**. Only the machine-readable payload is emitted. This
    guarantees the output is always valid against the SARIF schema, regardless of terminal state.

### `Zxxx` → SARIF `ruleId` mapping

Every Zenzic finding maps verbatim: the `Zxxx` code becomes the `ruleId`. The
`tool.driver.rules` array is populated dynamically — only codes that produced at least one
result in the run are declared. Each rule entry carries a `helpUri` pointing to the anchor
in this reference page.

| Finding | `ruleId` | SARIF `level` |
| :--- | :---: | :---: |
| Z101 LINK_BROKEN | `Z101` | `error` |
| Z102 ANCHOR_MISSING | `Z102` | `error` |
| Z103 ORPHAN_LINK | `Z103` | `error` |
| Z104 FILE_NOT_FOUND | `Z104` | `error` |
| Z105 ABSOLUTE_PATH | `Z105` | `error` |
| Z106 CIRCULAR_LINK | `Z106` | `note` |
| Z107 CIRCULAR_ANCHOR | `Z107` | `error` |
| Z108 EMPTY_LINK_TEXT | `Z108` | `error` |
| Z110 STALE_ALLOWLIST_ENTRY | `Z110` | `warning` |
| Z111 VIRTUAL_ROUTE_BROKEN | `Z111` | `error` |
| Z113 AUTHOR_KEY_COLLISION | `Z113` | `error` |
| Z114 LARGE_PAGINATION_SET | `Z114` | `note` |
| Z201 CREDENTIAL_SECRET | `Z201` | `error` |
| Z202 PATH_TRAVERSAL | `Z202` | `error` |
| Z203 PATH_TRAVERSAL_FATAL | `Z203` | `error` |
| Z204 FORBIDDEN_TERM | `Z204` | `error` |
| Z301–Z303 Reference Integrity | `Z301`–`Z303` | `warning` |
| Z401–Z406 Structure | `Z401`–`Z406` | `warning` |
| Z501–Z505 Content Quality | `Z501`–`Z505` | `warning` |
| Z601 Governance | `Z601` | `warning` |
| Z901–Z902 System | `Z901`–`Z902` | `warning` |
| Z906 NO_FILES_FOUND | `Z906` | `note` |

### Example SARIF output

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "zenzic",
          "version": "<version>",
          "informationUri": "https://zenzic.dev",
          "rules": [
            {
              "id": "Z104",
              "name": "FILE_NOT_FOUND",
              "shortDescription": { "text": "File not found" },
              "defaultConfiguration": { "level": "error" },
              "helpUri": "./finding-codes.md#z104"
            },
            {
              "id": "Z201",
              "name": "CREDENTIAL_SECRET",
              "shortDescription": { "text": "Credential detected" },
              "defaultConfiguration": { "level": "error" },
              "helpUri": "./finding-codes.md#z201"
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "Z104",
          "level": "error",
          "message": { "text": "docs/guides/setup.md:42: 'install.md' not found in docs" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {
                  "uri": "docs/guides/setup.md",
                  "uriBaseId": "%SRCROOT%"
                },
                "region": { "startLine": 42 }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

For automated upload to GitHub Code Scanning, use the
[Zenzic GitHub Action](../how-to/configure-ci-cd#github-actions-zenzic-credential-gate) —
it validates SARIF integrity before upload (truncation guard) and surfaces findings as
inline PR annotations.

---

## Engine override

The `--engine` flag overrides the build engine adapter for a single run without modifying
`.zenzic.toml`. Accepted by `check orphans` and `check all`:

```bash
zenzic check orphans --engine mkdocs
zenzic check all --engine zensical
zenzic check all --engine standalone    # disable orphan check regardless of config
```

If you pass an engine name with no registered adapter, Zenzic lists available adapters and
exits with code 1:

```text
ERROR: Unknown engine adapter 'hugo'.
Installed adapters: mkdocs, standalone, zensical
Install a third-party adapter or choose from the list above.
```

Third-party adapters are discovered automatically once installed — no Zenzic update required.
See [Writing an Adapter](../developers/how-to/implement-adapter.md).

---

## Quality scoring

Individual checks answer a binary question: pass or fail. `zenzic score` answers a different one:
*how healthy is this documentation, and is it getting better or worse over time?*

```bash
zenzic score                   # Compute 0–100 quality score
zenzic score --save            # Compute and persist snapshot to .zenzic-score.json
zenzic score --stamp           # Update audit+score markers in badge_stamp_files
zenzic score --fail-under 80   # Exit 1 if score is below threshold
zenzic score --format json     # Machine-readable score report
zenzic score --ci              # Run in CI mode (suppresses header)
zenzic score [PATH]            # Score a remote project (sovereign root)

zenzic diff                    # Compare current score against saved snapshot
zenzic diff --threshold 5      # Exit 1 only if score dropped by more than 5 points
zenzic diff --format json      # Machine-readable diff report
zenzic diff --ci               # Run in CI mode (suppresses header)
zenzic diff [PATH]             # Diff a remote project against its saved baseline
```

### How the score is computed

Each check category carries a fixed weight that reflects its impact on the reader experience:

| Category | Weight | Rationale |
| :--- | ---: | :--- |
| links | 35 % | A broken link is an immediate dead end for the reader |
| orphans | 20 % | Unreachable pages are invisible — they might as well not exist |
| snippets | 20 % | Invalid code examples actively mislead developers |
| placeholders | 15 % | Placeholder content signals an unfinished or abandoned page |
| assets | 10 % | Unused assets are waste, but they do not block the reader |

Within each category, the score decays linearly: the first issue costs 20 % of the category
weight, the second costs another 20 %, floored at zero. A category with five or more issues
contributes nothing to the total. The weighted contributions are summed and rounded to an integer.

### Regression tracking

```bash
# On main — establish or refresh the baseline
zenzic score --save

# On every pull request — block documentation regressions
zenzic diff --threshold 5
```

`--threshold 5` gives contributors a five-point margin. Set it to `0` for a strict gate where
any regression fails the pipeline.

### Minimum score floor

```bash
zenzic score --fail-under 80
```

Use this when the team has committed to maintaining a defined quality level, regardless of what
the score was last week. You can also set `fail_under = 80` in `.zenzic.toml` to make it
persistent.

### Inline badge stamping

```bash
zenzic score --stamp
```

Updates both marker types in all files listed in `badge_stamp_files` (default: `README.md`):

- `<!-- zenzic:audit-badge -->` → deterministic `passing` / `failing` governance badge
- `<!-- zenzic:score-badge -->` → numeric score badge (`0..100`) with brand color

The Shields.io badge URL on the line immediately following each marker is replaced in place.

| Color | Hex | Condition |
| :--- | :--- | :--- |
| Indigo | `4f46e5` | Score = 100 |
| Amber | `f59e0b` | Score ≥ `fail_under` (passing) |
| Red | `ef4444` | Score < `fail_under` or security override |

The stamp always runs **before** exit-code checks, so the badge reflects the actual score even when
the build fails. When the score is below `fail_under` locally, the red badge is immediate feedback
before the push — it will never appear on main because the CI blocks the commit.
See [Official Badges](../how-to/add-badges.md) for setup and the full CI/CD snippet.

To surface the score without blocking the pipeline:

```bash
zenzic check all --exit-zero   # full report, exit 0 regardless
zenzic score                   # show score for visibility
```

### Detailed score breakdown (`--breakdown`)

Use the `--breakdown` flag to output a detailed category breakdown of occurred Z-Codes (including informational or zero-point codes like `Z106` or `Z401`) and the transparent DQS mathematical formula calculations:

```bash
zenzic score --breakdown
```

Example output:

```text
DETAILED CATEGORY BREAKDOWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRUCTURAL CATEGORY (Weight: 30%, Max: 30.0 pts)
  ✗ Z106 (CIRCULAR_LINK): 24 occurrence(s) x -0.0 pts = -0.0 pts
  Category Raw Penalty:  0.0 pts
  Category Net Score:    30.0 / 30.0 pts

NAVIGATION CATEGORY (Weight: 25%, Max: 25.0 pts)
  ✓ No issues detected
  Category Raw Penalty:  0.0 pts
  Category Net Score:    25.0 / 25.0 pts

CONTENT CATEGORY (Weight: 20%, Max: 20.0 pts)
  ✓ No issues detected
  Category Raw Penalty:  0.0 pts
  Category Net Score:    20.0 / 20.0 pts

BRAND CATEGORY (Weight: 25%, Max: 25.0 pts)
  ✓ No issues detected
  Category Raw Penalty:  0.0 pts
  Category Net Score:    25.0 / 25.0 pts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DQS MATHEMATICAL TRANSPARENCY
  Base Score:                100.0 pts
  + Structural Contribution:   +30.0 pts (max 30.0)
  + Navigation Contribution:   +25.0 pts (max 25.0)
  + Content Contribution:   +20.0 pts (max 20.0)
  + Brand Contribution:   +25.0 pts (max 25.0)
  ─────────────────────────────────────
  Category Subtotal:          100.0 / 100.0 pts
  - Gravity Cap Loss:           -0.0 pts (Brand bucket zeroed cap)
  - Technical Debt Penalty:     -0.0 pts (0 suppression(s) x -1.0 pt)
  ─────────────────────────────────────
  Final Quality Score:        100 / 100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Arsenal Inspection

```bash
zenzic inspect capabilities   # Show all built-in scanners, plugin rules, and engine-specific link bypasses
```

`zenzic inspect capabilities` shows Zenzic's complete scanner arsenal in two sections:

**Section A — Core Scanners (Built-in):** scanners compiled into Zenzic itself from the canonical registry. The credential scanner
(Z201) and path traversal guard (Z202–203) use dedicated exit codes (2 and 3 respectively) that are never
suppressible with `--exit-zero`.

**Section B — Extensible Rules (Plugin System):** rules registered via the `zenzic.rules`
entry-point group from any installed third-party package.

<!-- Terminal output: run `uvx zenzic check all` -->

Each row in the Extensible Rules table shows the entry-point name, the rule's stable `rule_id`
(used in findings and suppression lists), the origin distribution (`(core)` for built-in rules,
or the package name for third-party plugins), and the fully qualified Python class name.

Use this command to verify which rules are active after installing a plugin package.

### `inspect codes` — Tiered code registry

```bash
zenzic inspect codes
zenzic inspect codes --tier governance
zenzic inspect codes --tier plugin
```

`inspect codes` renders the canonical code registry grouped by tier:

- `core`
- `governance`
- `plugin`
- `custom`

The table always uses four columns: **Tier**, **Code**, **Name**, **Status**.

Governance activation is read from loaded configuration:

- `Z601` is `[ACTIVE]` when `[governance].brand_obsolescence` is non-empty.

For plugin rules, status is `[ACTIVE]` only when the plugin source is enabled in
`plugins`. Custom rules from `custom_rules` are shown in the `custom` tier.

Invalid tiers fail fast with exit code `1`:

```text
Error: --tier must be one of: core, governance, plugin, custom, all
```

### `inspect routes` — Site map export

```bash
zenzic inspect routes
zenzic inspect routes --kind physical
zenzic inspect routes --kind virtual
zenzic inspect routes --json
```

`inspect routes` exports the Virtual Site Map as route records. `--kind` accepts only
`physical`, `virtual`, or `all`.

With `--json`, stdout contains only valid JSON in this shape:

```json
{
  "routes": [
    {
      "url": "/guide/install",
      "kind": "physical",
      "source_files": ["docs/guide/install.md"],
      "digest": "...sha256..."
    }
  ]
}
```

Field contract:

- `url`: canonical URL.
- `kind`: `physical`, `tag`, `tag_index`, `pagination`, `author`, or `author_index`.
- `source_files`: repo-relative POSIX source paths that activate the route.
- `digest`: SHA-256 of `url + ':' + ','.join(sorted(source_files))`.

If `--kind` is invalid, the command exits `1` and emits the error to stderr when
`--json` is active, preserving JSON purity on stdout.

---

## Interactive Lab {#lab}

```bash
zenzic lab [CODE] [--list]
```

`zenzic lab` is an interactive showcase that runs bundled Z-code gallery scenarios against
Zenzic and reports whether each scenario met its expected outcome.

### Scenario selection

| Syntax | Behaviour |
| :--- | :--- |
| `zenzic lab` | Display the gallery menu |
| `zenzic lab z101` | Run a single Z-code scenario |
| `zenzic lab all` | Run all 5 gallery scenarios in sequence |
| `zenzic lab --list` | Print the gallery index without running |

### Gallery

| Z-Code | Title | Expects |
| :---: | :--- | :---: |
| `Z101` | Link Integrity | FAIL |
| `Z201` | Credential Scanner | BREACH |
| `Z405` | Asset Integrity | FAIL |
| `Z601` | Brand Obsolescence | FAIL |

### Outcome labels

Each scenario declares its expected outcome. After execution, the lab reports whether
the expectation was met:

| Label | Meaning |
| :--- | :--- |
| `PASS ✓` | Expected clean run — zero findings |
| `EXPECTED FAIL ✓` | Expected errors were found |
| `BREACH ✓` | Expected credential scanner detection |
| `FAIL (unexpected)` | Scenario expected to pass but errors found |
| `BREACH expected — not triggered` | Expected credential scanner hit was not produced |

### Examples

```bash
# Run the credential scanner scenario
zenzic lab z201

# Run the full gallery
zenzic lab all

# Run a single Z-code scenario
zenzic lab z101

# Print the gallery index without running
zenzic lab --list
```

---

## `uvx` vs `uv run` vs bare `zenzic`

| Invocation | Behaviour | When to use |
| :--- | :--- | :--- |
| `uvx zenzic ...` | Downloads and runs in an **isolated, ephemeral** environment | One-off jobs, pre-commit hooks, CI with no project install phase |
| `uvx --from zenzic zenzic ...` | Runs via `uvx` with explicit package source | When you want explicit package resolution while staying outside project env |
| `zenzic ...` (bare) | Requires Zenzic on `$PATH` | Developer machines with a global install |

!!! tip "CI recommendation"
    Prefer `uvx zenzic ...` for CI steps that do not already install project dependencies — it
    avoids adding Zenzic to your production dependency set.
