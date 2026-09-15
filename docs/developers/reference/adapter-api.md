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

### `find_repo_root(*, fallback_to_cwd: bool = False, search_from: Path | None = None) -> Path` {#find_repo_root-fallback_to_cwd-bool--false---path}

Walks upward from `search_from` (or the current working directory) to discover the workspace root marker — any of `.git/`, `.zenzic.toml`, `zensical.toml`, or `mkdocs.yml`. If `fallback_to_cwd` is `True`, returns the starting path as the fallback root instead of raising a `RuntimeError` when no marker is found.

::: zenzic.core.scanner
    options:
      members:
        - find_orphans
        - find_unused_assets
        - find_missing_directory_indices
        - calculate_orphans
        - calculate_unused_assets
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

All 14 abstract methods below **must** be implemented by every adapter; the engine
raises `TypeError` at construction time otherwise. 4 additional members
(`get_link_scheme_bypasses`, `dynamic_directories`, `use_directory_urls`,
`watched_config_files`) have default implementations and are optional to override.
See [Adapter Contract Guarantees](../how-to/implement-adapter.md#adapter-contract-guarantees)
for the full behavioral invariants each method must satisfy.

#### `is_locale_dir(self, part: str) -> bool`

Returns `True` when `part` is a non-default locale directory name. Must return `False`
for the default locale — only non-default locale directories should return `True`.

#### `resolve_asset(self, missing_abs: Path, docs_root: Path) -> Path | None`

Returns the default-locale fallback path for a missing locale asset, or `None` if no
fallback exists (or the engine has no i18n asset fallback).

#### `resolve_anchor(self, resolved_file: Path, anchor: str, anchors_cache: dict[Path, set[str]], docs_root: Path) -> bool`

Returns `True` when an anchor miss on a locale file should be suppressed because the
anchor exists in the default-locale equivalent (headings are translated).

#### `is_shadow_of_nav_page(self, rel: Path, nav_paths: frozenset[str]) -> bool`

Returns `True` when `rel` is a locale mirror of a nav-listed page (e.g.
`docs/fr/guide/index.md` shadowing `guide/index.md`).

#### `get_ignored_patterns(self) -> set[str]`

Returns glob patterns for files the orphan check should skip (e.g. suffix-mode i18n
plugin files like `*.fr.md`).

#### `get_nav_paths(self) -> frozenset[str]`

Returns the set of file paths reachable via the site's navigation UI, relative to the
documentation root. Used to detect orphan pages.

#### `has_engine_config(self) -> bool`

Returns `True` when a build-engine config was found and loaded. When `False`, the
orphan check is skipped — with no nav information there is no reference set to
compare the file list against.

#### `get_metadata_files(self) -> frozenset[str]`

Returns engine-owned metadata filenames excluded from quality findings.

#### `get_route_info(self, rel: Path) -> RouteMetadata`

Constructs and returns routing metadata, including the canonical URL and route status (`REACHABLE`, `ORPHAN_BUT_EXISTING`, or `IGNORED`), for a given relative source file path.

#### `provides_index(self, directory_path: Path) -> bool`

Answers whether the engine auto-generates a browsable index for the directory (e.g., via `index.md` or a category metadata file). Used during missing index directory scans. The only method permitted to do I/O.

#### `get_extra_content_roots(self, repo_root: Path) -> list[Path]`

Returns additional markdown content roots outside `docs_root` (e.g. MkDocs
monorepo-plugin extra doc trees).

#### `get_locale_source_roots(self, repo_root: Path) -> list[tuple[Path, str]]`

Returns locale source roots as `(root_path, locale_label)` pairs.

#### `get_absolute_url_prefixes(self, repo_root: Path | None = None) -> list[str]`

Returns project-owned absolute URL prefixes, for `Z105` allowlisting.

#### `get_entry_points(self, vsm: VirtualSiteMap) -> list[str]`

Returns canonical URLs serving as root entry points for reachability analysis (e.g. the
homepage, or every route when there is no nav tree).

#### `get_link_scheme_bypasses(self) -> frozenset[str]`

Returns a set of engine-specific URI schemes (e.g., `pathname`) to bypass the validator's standard absolute-path checks. Optional — defaults to `frozenset()`.

#### `watched_config_files` (Property `-> frozenset[str]`)

Returns the set of framework configuration filenames (e.g., `mkdocs.yml`, `zensical.toml`) that dictate documentation structure. The Zenzic Language Server watches these files to trigger real-time VSM hot-reloading. Optional — defaults to `frozenset()`.

#### `dynamic_directories` (Property `-> set[Path]`)

Returns the set of absolute directory paths managed dynamically by framework plugins or engine runtime components (e.g., MkDocs Material blog post directories). This prevents false-positive `Z401` (`MISSING_DIRECTORY_INDEX`) findings on directories that lack a physical `index.md` on disk but are served dynamically by the framework at build time, eliminating the need for configuration suppressions in `.zenzic.toml`. Optional — defaults to `set()`.

#### `use_directory_urls` (Property `-> bool`)

Declares the adapter routing mode for canonical page URLs. Return `True` for directory-style URLs (`/page/`), and `False` for flat HTML-style URLs (`/page.html`). The incremental engine forwards this value to VSM link canonicalization. Optional — defaults to `True`.

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
