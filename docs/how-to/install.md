---
sidebar_position: 1
sidebar_label: "Install & First Run"
description: "Install Zenzic and run your first documentation quality check."
---
<!-- markdownlint-disable MD024 -->

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Install Zenzic

Zenzic reads directly from the filesystem and works with any Markdown-based project. Use it
in local development, as a pre-commit hook, in CI pipelines, or for one-off audits.

---

## Installation Options

Ensure Python 3.10 or higher is installed on your system. Select your preferred installation method:

=== "uv (Recommended)"

    !!! tip "Zero Environment Contamination"
        We strongly recommend using `uv` or `uvx` to execute Zenzic in isolated environments without dependency conflicts.

    **Global Binary Install:**
    ```bash title="Terminal"
    uv tool install zenzic
    zenzic check all
    ```

    **Ephemeral Execution (Zero Installation):**
    ```bash title="Terminal"
    uvx zenzic check all
    ```

    **Project Dev Dependency:**
    ```bash title="Terminal"
    uv add --dev zenzic
    uvx zenzic check all
    ```

=== "pip"

    **Virtual Environment Install:**
    ```bash title="Terminal"
    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install zenzic
    zenzic check all
    ```

    **User Global Install:**
    ```bash title="Terminal"
    pip install --user zenzic
    zenzic check all
    ```

=== "Git Source Execution"

    Execute directly from GitHub without local installation:
    ```bash title="Terminal"
    uvx --from git+https://github.com/PythonWoods/zenzic zenzic .
    ```

    Pin to a specific version tag for deterministic execution:
    ```bash title="Terminal"
    uvx --from git+https://github.com/PythonWoods/zenzic@v0.25.0 zenzic .
    ```

### Static analysis only — no build runtime required {#lean-agnostic}

Zenzic reads configuration files (`mkdocs.yml`, `zensical.toml`, `pyproject.toml`) as plain
text. It does **not** execute the build engine or its plugins.

Do **not** install MkDocs, Material for MkDocs, or any build plugin in your linting
environment. They are not needed. The linting environment has one dependency: `zenzic`.

```bash title="Terminal"
# Audit any project without build dependencies
uvx zenzic check all
```


!!! note "Third-party engine adapters"
    Third-party adapters (e.g. a hypothetical `zenzic-hugo-adapter`) are separate
    installable packages — not extras of `zenzic` itself. No extra is required for
    `StandaloneAdapter` (plain Markdown folders).

---

## Init → Config → Check workflow {#init-config-check}

The standard workflow for adopting Zenzic in a project:

### 1. Init — scaffold a configuration file {#init}

Bootstrap a `.zenzic.toml` with a single command. Zenzic identifies the documentation engine
from its configuration files and pre-populates `[build_context]` accordingly:

```bash
zenzic init
```

**Example output when `mkdocs.yml` is present:**

```text
Created .zenzic.toml
  Engine pre-set to mkdocs (detected from mkdocs.yml).

Edit the file to enable rules, adjust directories, or set a quality threshold.
Run zenzic check all to validate your documentation.
```

If no engine config file is found, `zenzic init` produces an engine-agnostic scaffold (Standalone
mode). In either case, all settings are commented out by default — uncomment and adjust only the
fields you need.

Run Zenzic without a `.zenzic.toml` and it falls back to built-in defaults, printing a Helpful
Hint panel that suggests `zenzic init`:

```text
╭─ 💡 Zenzic Tip ─────────────────────────────────────────────────────╮
│ Using built-in defaults — no .zenzic.toml found.                      │
│ Run zenzic init to create a project configuration file.              │
│ Customise docs directory, excluded paths, engine adapter, and rules. │
╰──────────────────────────────────────────────────────────────────────╯
```

### 2. Config — tune to your project {#config}

Edit the generated `.zenzic.toml` to suppress noise and set thresholds appropriate to your project:

```toml
# .zenzic.toml — place at the repository root
excluded_assets = [
"assets/favicon.svg",      # referenced by mkdocs.yml, not by any .md page
"assets/social-preview.png",
]
placeholder_max_words = 30     # technical reference pages are intentionally brief
fail_under = 70                # establish an initial quality floor
```

See the [Configuration Reference](../reference/index.md) for the full field list.

!!! tip "Git Ignore"
    Add `.zenzic_cache/` to your repository's `.gitignore` to prevent committing the local network validation cache.

### 3. Check — run continuously {#check}

With the baseline established, run Zenzic on every commit and pull request:

```bash
# Pre-commit hook or CI step
# --strict: validate external URLs + treat warnings as errors
zenzic check all --strict

# Save a quality baseline on main
zenzic score --save

# Block PRs that regress the baseline by more than 5 points
zenzic diff --threshold 5
```

---

## Engine modes {#engine-modes}

Zenzic selects an adapter based on the build-engine configuration file present at the repository root. **Engine-aware mode** activates when `mkdocs.yml` or `zensical.toml` is found, enabling nav-aware orphan detection, i18n fallback resolution, locale directory suppression, and Ghost Route tracking. **Standalone mode** activates when no engine config is found — the orphan check is skipped because without a nav declaration every file would appear orphaned.

Use `--engine` to override the detected adapter for a single run without changing `.zenzic.toml`.

> For the full design rationale behind engine-aware vs. standalone mode, see [Architecture — Sovereign CLI](../explanation/architecture.md#sovereign-cli).

## Decommissioning Zenzic

If you need to remove Zenzic from your project, the decommission process takes less than 30 seconds and leaves no trace.

### Step 1 — Remove from CI/CD

Delete the Zenzic block from your workflow files (e.g., `.github/workflows/docs.yml`):

```yaml
- uses: PythonWoods/zenzic-action@<version>
  with:
    version: "<version>"
    format: sarif
    upload-sarif: "true"
```

Or, if running directly in a shell step:

```yaml
- name: Zenzic
  run: uvx zenzic check all
```

### Step 2 — Remove configuration

Delete the configuration file from your repository:

```bash
rm .zenzic.toml
# OR edit pyproject.toml and remove the [tool.zenzic] section
```

---

**Next steps:**

- [CLI Commands reference](../reference/cli.md) — every command, flag, and exit code
- [Advanced features](../reference/advanced-features.md) — Reference integrity, credential scanner, programmatic usage
- [CI/CD Integration](./configure-ci-cd.md) — GitHub Actions, pre-commit hooks, baseline management
