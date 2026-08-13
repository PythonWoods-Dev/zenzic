---
sidebar_position: 3
description: Reference for .zenzic.toml and pyproject.toml configuration fields, types, defaults, and CLI overrides.
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration Reference

Zenzic is configured through a TOML file. Every field has a sensible default, so zero-config usage is fully supported -- but production projects benefit from explicit tuning.

!!! warning "The TOML Root Key Law"

    In TOML, once a `[table]` is declared, all subsequent keys belong to that table. You MUST declare all root-level keys (e.g., excluded_dirs, fail_under) at the absolute top of the .zenzic.toml file, before opening any bracketed sections like `[governance]` or `[network]`. Keys placed at the bottom will be silently swallowed by the preceding table and ignored by Zenzic.

## Config File Priority {#config-priority}

Zenzic resolves configuration using a **4-level hierarchy** — the most specific source wins:

| Priority | Source | Description |
| :---: | :--- | :--- |
| **1 (highest)** | **CLI flags** | `--engine`, `--exclude-dir`, `--strict`, etc. Override every other source for the current run. |
| 2 | `.zenzic.toml` | Standalone file at the repository root — the authoritative sovereign config |
| 3 | `pyproject.toml` | `[tool.zenzic]` table inside `pyproject.toml` |
| 4 (lowest) | Built-in defaults | Hardcoded defaults when no config file is found |

**CLI flags always win.** A flag like `--engine mkdocs` overrides the `engine` value in `.zenzic.toml` for that single run without modifying any file.

**Exclusions and inclusions are cumulative, not replacing:**

- `--exclude-dir` *adds* to the list already defined in the config file.
- `--include-dir` is a **force override**: a directory excluded in `.zenzic.toml` but included via `--include-dir` will be scanned. The only exception is Level 1 System Guardrails (`node_modules`, `.git`, etc.) — these cannot be force-included.

When a config file is present but contains a TOML syntax error, Zenzic raises a `ConfigurationError` with a Rich-formatted message. It will **never** silently fall back to defaults when a file exists but cannot be parsed.

### Standalone `.zenzic.toml`

```toml title=".zenzic.toml"
docs_dir = "docs"
snippet_min_lines = 3
strict = true

[build_context]
engine = "mkdocs"
```

### Embedded in `pyproject.toml`

```toml title="pyproject.toml"
[tool.zenzic]
docs_dir = "docs"
snippet_min_lines = 3
strict = true

[tool.zenzic.build_context]
engine = "mkdocs"
```

Use `zenzic init` to scaffold a config file. If `pyproject.toml` exists, the command will prompt whether to embed the config there. Use `zenzic init --pyproject` to skip the prompt.

`zenzic init` also scaffolds `.zenzic.local.toml` as a machine-local overlay. This
file is designed for Local Sovereignty: local values override shared config, but
must remain private on your workstation.

## `.zenzic.local.toml` Local Sanctuary {#local-sanctuary}

`.zenzic.local.toml` is the private maneuvering space for engineers.

- It is loaded after shared config (`.zenzic.toml` or `[tool.zenzic]`) and therefore wins locally.
- It is intended for machine-specific paths, temporary cleanup knobs, diagnostics, and private secrets.
- It is never a team policy file.

When `zenzic init` runs in a Git repository, it enforces `.zenzic.local.toml` inside
`.gitignore` (creating or updating `.gitignore` safely, without destructive edits).

```toml title=".zenzic.local.toml"
# --- ZENZIC LOCAL OVERRIDES ---
# This file is auto-generated and must stay in .gitignore.
# Everything declared here overrides shared .zenzic.toml only on your machine.

[core]
# docs_dir = "my/custom/path/to/docs"
forbidden_patterns = []

[governance]
# suppression_cap = 100
# suppression_cap_fail_hard = false

[secrets]
# github_pat = "YOUR_GITHUB_PAT"

[debug]
# log_level = "DEBUG"

[env]
# ZENZIC_FORCE_COLOR = "true"
```

Use `.zenzic.toml` for shared constitutional governance. Use `.zenzic.local.toml`
for local experiments and private data only.

### What Belongs Where — Decision Matrix {#local-vs-shared}

| Configuration intent | File |
| :--- | :--- |
| Engine (`engine = "mkdocs"`) | `.zenzic.toml` — shared |
| `docs_dir` | `.zenzic.toml` — **always shared**; if placed only in `.zenzic.local.toml`, CI will use the default (`"docs"`) |
| `fail_under`, `suppression_cap` | `.zenzic.toml` — shared governance gate |
| `strict = true` | **CLI flag only** for monorepos (`--strict`); in `.zenzic.toml` only for projects with stable, actionable warning counts |
| `docs_dir` for temporary path override | `.zenzic.local.toml` — local override only |
| API tokens, `github_pat` | `.zenzic.local.toml` — never commit secrets |
| `log_level = "DEBUG"` | `.zenzic.local.toml` — diagnostics stay local |
| `suppression_cap = 100` (raise for local experiments) | `.zenzic.local.toml` — does not affect team CI |

!!! caution "`docs_dir` trap"
    A `docs_dir` declared only in `.zenzic.local.toml` works on your machine but breaks in CI. CI runners load only `.zenzic.toml` (the local file is in `.gitignore`). Always put `docs_dir` in the shared config.

!!! caution "`strict = true` trap for monorepos"
    Setting `strict = true` in `.zenzic.toml` promotes **all warnings to errors** on every machine. On a monorepo with versioned snapshots this is guaranteed to hard-fail. Use `--strict` as a CI flag instead:
    ```yaml
    # .github/workflows/zenzic.yml
    - run: zenzic check all --strict
    ```

### Source-of-Truth Introspection (`zenzic config explain`)

Use `zenzic config explain` to verify both active value and origin for each
config field.

```bash
zenzic config explain
```

Expected provenance semantics:

- `local` -> `.zenzic.local.toml (Override)`
- `global` -> `.zenzic.toml`
- `default` -> built-in fallback

Example (governance override):

```text
suppression_cap = 45   Source: .zenzic.local.toml (Override)
```

### Governance Suppression Contract (Suppression CAP)

```toml
[governance]
suppression_cap = 30
suppression_cap_fail_hard = true
per_file_ignores = { "docs/legacy/*.md" = ["Z601"] }
```

- `suppression_cap` and `suppression_cap_fail_hard` enforce CAP governance.
- `per_file_ignores` defines scoped suppressions in normal runs.
- `zenzic check all --audit` ignores both inline suppressions and
  `per_file_ignores` to expose full debt truth.

```bash
# Create a .zenzic.toml file at the project root
zenzic init

# Or embed config in pyproject.toml
zenzic init --pyproject
```

---

## Core Settings {#core-settings}

Configure core workspace paths and execution parameters.

### `docs_dir` {#docs-dir}

| | |
| :--- | :--- |
| **Type** | `Path` |
| **Default** | `"docs"` |

Path to the documentation root directory, relative to the repository root.

When omitted, Zenzic defaults to `"docs"`. Set to `"."` to scan the entire
repository root (L1 system exclusions still apply). Set to any other
relative path when your project stores documentation in a non-standard
location such as `website/` or `content/`.

```toml
# docs_dir = "docs"   # default — omit if your docs live in docs/
docs_dir = "."        # scan the entire repository (e.g. README-only projects)
```

### `snippet_min_lines` {#snippet-min-lines}

| | |
| :--- | :--- |
| **Type** | `int` |
| **Default** | `1` |

Minimum number of lines for a fenced code block to be syntax-checked. Set to `3` or higher to skip trivial one-liner import stubs.

```toml
snippet_min_lines = 3
```

### `placeholder_max_words` {#placeholder-max-words}

| | |
| :--- | :--- |
| **Type** | `int` |
| **Default** | `50` |

Pages with fewer words than this threshold are flagged as `short-content` placeholders.

```toml
placeholder_max_words = 100
```

### `placeholder_patterns` {#placeholder-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | See below |

Case-insensitive strings that flag a page as containing placeholder text.

!!! warning "Absolute Override Behavior"
    All list-based configurations in `.zenzic.toml` (such as `placeholder_patterns`) operate as an **Absolute Override**, not an extension.
    If you provide a custom list, it completely replaces the default list.

    To **globally disable Z501**, supply an empty list:
    ```toml
    placeholder_patterns = []
    ```
    To add a custom regex while keeping the defaults, you must explicitly re-declare the default patterns alongside your new ones.

The default list includes both English and Italian patterns:

```toml
# Default patterns (shown for reference — override to customise)
placeholder_patterns = [
  "\\btodo\\b", "\\bfixme\\b", "\\bwip\\b", "\\btbd\\b",
  "\\bstub\\b", "\\bda completare\\b", "\\bin costruzione\\b",
  "\\bin lavorazione\\b", "\\bbozza\\b", "\\bprossimamente\\b"
]
```

### `validate_same_page_anchors` {#validate-same-page-anchors}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `true` |

When `true`, same-page anchor links (`#section`) are validated against headings present in the source file. Enabled by default for stronger source-level integrity checks. Disable it only when anchor IDs are generated by HTML attributes, custom plugins, or build-time macros invisible at source-scan time.

```toml
validate_same_page_anchors = true
```

---

## Exclusion Settings {#exclusion-settings}

Configure file and directory exclusion patterns.

### `excluded_dirs` {#excluded-dirs}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `["includes", "stylesheets", "overrides"]` |

Directories inside `docs/` to exclude from orphan and snippet checks. User entries are **merged** with the immutable System Guardrails (`SYSTEM_EXCLUDED_DIRS`) -- they can never be removed.

**Path matching semantics:** If an entry contains a slash (`/`), it is evaluated against the repository-relative path. If it does not, it evaluates against the directory basename globally.

```toml
excluded_dirs = ["includes", "stylesheets", "overrides", "snippets"]
```

!!! info "System Guardrails (always excluded)"
    The following directories are excluded unconditionally, regardless of configuration:

    `.git`, `.github`, `.venv`, `node_modules`, `.nox`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `.cache`, `.hypothesis`, `.temp`

    These represent the **L1 System Guardrails** layer. No configuration can override them.

### `excluded_file_patterns` {#excluded-file-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Filename glob patterns excluded from **all** checks (orphan detection, placeholder scanning, reference pipeline, and credential scanner). Uses glob syntax compiled to RE2 regular expressions — standard `*` and `?` wildcards are supported.

```toml
# Skip locale-suffixed files and changelogs
excluded_file_patterns = ["*.it.md", "*.fr.md", "CHANGELOG*.md"]
```

### `excluded_assets` {#excluded-assets}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Asset paths (relative to `docs_dir`) excluded from the unused-assets check. Entries may be literal paths or glob patterns (`fnmatch` syntax). Use for files referenced by the build tool or theme templates rather than by Markdown pages.

```toml
excluded_assets = [
  "img/favicon.ico",
  "img/logo.svg",
  "img/social/*.png",
  "_category_.json",
]
```

### `excluded_asset_dirs` {#excluded-asset-dirs}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `["overrides"]` |

Directories inside `docs/` whose non-Markdown files are excluded from the unused-assets check. Use for theme override directories whose files are consumed by the build tool rather than referenced from Markdown pages.

```toml
excluded_asset_dirs = ["overrides", "theme"]
```

### `excluded_build_artifacts` {#excluded-build-artifacts}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Glob patterns (relative to `docs_dir`) for assets generated at build time. Links to matching paths are not flagged as broken even when the file does not exist on disk at lint time. This is especially useful for RSS and Atom feeds generated by plugins (e.g., `mkdocs-rss-plugin`), which are never present in the source repository but are required to be linked natively.

```toml
excluded_build_artifacts = ["pdf/*.pdf", "assets/bundle.zip", "feed_rss_created.xml"]
```

### `excluded_external_urls` {#excluded-external-urls}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

External URLs (or URL prefixes) excluded from the broken-link check in `--strict` mode. A URL is skipped when it starts with any entry in this list.

```toml
excluded_external_urls = [
  "https://internal.example.com",
  "https://github.com/PythonWoods/unreleased-repo",
]
```

!!! warning "Rule R19 — No Domain-Level Exclusions"
    Never add an entire domain as an exclusion (e.g. `"https://zenzic.dev/"`). A blanket domain exclusion creates a permanent blindspot that survives content restructures and silently masks broken links. Entries must target **specific URLs or prefixes**, not root domains. Use `--exclude-url <url>` at the CLI for temporary, one-off skips.

---

## VCS-Aware Exclusion {#vcs-aware-exclusion}

> See [Exclusion Design](../explanation/exclusion-design.md) for the rationale behind conscious exclusion vs. blind VCS automation.

---

### `respect_vcs_ignore` {#respect-vcs-ignore}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `true` |

When `true`, Zenzic reads `.gitignore` files from the repository root and docs directory and excludes matching files from all checks. Enabled by default — see [Exclusion Design](../explanation/exclusion-design.md) for operational guidance.

Forced inclusions (`included_dirs`, `included_file_patterns`) override VCS exclusions, but System Guardrails are always enforced.

```toml
respect_vcs_ignore = true
```

### `included_dirs` {#included-dirs}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Directory names inside `docs/` that are forcefully included even when excluded by VCS ignore patterns or `excluded_dirs`. Forced inclusions **cannot** override System Guardrails (`.git`, `.venv`, etc.).

```toml
included_dirs = ["generated-api"]
```

### `included_file_patterns` {#included-file-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Filename glob patterns (`fnmatch` syntax) forcefully included even when excluded by VCS ignore patterns or `excluded_file_patterns`. Use for build-generated documentation that should be linted despite being in `.gitignore`.

```toml
included_file_patterns = ["api.generated.md"]
```

---

---

## Network Settings {#network-settings}

The `[network]` section controls external network resolution behaviors, specifically atomic local caching.

### `cache_ttl_hours` {#cache-ttl-hours}

| | |
| :--- | :--- |
| **Type** | `int` |
| **Default** | `24` |
| **Section** | `[network]` |

Time-To-Live (in hours) for the atomic local cache of external link validation (`.zenzic_cache/external_links.json`). Set to `0` to completely disable caching and force synchronous network validation for every run.

```toml
[network]
cache_ttl_hours = 24
```

---

## Build Context {#build-context}

The `[build_context]` table tells Zenzic which documentation engine produced the site and how to resolve locale-specific paths.

### `engine` {#engine}

| | |
| :--- | :--- |
| **Type** | `str` |
| **Default** | `"auto"` |

Build engine identifier. Used by the adapter factory to select the correct path-resolution strategy. Built-in adapters: `mkdocs`, `zensical`, `standalone`.

When set to `"auto"` (the default), Zenzic probes the project root at runtime using **engine auto-discovery**, scanning for engine config files in priority order:

1. `zensical.toml` → `zensical`
2. `mkdocs.yml` → `mkdocs`
3. *(no match)* → `standalone`

For production CI, pin the engine explicitly to skip discovery overhead:

```toml
[build_context]
engine = "mkdocs"
```

### `default_locale` {#default-locale}

| | |
| :--- | :--- |
| **Type** | `str` |
| **Default** | `"en"` |

ISO 639-1 code of the default locale. Used by adapters for i18n fallback logic.

```toml
[build_context]
default_locale = "en"
```

### `locales` {#locales}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Non-default locale directory names. Pages in locale directories receive special handling during orphan detection and anchor resolution.

```toml
[build_context]
locales = ["it", "fr", "de"]
```

### `base_url` {#base-url}

| | |
| :--- | :--- |
| **Type** | `str` |
| **Default** | `""` |

Site base URL (e.g. `"/"` or `"/docs/"`). When set, the adapter uses this value instead of attempting static extraction from the build tool's config file. Recommended when the config file uses dynamic patterns that cannot be parsed statically.

```toml
[build_context]
base_url = "/docs/"
```

### `fallback_to_default` {#fallback-to-default}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `true` |

When `true`, missing locale-tree assets and pages fall back to the default-locale tree. Mirrors the `fallback_to_default` option in mkdocs-i18n. Set to `false` to report every missing locale file as an error.

```toml
[build_context]
fallback_to_default = false
```

---

## CI / Exit Behaviour {#ci-exit-behaviour}

Configure continuous integration exit thresholds.

### `fail_under` {#fail-under}

| | |
| :--- | :--- |
| **Type** | `int` |
| **Default** | `0` |

Minimum quality score (0--100). If the Zenzic Score falls below this value, `zenzic score` exits with code 1. A value of `0` disables the threshold (observational mode).

```toml
fail_under = 80
```

> See [Exclusion Design — Governance Score Math](../explanation/exclusion-design.md#governance-score-math) for the flat-cost model and hybrid governance policy design.

### `strict` {#strict}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `false` |

When `true`, treat warnings as errors and validate external URLs via network requests. Equivalent to passing `--strict` on every invocation of `check all`, `score`, or `diff`.

```toml
strict = true
```

### `exit_zero` {#exit-zero}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `false` |

When `true`, `zenzic check all` always exits with code 0 even when issues are found. Issues are still printed and scored. Useful for observation-only pipelines. Credential scanner violations (exit code 2) and path traversal guard events (exit code 3) are **never** suppressed.

```toml
exit_zero = true
```

---

## Project Metadata {#project-metadata}

Configure project identity and release naming metadata.

### `release_name` {#release-name}

| | |
| :--- | :--- |
| **Type** | `str` |
| **Default** | `""` |
| **Section** | `[project_metadata]` |

The current release codename. Used as the protected term in `brand_obsolescence` enforcement — Zenzic emits Z601 if this string appears as an obsolete term in documentation.

```toml
[project_metadata]
release_name = "Graphite"
```

### `badge_stamp_files` {#badge-stamp-files}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `["README.md"]` |
| **Section** | `[project_metadata]` |

Files updated by `zenzic score --stamp`. Each file must contain one or both HTML comment markers: `<!-- zenzic:audit-badge -->` and `<!-- zenzic:score-badge -->`. The Shields.io badge URL on the line immediately following each marker is replaced in place with deterministic audit and score telemetry.

The stamp runs **before** exit-code checks, so the badge always reflects the actual score — including a red badge in local development, which is immediate feedback that the commit will be rejected by CI.

```toml
[project_metadata]
badge_stamp_files = ["README.md", "README.it.md"]
```

Add one or both markers to each listed file, followed on the next line by any Shields.io badge as a placeholder. See [Official Badges](../how-to/add-badges.md) for the complete setup guide.

---

## Governance Settings {#governance-settings}

Configure brand governance and directory policies.

### `brand_obsolescence` {#brand-obsolescence}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[governance]` |
| **Finding** | Z601 `BRAND_OBSOLESCENCE` |

A governance rule to enforce terminology standards across documentation. Ideal for corporate rebranding or deprecating internal project names. Zenzic ships with an empty default list — teams configure their own deprecated term lists here.

When a term in this list appears in any scanned file, Zenzic emits Z601 `BRAND_OBSOLESCENCE` with exit code 2 (same severity as a credential leak). Historical files (e.g. `CHANGELOG*.md`) are excluded via `excluded_file_patterns`. Use an inline `[HISTORICAL]` comment to suppress individual intentional references in other files.

```toml
[governance]
brand_obsolescence = [
    "OldProductName",
    "LegacyBrand",
    "DeprecatedInternalTerm",
]
```

**Pattern matching:** case-sensitive whole-word scan. The term `"Deprecated"` does not match `"DeprecatedFeature"` or `"deprecated"`.

**Scope:** applies to all files within the active `docs_dir` scan scope, subject to the standard exclusion hierarchy.

### `per_file_ignores` {#per-file-ignores}

| | |
| :--- | :--- |
| **Type** | `dict[str, list[str]]` |
| **Default** | `{}` |
| **Section** | `[governance]` |

Scoped suppressions per glob pattern. Security findings remain non-suppressible.

!!! important "Path Resolution Invariant"
    Glob patterns for both `per_file_ignores` and `directory_policies` are evaluated relative to the **repository root**.
    In monorepos or nested layouts, you must include the full path prefix from the repository root:
    *Use `"website/docs/**"` instead of `"docs/**"` if the content folder lives in `website/docs/`.
    * Use `"docs/blog/**"` instead of `"blog/**"` if the blog folder lives inside `docs/blog/`.

### `directory_policies` {#directory-policies}

| | |
| :--- | :--- |
| **Type** | `dict[str, list[str]]` |
| **Default** | `{}` |
| **Section** | `[governance]` |

Strategic directory-level policy exemptions (zero debt). In `--audit` mode,
these findings are surfaced with the `[POLICY_EXEMPTION]` label.

!!! tip "Z620 (Stale Global Suppression)"
    Zenzic automatically maintains configuration hygiene via the `GlobalUsageTracker`. If a pattern declared in `directory_policies`, `excluded_file_patterns`, or `excluded_external_urls` is never used to suppress an actual finding, Zenzic emits the **Z620** warning to prevent dead configuration accumulation. The solution is always to remove the unused policy from `.zenzic.toml`.

### `suppression_cap_scope` {#suppression-cap-scope}

| | |
| :--- | :--- |
| **Type** | `"all"` |
| **Default** | `"all"` |
| **Section** | `[governance]` |

Defines suppression counting scope. Current supported value is `"all"`.

### `suppression_cap_fail_hard` {#suppression-cap-fail-hard}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `true` |
| **Section** | `[governance]` |

When `true`, exceeding `suppression_cap` triggers immediate exit code 1.

```toml
[governance]
suppression_cap = 30
suppression_cap_scope = "all"
suppression_cap_fail_hard = true

[governance.per_file_ignores]
"docs/legacy/**" = ["Z601"]

[governance.directory_policies]
"docs/blog/**" = ["Z601"]
```

---

## Policy-as-Code Settings {#policies-settings}

Configure declarative Policy-as-Code rules (`Z610` and `Z611`). All policy rules are **opt-in** and inactive by default — empty lists (`[]`) short-circuit evaluation in $O(1)$ time with zero performance overhead.

### `required_frontmatter_keys` {#required-frontmatter-keys}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z610 `REQUIRED_FRONTMATTER_MISSING` |
| **Opt-in** | **Yes** |

Declarative list of required YAML frontmatter keys. Every Markdown file in the documentation graph must declare these keys in its leading `---` frontmatter block. Zenzic emits Z610 for each absent required key per file.

```toml
[policies]
required_frontmatter_keys = ["title", "description", "author"]
```

### `forbidden_external_domains` {#forbidden-external-domains}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z611 `FORBIDDEN_DOMAIN_REFERENCE` |
| **Opt-in** | **Yes** |

Declarative list of restricted external domain prefixes. Links (native Markdown `[text](url)` or raw HTML `<a href="url">`) referencing matching domains emit Z611 governance findings. Matching is case-insensitive and covers exact domain names and all subdomains (e.g. `"example.com"` matches `"sub.example.com"`).

```toml
[policies]
forbidden_external_domains = ["legacy.corp", "competitor.example.com"]
```

---

## Custom Rules {#custom-rules}

Project-specific lint rules can be declared inline without writing Python. Each entry applies a regex pattern line-by-line to every `.md` file.

```toml
[[custom_rules]]
id = "ZZ-NOINTERNAL"
pattern = "internal\\.corp\\.example\\.com"
message = "Internal hostname must not appear in public docs."
severity = "error"

[[custom_rules]]
id = "ZZ-NODRAFT"
pattern = "(?i)\\bDRAFT\\b"
message = "Remove DRAFT marker before publishing."
severity = "warning"
```

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `str` | (required) | Stable unique identifier (e.g. `"ZZ001"`) |
| `pattern` | `str` | (required) | Regex applied to each content line |
| `message` | `str` | (required) | Human-readable explanation shown in findings |
| `severity` | `str` | `"error"` | `"error"`, `"warning"`, or `"info"` |

---

## Plugins {#plugins}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Explicit allow-list of external rule plugins to activate from the `zenzic.rules` entry-point group. Core rules shipped by Zenzic are always enabled.

```toml
plugins = ["zenzic-no-draft", "zenzic-link-policy"]
```

Use `zenzic inspect capabilities` to see all discovered rules and their origins.

---

## CLI Flags {#cli-flags}

Several configuration values can be overridden per-run via CLI flags on `zenzic check all`:

| Flag | Overrides | Description |
| :--- | :--- | :--- |
| `--strict` / `-s` | `strict` | Treat warnings as errors; validate external URLs |
| `--exit-zero` | `exit_zero` | Always exit 0 (issues still reported) |
| `--engine ENGINE` | `build_context.engine` | Override the build engine adapter |
| `--exclude-dir DIR` | (additive) | Additional directories to exclude (repeatable) |
| `--include-dir DIR` | (additive) | Force-include directories even if excluded by config (repeatable). Cannot override System Guardrails |
| `--show-info` | (display) | Show info-level findings (e.g. circular links) |
| `--format json` | (display) | Output in JSON format instead of Zenzic report |
| `--fail-under N` | `fail_under` | Exit non-zero if score is below threshold (on `zenzic score`) |
| `--quiet` / `-q` | (display) | Minimal one-line output for pre-commit hooks |

### Override Priority

CLI flags always override both `.zenzic.toml` and `pyproject.toml` values for a single run. The full priority chain is:

```text
CLI flags > .zenzic.toml > pyproject.toml [tool.zenzic] > built-in defaults
```

---

## Complete Example {#complete-example}

```toml title=".zenzic.toml"

docs_dir = "docs"
snippet_min_lines = 3
placeholder_max_words = 100
validate_same_page_anchors = true

# Exclusions
excluded_dirs = ["includes", "stylesheets", "overrides"]
excluded_file_patterns = ["*.it.md", "*.fr.md"]
excluded_assets = ["img/favicon.ico", "img/social/*.png"]
excluded_asset_dirs = ["overrides"]
excluded_build_artifacts = ["pdf/*.pdf"]
excluded_external_urls = ["https://internal.example.com"]

# VCS-aware discovery
respect_vcs_ignore = true
included_dirs = ["generated-api"]
included_file_patterns = ["api.generated.md"]

# Build engine
[build_context]
engine = "mkdocs"
default_locale = "en"
locales = ["it", "fr"]
base_url = "/"
fallback_to_default = true

# CI behaviour
strict = false
fail_under = 80
exit_zero = false

# Custom rules
[[custom_rules]]
id = "ZZ-NOINTERNAL"
pattern = "internal\\.corp\\.example\\.com"
message = "Internal hostname must not appear in public docs."
severity = "error"

# Plugins
plugins = []
```

---

## TOML Pitfalls {#toml-pitfalls}

Avoid common syntax and order pitfalls when editing `.zenzic.toml`.

### Field Order is Law {#field-order}

In TOML, every key written **after** a `[section]` header belongs to that section, not to the root.
Zenzic loads the root with `_build_from_data`, which filters against `ZenzicConfig.model_fields` — any key nested inside an unknown section is silently discarded.

**Wrong — all root fields after `[project]` are swallowed:**

```toml
[project]
name = "My Project"

# ❌ These lines look like root settings but they are INSIDE [project]
# Zenzic ignores them — the section is unknown
placeholder_patterns = []
docs_dir = "docs"
```

**Correct — all root fields BEFORE the first section header:**

```toml
# ✔ Root fields first
docs_dir = "docs"
placeholder_patterns = []
fail_under = 100

# ✔ Sub-table section last
[build_context]
engine = "zensical"
base_url = "/"
```

### Unknown Sections Emit a Warning {#unknown-sections}

Zenzic, Zenzic emits a `WARNING` when it encounters an unrecognised TOML section (e.g. `[project]`) instead of discarding it silently.
If you see:

```text
WARNING  .zenzic.toml: unknown section [project] will be ignored …
```

move all settings that follow that header to the top of the file, before any `[section]` tag.

### Dogfooding Pattern with Zensical/MkDocs {#dogfooding}

Documenting an integrity engine with its own analysis tool creates intentional false positives: pages that *explain* placeholder patterns will trigger the placeholder checker.
Disable the checker in the `.zenzic.toml` of the documentation repository:

```toml
# Doc repository — explains lint rules without triggering them
placeholder_patterns  = []   # disabled: this doc describes patterns by example
placeholder_max_words = 0    # disabled: glossary entries are intentionally short

[build_context]
engine = "zensical"
```
