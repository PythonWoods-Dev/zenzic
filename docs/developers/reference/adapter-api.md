---

description: "Python API reference for Zenzic's public modules and classes."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# API Reference

Auto-generated reference documentation for all public modules in `zenzic`. This section is English-only, as the source docstrings are written in English.

---

## `zenzic.core.scanner`

Filesystem scanning utilities: repo root discovery, orphan page detection, asset tracking, and placeholder scanning.

### `find_repo_root(*, fallback_to_cwd: bool = False) -> Path` {#find_repo_root-fallback_to_cwd-bool--false---path}

Walks upward from the current working directory to discover the workspace root marker (`.git/` or `.zenzic.toml`). If `fallback_to_cwd` is `True`, returns the current working directory as the fallback root instead of raising a `RuntimeError` when no marker is found.

::: zenzic.core.scanner
    options:
      members:
        - find_config_file
        - find_orphans
        - find_placeholders
        - find_unused_assets
        - find_missing_directory_indices
        - calculate_orphans
        - calculate_unused_assets
        - check_placeholder_content
        - check_asset_references

---

## `zenzic.core.scorer`

Documentation quality scoring engine: weighted 0–100 score computation, snapshot persistence, and snapshot loading.

::: zenzic.core.scorer
    options:
      members:

        - compute_score
        - save_snapshot
        - load_snapshot
        - ScoreReport
        - CategoryScore

---

## `zenzic.core.validator`

Validation logic: broken link detection (engine-agnostic) and Python snippet syntax checking.

::: zenzic.core.validator
    options:
      members:

        - validate_links
        - validate_snippets
        - check_snippet_content
        - SnippetError

---

## `zenzic.models.config`

Configuration model.

::: zenzic.models.config
    options:
      members:

        - ZenzicConfig

---

## `BaseAdapter` Interface

The abstract base class for all engine adapters. Adapters translate engine-specific directory layouts, navigation schemes, and custom routing behaviors into the standardized vocabulary used by the validation core.

### Core Methods

This section details the specifications and guidelines for Core Methods within the Zenzic ecosystem.

#### `provides_index(self, directory_path: Path) -> bool`

Answers whether the engine auto-generates a browsable index for the directory (e.g., via `index.md` or a category metadata file). Used during missing index directory scans.

#### `get_nav_paths(self) -> frozenset[str]`

Returns the set of file paths reachable via the site's navigation UI, relative to the documentation root. Used to detect orphan pages.

#### `get_link_scheme_bypasses(self) -> frozenset[str]`

Returns a set of engine-specific URI schemes (e.g., `pathname`) to bypass the validator's standard absolute-path checks.

#### `get_route_info(self, rel: Path) -> RouteMetadata`

Constructs and returns routing metadata, including the canonical URL and route status (`REACHABLE`, `ORPHAN_BUT_EXISTING`, or `IGNORED`), for a given relative source file path.

#### `watched_config_files` (Property `-> frozenset[str]`)

Returns the set of framework configuration filenames (e.g., `mkdocs.yml`, `zensical.toml`) that dictate documentation structure. The Zenzic Language Server watches these files to trigger real-time VSM hot-reloading.

#### `dynamic_directories` (Property `-> set[Path]`)

Returns the set of absolute directory paths managed dynamically by framework plugins or engine runtime components (e.g., MkDocs Material blog post directories). This prevents false-positive `Z401` (`MISSING_DIRECTORY_INDEX`) findings on directories that lack a physical `index.md` on disk but are served dynamically by the framework at build time, eliminating the need for configuration suppressions in `.zenzic.toml`.

#### `use_directory_urls` (Property `-> bool`)

Declares the adapter routing mode for canonical page URLs. Return `True` for directory-style URLs (`/page/`), and `False` for flat HTML-style URLs (`/page.html`). The incremental engine forwards this value to VSM link canonicalization.


---

## `zenzic.rules` — Plugin SDK Façade

`zenzic.rules` is the stable, canonical entry point for plugin authors. It re-exports classes and helpers from `zenzic.core.rules`.

For step-by-step guides and packaging templates, see [Writing Plugin Rules](../how-to/write-plugin.md).

### Class and Type Definitions

| Name | Type | Purpose |
| :--- | :--- | :--- |
| `BaseRule` | `class` | Abstract base class for all plugin rules. Must subclass and implement `check`. |
| `run_rule` | `function` | Test helper to run a single rule against a Markdown string. |
| `RuleFinding` | `dataclass` | Finding object returned by `BaseRule.check()`. |
| `Severity` | `enum` | Enum values: `ERROR`, `WARNING`, `INFO`. |
| `Violation` | `alias` | Alias of `RuleFinding` (kept for backward compatibility). |
| `CustomRule` | `class` | TOML-declared rule engine (internal use only). |
