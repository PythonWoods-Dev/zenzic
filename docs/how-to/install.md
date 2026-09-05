---
description: "Install Zenzic and run your first documentation quality check."
---
<!-- markdownlint-disable MD024 -->

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Install Zenzic

Zenzic reads directly from the filesystem and works with any Markdown-based project. Use it
in local development, as a pre-commit hook, in CI pipelines, or for one-off audits.

---

## Canonical Distribution Hierarchy

To guarantee deterministic quality without environment contamination or dependency collisions, Zenzic recommends three distinct distribution tracks in order of priority:

```text
  ┌────────────────────────────────────────────────────────────────────────┐
  │  Track 1: Pre-commit (Recommended)  ──> Isolated, Pinned, Zero-Drift   │
  │  Track 2: Project Dependency        ──> Docs-as-Code, uv/pip lockfile │
  │  Track 3: Global / Ephemeral         ──> One-Off Audits, Non-Python   │
  └────────────────────────────────────────────────────────────────────────┘
```

---

### Track 1: Pre-commit (Recommended) {#track-1-pre-commit}

!!! tip "Zero Environment Contamination & Maximum Determinism"
    Pre-commit runs Zenzic in a dedicated, isolated virtual environment managed by `pre-commit`. It prevents dependency collisions with your host project or system libraries (e.g., `pydantic` or `google-re2` version conflicts) and guarantees reproducible execution across every contributor workstation.

Add Zenzic to your `.pre-commit-config.yaml`:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0  # Pinned release tag for reproducible local audits
    hooks:
      # Fast staged-file credential & forbidden pattern scanner (<50ms per commit)
      - id: zenzic-guard

      # Optional: full repository graph & link integrity audit (ideal for pre-push)
      # - id: zenzic-verify
      #   stages: [pre-push]
```

Install the git hook into your repository:

```bash title="Terminal"
pre-commit install
# Optional: install pre-push stage if using zenzic-verify
pre-commit install --hook-type pre-push
```

---

### Track 2: Project Dependency (Docs-as-Code) {#track-2-project-dependency}

!!! info "Native Lockfile & VS Code IDE Auto-Discovery"
    If your project already uses a Python toolchain (`uv`, `poetry`, `pdm`, or `pip-tools`), declaring Zenzic as a project dependency locks its version alongside your documentation tooling (e.g., MkDocs or Zensical).

Add Zenzic to your `pyproject.toml` with a compatible-release range:

```toml title="pyproject.toml"
[project.optional-dependencies]
docs = [
    "zenzic~=0.30.0",
]
```

Install and synchronize your environment:

=== "uv"

    ```bash title="Terminal"
    # Add to dev/docs dependency group
    uv add --dev "zenzic~=0.30.0"

    # Synchronize and run via uv
    uv run zenzic check all
    ```

=== "pip"

    ```bash title="Terminal"
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install "zenzic~=0.30.0"
    zenzic check all
    ```

**Advantages of Track 2:**

- **VS Code Extension Integration**: The [Zenzic VS Code Extension](../editor/vscode.md) automatically discovers the active `.venv/bin/zenzic` executable.
- **Unified Lockfile**: Guarantees identical execution between local developers running `uv run zenzic` and CI pipelines running `just check`.

---

### Track 3: Global / Ephemeral Execution (One-Off Audits) {#track-3-global-ephemeral}

!!! warning "Dependency Conflict Notice"
    Global installations share system packages and may suffer from version drift or collisions. Track 3 is intended for quick audits of non-Python repositories or machines without `pre-commit` installed. For daily development, prefer **Track 1** or **Track 2**.

=== "Ephemeral Run (uvx)"

    ```bash title="Terminal"
    # Execute immediately in a temporary isolated environment
    uvx zenzic@0.30.0 check all
    ```

=== "Global Binary (uv tool)"

    ```bash title="Terminal"
    # Install as an isolated global CLI tool
    uv tool install zenzic
    zenzic check all
    ```

=== "User Global (pip)"

    ```bash title="Terminal"
    pip install --user zenzic
    zenzic check all
    ```

---

### Static analysis only — no build runtime required {#lean-agnostic}

Zenzic reads configuration files (`mkdocs.yml`, `zensical.toml`, `pyproject.toml`) as plain text. It does **not** execute your build engine (MkDocs, Zensical, or any other static site generator) or its runtime plugins.

Do **not** install heavy build dependencies into your linting environment. The linting environment has one dependency: `zenzic`.

---

## Init → Config → Check workflow {#init-config-check}

The standard workflow for adopting Zenzic in a project:

### 1. Init — scaffold a configuration file {#init}

Bootstrap a `.zenzic.toml` with a single command. Zenzic identifies the documentation engine
from its configuration files and pre-populates `[build_context]` accordingly:

```bash
zenzic init
```

**Example output when `mkdocs.yml` is present** (rendered inside a bordered "Zenzic Init" panel):

```text
✔ .zenzic.toml created.
✔ .zenzic.local.toml will be scaffolded next (machine-local, gitignored).
💡 Engine: mkdocs (auto-detected).

Run zenzic check all to verify your documentation.
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
│ Customise docs directory, excluded paths, engine adapter, and lint rules. │
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

---

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
