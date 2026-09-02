---
description: Reference for .zenzic.toml and pyproject.toml configuration fields, types, defaults, and CLI overrides.
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration Reference

Zenzic is configured through a TOML file. Every field has a sensible default, so zero-config usage is fully supported -- but production projects benefit from explicit tuning.

!!! warning "The TOML Root Key Law"

    In TOML, once a `[table]` is declared, all subsequent keys belong to that table. You MUST declare all root-level keys (e.g., excluded_dirs, fail_under) at the absolute top of the .zenzic.toml file, before opening any bracketed sections like `[governance]` or `[network]`. Keys placed at the bottom will be silently swallowed by the preceding table and ignored by Zenzic.

---

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

When a config file is present but contains a TOML syntax error, Zenzic raises a `ZenzicConfigError` with a Rich-formatted message. It will **never** silently fall back to defaults when a file exists but cannot be parsed.

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

---

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

**Merge semantics**: most scalar fields follow last-write-wins — `.zenzic.local.toml`
loads after shared config, so a local value overrides the shared one. List fields
`forbidden_patterns` and `excluded_dirs` are the exception: they merge **additively**
(deduplicated) rather than replacing — a local entry extends the shared list, it
never removes from it (`config.py`'s `_apply_local_toml`).

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

!!! warning "Track 2 (`pyproject.toml`) provenance is not reported"
    `zenzic config explain` only reads `.zenzic.toml` directly for its "Global config" status line.
    A project configured exclusively via `[tool.zenzic]` in `pyproject.toml` will report
    `global: not found — using built-in defaults`, even though `zenzic check`/`score`/etc. did
    successfully load that configuration. Track 2 users should not rely on this command's
    provenance summary — the underlying values shown are still correct, only the reported
    *source* of a Track-2-only field is misleading.

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

### `max_sentence_length` {#max-sentence-length}

| | |
| :--- | :--- |
| **Type** | `int` |
| **Default** | `40` |

Maximum words allowed in a sentence before triggering `Z511` `EXCESSIVE_SENTENCE_LENGTH`.

```toml
max_sentence_length = 60
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

The default list:

```toml
# Default patterns (shown for reference — override to customise)
placeholder_patterns = [
  '\btodo\b', '\bfixme\b', '\bwip\b', '\btbd\b'
]
```

### `absolute_path_allowlist` {#absolute-path-allowlist}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Absolute path prefixes allowed in links — a match exempts the link from `Z105`. An entry never matched by any scanned link is reported as `Z110` `STALE_ALLOWLIST_ENTRY`.

```toml
absolute_path_allowlist = ["/api/"]
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

!!! warning "The security tier ignores this setting"
    Excluded directories are scoped out of *quality* analysis only. The **whole
    security tier** still runs on every file here — credentials and forbidden terms
    (`Z201`/`Z204`), forbidden schemes (`Z205`), and path traversal (`Z202`/`Z203`).
    Those findings are non-suppressible by any mechanism, including scoping, and
    `zenzic guard scan` scans these files too. Only System Guardrails and VCS-ignored
    content are outside the security scan.

**Path matching semantics:** If an entry contains a slash (`/`), it is evaluated against the repository-relative path. If it does not, it evaluates against the directory basename globally.

```toml
excluded_dirs = ["includes", "stylesheets", "overrides", "snippets"]
```

!!! info "System Guardrails (always excluded)"
    The following directories are excluded unconditionally, regardless of configuration:

    `.git`, `.github`, `_zenzic_core`, `.zenzic_cache`, `.venv`, `node_modules`, `.nox`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.hypothesis`, `build`, `dist`, `temp`, `.temp`, `tmp`, `mutants`, `out`, `.vscode-test`

    These represent the **L1 System Guardrails** layer (`SYSTEM_EXCLUDED_DIRS`). No configuration can override them.

### `excluded_file_patterns` {#excluded-file-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |

Filename glob patterns excluded from every **quality** check (orphan detection, placeholder scanning, reference pipeline). Uses glob syntax compiled to RE2 regular expressions — standard `*` and `?` wildcards are supported.

The security tier is **not** exempted — `Z201`/`Z204` (credentials and forbidden
terms), `Z205` (forbidden schemes) and `Z202`/`Z203` (path traversal) alike. A
matching file still gets the security pass, in `zenzic check`, `zenzic guard scan`
and the editor — the tier is non-suppressible by any mechanism, scoping included.

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
| **Type** | `Literal["prebuilt", "vsm", "mkdocs", "zensical", "standalone", "auto"]` |
| **Default** | `"auto"` |

Build engine identifier. Used by the adapter factory to select the correct path-resolution strategy. Built-in adapters: `prebuilt`, `vsm`, `mkdocs`, `zensical`, `standalone`.

When set to `"auto"` (the default), Zenzic probes the project root at runtime using **engine auto-discovery**, scanning for engine config files in priority order:

1. `.zenzic-vsm.json` → `prebuilt`
2. `zensical.toml` → `zensical`
3. `mkdocs.yml`/`mkdocs.yaml` with `theme: zensical` → `zensical` (compat)
4. `mkdocs.yml`/`mkdocs.yaml` → `mkdocs`
5. *(no match)* → `standalone`

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

### `offline_mode` {#offline-mode}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `false` |

When `true`, adapters force a flat URL structure (e.g. `use_directory_urls = false`) for offline builds.

```toml
[build_context]
offline_mode = true
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

### `baseline_stale_days` {#baseline-stale-days}

| | |
| :--- | :--- |
| **Type** | `int` (optional) |
| **Default** | `None` — falls back to Core's built-in default of `7` |

Age in days after which the saved score snapshot (`.zenzic-score.json`, written by `zenzic score --save`) is considered stale. `zenzic score --json` reports this as `baseline_status` (`"fresh"`, `"stale"`, or `"absent"` when no snapshot exists yet) and `baseline_age_days`, letting editor integrations (e.g. the VS Code Quality Status Panel) surface the signal without recomputing it.

```toml
baseline_stale_days = 14
```

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

The current release codename, shown in `zenzic --version` and related metadata output. It has no effect on Z601 detection — obsolete brand terms are declared separately via `governance.brand_obsolescence` (see below).

```toml
[project_metadata]
release_name = "Graphite"
```

### `obsolete_names_exclude_patterns` {#obsolete-names-exclude-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `["CHANGELOG*.md", "CHANGELOG*.archive.md"]` |
| **Section** | `[project_metadata]` |

Glob patterns, relative to `docs_dir`, for files exempt from `Z601` brand-obsolescence detection. Changelogs are excluded by default: a release history is expected to name superseded products in past-tense prose, and flagging it would penalise an accurate historical record.

Setting this to an empty list removes the exemption, so every file — changelogs included — is checked.

```toml
[project_metadata]
obsolete_names_exclude_patterns = ["CHANGELOG*.md", "docs/archive/**"]
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

**Pattern matching:** case-insensitive whole-word scan. The term `"Deprecated"` matches `"deprecated"` but not `"DeprecatedFeature"`.

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
    Zenzic automatically maintains configuration hygiene via the `GlobalUsageTracker`. If a pattern declared in `directory_policies`, `per_file_ignores`, `excluded_file_patterns`, or `excluded_external_urls` is never used to suppress an actual finding, Zenzic emits the **Z620** warning to prevent dead configuration accumulation. The solution is always to remove the unused policy from `.zenzic.toml`.

### `suppression_cap` {#suppression-cap}

| | |
| :--- | :--- |
| **Type** | `int` (`>= 0`) |
| **Default** | `30` |
| **Section** | `[governance]` |

Maximum number of active suppressions (inline `zenzic:ignore` comments plus `per_file_ignores` entries) allowed before the debt is considered excessive.

```toml
[governance]
suppression_cap = 50
```

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

## Repository Health {#doctor-settings}

Conventions read by [`zenzic doctor`](./cli.md) and [`zenzic adr new`](./cli.md). They are
configuration rather than constants because they differ per project: where decision records
live, how they are cited, where a redirects file sits.

!!! info "Public repository content only"
    Every `[doctor]` path resolves inside the published tree, and paths reaching into a
    gitignored directory (`.claude/`, `.human/`) are rejected at config load rather than
    merely discouraged. A check that inspected gitignored content would pass for whoever
    holds those files locally and be unrunnable in CI or a fresh clone — so `doctor`, like
    every other Zenzic check, reads public repository content only.

### `adr_vault_path` {#adr-vault-path}

Directory holding architectural decision records, relative to the repository root.

- **Default:** `"docs/developers/explanation/adr-vault"`
- Records are matched by filename against `adr_citation_pattern`.
- If the directory does not exist, `zenzic doctor` reports one actionable finding rather
  than a finding per citation.

### `adr_citation_pattern` {#adr-citation-pattern}

Regular expression matching an ADR citation in prose or source.

- **Default:** `"ADR-\\d{3}"`
- Compiled at config load; an invalid pattern is a configuration error, not a scan-time
  crash.
- The same pattern identifies both a citation in text and the record file that satisfies
  it, so a project using `RFC-0001` style needs only this one setting changed.

### `redirects_path` {#redirects-path}

Redirects file to structurally validate, relative to the repository root.

- **Default:** `"docs/_redirects"`
- Absence is not a finding — most projects have no redirects file.
- Each non-comment line must carry exactly three fields, a source beginning `/`, a
  destination beginning `/` or `http`, and a numeric status.

### `redirects_expected_blanks` {#redirects-expected-blanks}

Expected blank-line count in the redirects file.

- **Default:** `8`
- Blank lines belong only to the file's comment header, so an unexplained change in the
  count is a signal that something reshaped the file.
- Set to `0` to disable this check while keeping the structural validation.

---

## Policy-as-Code Settings {#policies-settings}

Configure declarative Policy-as-Code rules (`Z412`, `Z518`–`Z519`, `Z521`–`Z523`, `Z610`–`Z619`). All policy rules are **opt-in** and inactive by default — empty lists/dicts (`[]`/`{}`) short-circuit evaluation in $O(1)$ time with zero performance overhead.

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

### `forbidden_frontmatter_keys` {#forbidden-frontmatter-keys}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z612 `FORBIDDEN_FRONTMATTER_KEY` |
| **Opt-in** | **Yes** |

Declarative list of forbidden YAML frontmatter keys. Every Markdown file in the documentation graph must not contain any of these keys in its leading `---` frontmatter block. Zenzic emits Z612 for each present forbidden key per file.

```toml
[policies]
forbidden_frontmatter_keys = ["draft", "internal_notes"]
```

### `frontmatter_schema_match` {#frontmatter-schema-match}

| | |
| :--- | :--- |
| **Type** | `dict[str, str]` |
| **Default** | `{}` |
| **Section** | `[policies]` |
| **Finding** | Z613 `FRONTMATTER_SCHEMA_MISMATCH` |
| **Opt-in** | **Yes** |

Dictionary mapping frontmatter key names to required RE2 regular expression pattern strings. If a key is present in a file's frontmatter and its string value fails to match the specified pattern, Zenzic emits a Z613 error finding.

```toml
[policies.frontmatter_schema_match]
version = "^v\\d+\\.\\d+\\.\\d+$"
```

### `allowed_external_domains` {#allowed-external-domains}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z614 `UNAPPROVED_DOMAIN_REFERENCE` |
| **Opt-in** | **Yes** |

Zero-Trust whitelist of allowed external domain prefixes. When non-empty, ANY external link pointing to a domain not in this whitelist emits a Z614 error finding.

```toml
[policies]
allowed_external_domains = ["zenzic.dev", "github.com"]
```

### `required_url_schemes` {#required-url-schemes}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z615 `FORBIDDEN_URL_SCHEME` |
| **Opt-in** | **Yes** |

Whitelist of permitted URL scheme protocols (e.g., `["https", "mailto"]`). Any link using a scheme not listed in this whitelist emits a Z615 warning finding.

```toml
[policies]
required_url_schemes = ["https", "mailto"]
```

### `cross_namespace_restrictions` {#cross-namespace-restrictions}

| | |
| :--- | :--- |
| **Type** | `dict[str, list[str]]` |
| **Default** | `{}` |
| **Section** | `[policies]` |
| **Finding** | Z616 `CROSS_NAMESPACE_LINK_FORBIDDEN` |
| **Opt-in** | **Yes** |

Dictionary mapping source namespace path prefixes to a list of forbidden target namespace path prefixes. Internal links crossing restricted boundaries emit a Z616 error finding.

```toml
[policies.cross_namespace_restrictions]
"docs/public" = ["docs/internal"]
```

### `forbidden_content_patterns` {#forbidden-content-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z617 `FORBIDDEN_CONTENT_PATTERN` |
| **Opt-in** | **Yes** |

List of RE2 regular expression patterns forbidden from appearing anywhere in a document's prose content. A match anywhere in the body emits a Z617 warning finding.

```toml
[policies]
forbidden_content_patterns = ["\\bTODO\\b", "\\bFIXME\\b", "\\bconfidential\\b"]
```

### `required_heading_patterns` {#required-heading-patterns}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z618 `REQUIRED_HEADING_PATTERN` |
| **Opt-in** | **Yes** |

List of RE2 regular expression patterns, each of which must match at least one heading in the document. A pattern with zero matching headings emits a Z618 warning finding.

```toml
[policies]
required_heading_patterns = ["^Overview$", "^License$"]
```

### `max_document_complexity` {#max-document-complexity}

| | |
| :--- | :--- |
| **Type** | `int` |
| **Default** | `0` |
| **Section** | `[policies]` |
| **Finding** | Z619 `MAX_DOCUMENT_COMPLEXITY` |
| **Opt-in** | **Yes** (`0` disables the check) |

Maximum allowed document complexity score, computed from word count, heading depth, and link density. Documents exceeding this threshold emit a Z619 warning finding.

```toml
[policies]
max_document_complexity = 500
```

### `weasel_words` {#weasel-words}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z519 `WEASEL_WORDS` |
| **Opt-in** | **Yes** |

List of weasel words to flag in prose. Each occurrence emits a Z519 warning finding.

```toml
[policies]
weasel_words = ["clearly", "simply", "obviously", "basically", "very"]
```

### `enable_passive_voice_check` {#enable-passive-voice-check}

| | |
| :--- | :--- |
| **Type** | `bool` |
| **Default** | `false` |
| **Section** | `[policies]` |
| **Finding** | Z518 `PASSIVE_VOICE_DETECTED` |
| **Opt-in** | **Yes** |

When `true`, enables heuristic passive-voice detection in prose. Detected sentences emit a Z518 warning finding.

```toml
[policies]
enable_passive_voice_check = true
```

### `required_table_columns` {#required-table-columns}

| | |
| :--- | :--- |
| **Type** | `dict[str, list[str]]` |
| **Default** | `{}` |
| **Section** | `[policies]` |
| **Finding** | Z521 `REQUIRED_TABLE_COLUMN` |
| **Opt-in** | **Yes** |

Dictionary mapping a heading/context pattern (or `"*"` for every table in the document) to a list of column header names that table must contain. A missing column emits a Z521 warning finding, reported at the table's own line.

```toml
[policies.required_table_columns]
"*" = ["Status", "Description"]
"^API Reference$" = ["Method", "Endpoint"]
```

### `table_cell_enums` {#table-cell-enums}

| | |
| :--- | :--- |
| **Type** | `dict[str, list[str]]` |
| **Default** | `{}` |
| **Section** | `[policies]` |
| **Finding** | Z522 `TABLE_CELL_ENUM` |
| **Opt-in** | **Yes** |

Dictionary mapping a column header name to the list of string values allowed in that column. Matching is case-insensitive; a cell value outside the whitelist emits a Z522 warning finding at the precise data-row line.

```toml
[policies.table_cell_enums]
Status = ["draft", "review", "stable"]
```

### `required_heading_order` {#required-heading-order}

| | |
| :--- | :--- |
| **Type** | `list[str]` |
| **Default** | `[]` |
| **Section** | `[policies]` |
| **Finding** | Z523 `HEADING_ORDER_VIOLATION` |
| **Opt-in** | **Yes** |

List of RE2 regular expression heading patterns that must appear in the document in strictly ascending sequential order. A heading matching an earlier pattern appearing after one matching a later pattern emits a Z523 warning finding.

```toml
[policies]
required_heading_order = ["^Overview$", "^Usage$", "^API Reference$"]
```

### `traceability_targets` {#traceability-targets}

| | |
| :--- | :--- |
| **Type** | `dict[str, list[str]]` |
| **Default** | `{}` |
| **Section** | `[policies]` |
| **Finding** | Z412 `TRACEABILITY_BROKEN` |
| **Opt-in** | **Yes** |

Dictionary mapping a target documentation glob pattern to a list of source documentation glob patterns that must link to it. A target document with no inbound link from any matching source emits a Z412 warning finding. Unlike the other policies on this page, Z412 is a graph-level finding that cannot be suppressed with an inline `<!-- zenzic:ignore -->` comment — see [Suppression Policy](suppression-policy.md) — it is governed only through `[governance] directory_policies`.

```toml
[policies.traceability_targets]
"docs/specs/**" = ["docs/architecture/**"]
```

---

## Custom Rules {#custom-rules}

Project-specific lint rules. Each entry is either a regex pattern applied line-by-line to every `.md` file, or a `class_name` reference to a Python class for AST-level analysis (Custom Rule SDK v3).

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
| `id` | `str \| None` | `None` | Stable unique identifier, must start with `"ZZ-"` (e.g. `"ZZ-NOINTERNAL"`) |
| `pattern` | `str \| None` | `None` | Regex applied to each content line (regex-flavor rules only) |
| `message` | `str \| None` | `None` | Human-readable explanation shown in findings (regex-flavor rules only) |
| `severity` | `str` | `"error"` | `"error"`, `"warning"`, or `"info"` |
| `class_name` | `str \| None` | `None` | Dotted import path to a Custom Rule SDK v3 class for AST-level rules (mutually exclusive with `pattern`) |

None of the fields are enforced as required at the schema level — a regex-flavor entry missing `id`, `pattern`, or `message` is silently skipped by the scanner rather than raising a load-time error.

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

# Repository health (zenzic doctor) — every value shown is the default
[doctor]
adr_vault_path = "docs/developers/explanation/adr-vault"
adr_citation_pattern = "ADR-\\d{3}"
redirects_path = "docs/_redirects"
redirects_expected_blanks = 8

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
Zenzic actively defends against this: before loading, it scans every table (including unrecognized
ones) for any of ~20 known root-level field names. If a root field name is found nested inside a
table, Zenzic raises a **fatal** `ZenzicConfigError` and refuses to load — it does not silently
discard the value.

**Wrong — this raises a fatal error, it does not silently ignore the misplaced fields:**

```toml
[project]
name = "My Project"

# ❌ These lines look like root settings but they are INSIDE [project].
# Zenzic detects this and raises:
#   FATAL CONFIGURATION ERROR: The root key 'docs_dir' was found inside
#   the '[project]' section. In TOML, root keys must be declared at the
#   absolute top of the file before any [tables] are opened.
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

### Unrecognized Sections With No Swallowed Root Key Emit a Warning {#unknown-sections}

An unrecognized TOML section (e.g. `[project]`) whose keys do **not** collide with any known
root-level field name is not fatal — Zenzic emits a `WARNING` and ignores that section's contents.
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
