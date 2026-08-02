---
sidebar_position: 1
sidebar_label: "Your First Audit"
description: "Step-by-step tutorial to run your first Zenzic documentation audit and credential scan in under three minutes."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Your First Audit

**What you'll achieve:** go from zero to a passing Zenzic report in under three minutes. Zenzic detects leaked credentials, orphan pages, and broken links. No configuration file required to start.

!!! tip "Prerequisites"

    You need [uv](https://docs.astral.sh/uv/) on your `PATH`. Everything else is handled automatically.

!!! info "Why start with the Lab?"

    `zenzic lab` runs every scanner against pre-built fixtures. It covers a security breach scenario and a clean-documentation scenario. Total run time: under 60 seconds.

---

## Step 1 — Run Zenzic without installing it {#step-1-uvx}

Point Zenzic at your project root. No virtual environment, no `pip install`:

```bash
uvx zenzic check all
```

`uvx` fetches Zenzic in an isolated environment and discards it when the command finishes.
Run this from the directory that contains your `.zenzic.toml` (or from the repo root).
Zenzic auto-discovers the configuration and activates the correct engine — including
orphan detection (Z402) when a nav contract is present.
If a `blog/` directory exists on disk, `zenzic check all` includes blog posts in the scan scope automatically. No extra setting required. No `blog_dir` to configure.
This is the recommended workflow for CI and for trying Zenzic on an unfamiliar repo.

---

## Step 2 — Credential Scanner Live Demo {#step-2-credential-scanner}

Before configuring anything, watch Zenzic protect a deliberately broken repo:

**Credential scanner demo** — run the Z201 credential scenario:

```bash
uvx zenzic lab z201
```

Zenzic scans the bundled `z201-credentials` fixture and fires **exit code 2** with the
Security Breach banner — the non-suppressible alert for a leaked credential:

<CredentialTerminal
  finding="AWS access key detected"
  location="docs/how-to/configure.md:4"
  credential="AKIA************MPLE"
/>

The masked credential and non-zero exit code are the expected output of the credential scanner.

**Link Integrity Demo (Zenzic Audit Badge)** — now run the Z101 LINK_BROKEN scenario:

```bash
uvx zenzic lab z101
```

The Zenzic Audit Badge: link findings detected, exit 1. The contrast is the proof —
the same engine that caught the secret confirms that clean documentation is genuinely clean.

!!! tip "Interactive Demo — No installation required"

    ```bash
    uvx zenzic lab
    ```

    Launches the gallery menu of 5 Z-code scenarios: credential leaks, broken links, orphan
    assets, brand obsolescence, and i18n parity. No installation. No configuration required.

    → Pick any scenario from the menu, or run a specific one: `uvx zenzic lab z201` (CREDENTIAL_SECRET), `uvx zenzic lab z101` (LINK_BROKEN).

---

## Step 3 — Initialize your Exclusion Zone {#step-3-init}

When you're ready to commit Zenzic to your project, generate a `.zenzic.toml` in one command:

!!! info "Workspace required"

    Zenzic analyses **workspaces, not arbitrary directories**. It performs an upward traversal from the
    target path to locate a root marker (`.git/` or `.zenzic.toml`). If you see:

    ```text
    ERROR: Could not locate repo root: no .git directory or .zenzic.toml found
    ```

    Run `zenzic init` in the root directory of your project to establish the workspace boundary.
    See [Discovery & Exclusion — The Authority of Root](../explanation/discovery#root-authority) for the full rationale.

```bash
cd your-project/
zenzic init
```

Zenzic inspects the directory and pre-configures the engine for you:

```text
Created .zenzic.toml
  Engine pre-set to mkdocs (detected from mkdocs.yml).

Edit the file to enable rules, adjust directories, or set a quality threshold.
Run zenzic check all to validate your documentation.
```

The generated file is annotated — every option is commented out with a short explanation.
Open it, uncomment what you need, leave the rest.

!!! note "Using pyproject.toml?"

    ```bash
    zenzic init --pyproject
    ```

    This appends a `[tool.zenzic]` section to your existing `pyproject.toml` instead of
    creating a separate file.

---

## Step 4 — Run your first real audit {#step-4-audit}

```bash
zenzic check all
```

Zenzic scans every Markdown file, validates internal links against the Virtual Site Map,
checks anchors, scans for credentials, and runs your custom rules — then prints a structured
report and exits with a machine-readable code. For details on exit code definitions and security tiers, see the [Exit Code Contract](../reference/finding-codes#exit-code-contract).

A clean run looks like this — the **Zenzic Audit Badge**:

<!-- Terminal output: run `uvx zenzic check all` -->

Exit 0 confirms that every link resolves, every page is reachable, and no credential is exposed within the analyzed scope.

!!! note "Deliberate Failure — The Traceability Proof"
    Insert a broken link in any file:

    ```markdown title="docs/intro.md"
    [See the guide](./nonexistent-page.md)
    ```

    Run `zenzic check all`. The finding is exact:

    ```text
    docs/intro.md:3  Z101  Internal link resolves to no page in the VSM  → ./nonexistent-page.md
    ```

    File path. Line number. Finding code. No finding without a physical origin.
    This is deterministic traceability — the same guarantee in CI as in local development.

Run `uvx zenzic score` on your own repo to obtain a baseline score without installing anything.

---

## Step 5 — Snapshot technical debt with Baseline Tracking {#step-5-baseline}

If your repository has existing technical debt, capture it into a deterministic baseline snapshot so your team can enforce strict CI gates for new code immediately:

```bash
# Capture current findings into .zenzic-baseline.json snapshot
zenzic check all --update-baseline
```

Subsequent CI audits against `--baseline .zenzic-baseline.json` tag existing debt as `is_baselined: true` without failing your build. This quality gate catches any newly introduced defects or DQS regressions:

```bash
# CI Quality Gate — verify PR against repository baseline
zenzic check all --baseline .zenzic-baseline.json
```

---

## What's next? {#next}

- **Baseline & Anti-Regression** — see [Baseline Tracking](../explanation/baseline-tracking) for CI/CD debt management
- **Measure your score** — run `uvx zenzic score` to get a precise 0–100 DQS for your repo
- **Add a CI gate** — see [CI/CD Integration](../how-to/configure-ci-cd) for automated quality enforcement
- **SARIF export** — `zenzic check all --format sarif` for GitHub Code Scanning inline annotations
- **Strict mode** — add `--strict` to also validate external URLs
- **Custom rules** — add `[[custom_rules]]` entries to `.zenzic.toml` to enforce your own patterns
- **Finding codes** — see the [Finding Codes reference](../reference/finding-codes) for the full `Zxxx` diagnostic catalogue
