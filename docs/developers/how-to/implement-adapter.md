---

description: "Implement the BaseAdapter abstract base class to teach Zenzic about a new documentation engine."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Writing a Zenzic Adapter

This guide explains how to create a third-party adapter that teaches Zenzic to
understand your documentation engine's project layout, navigation structure, and
i18n conventions — without modifying Zenzic itself.

---

## What Is an Adapter

An **adapter** is a Python class that extends the `BaseAdapter` abstract base class
(`src/zenzic/core/adapters/_base.py`).  Zenzic's
scanner, orphan detector, and link validator talk exclusively to this interface —
they never import or call engine-specific code directly.

An adapter answers questions for each docs tree through a single API surface:

### Metadata-Driven Routing

| Method | Question |
|---|---|
| `get_route_info(rel)` | What is the canonical URL, route status, slug, and proxy flag for this source file? Returns a `RouteMetadata` instance. |

### Common Methods

| Method | Question |
|---|---|
| `is_locale_dir(part)` | Is this top-level directory a non-default locale? |
| `resolve_asset(missing_abs, docs_root)` | Does a default-locale fallback exist for this missing asset? |
| `resolve_anchor(resolved_file, anchor, anchors_cache, docs_root)` | Should this anchor miss be suppressed because the anchor exists in the default-locale equivalent? |
| `is_shadow_of_nav_page(rel, nav_paths)` | Is this file a locale mirror of a nav-listed page? |
| `get_ignored_patterns()` | Which filename globs should the orphan check skip? |
| `get_nav_paths()` | Which `.md` paths are listed in this engine's nav config? |
| `has_engine_config()` | Was a build-engine config file found on disk? (Controls orphan check activation.) |
| `provides_index(directory_path)` | Does this directory have an engine-provided landing page? (Controls `MISSING_DIRECTORY_INDEX` emission.) |

### URL Routing Mode (`use_directory_urls`)

To ensure the core engine correctly resolves relative links to HTML files, your adapter must declare its routing mode.

If your framework generates directory-style URLs (e.g., `file.md` becomes `/file/index.html` served at `/file/`), return `True`. If it generates flat files (e.g., `file.md` becomes `/file.html`), return `False`.

```python
@property
def use_directory_urls(self) -> bool:
    """Return True if the framework uses directory URLs, False for flat URLs."""
    return True
```

---

## Step 1 — Create the Adapter Class

```python title="my_engine_adapter/adapter.py"
# my_engine_adapter/adapter.py

from __future__ import annotations

from pathlib import Path
from typing import Any

from zenzic.core.adapters import RouteMetadata
from zenzic.core.adapters._base import BaseAdapter
from zenzic.models.vsm import RouteStatus

class MyEngineAdapter(BaseAdapter):
    """Adapter for MyEngine documentation projects."""

    def __init__(
        self,
        config: dict[str, Any],
        docs_root: Path,
    ) -> None:
        self._docs_root = docs_root
        self._config = config
        # Extract whatever your engine's config format provides.
        self._nav_paths: frozenset[str] = self._parse_nav()

    # ── BaseAdapter protocol ───────────────────────────────────────────────

    def is_locale_dir(self, part: str) -> bool:
        """Return True when *part* is a non-default locale directory.

        If your engine does not support i18n, always return False.
        """
        locales: list[str] = self._config.get("locales", [])
        return part in locales

    def resolve_asset(self, missing_abs: Path, docs_root: Path) -> Path | None:
        """Return the default-locale fallback path for a missing locale asset.

        If your engine does not support i18n asset fallback, always return None.
        """
        return None

    def resolve_anchor(
        self,
        resolved_file: Path,
        anchor: str,
        anchors_cache: dict[Path, set[str]],
        docs_root: Path,
    ) -> bool:
        """Return True if an anchor miss on a locale file should be suppressed.

        Called when a link points to a heading anchor that exists in the
        default-locale file but not in the locale translation (because
        headings are translated). Return True to suppress the false positive.

        If your engine does not support i18n, always return False.
        """
        return False

    def has_engine_config(self) -> bool:
        """Return True when a build-engine config was found and loaded.

        When False, the orphan check is skipped — with no nav information
        there is no reference set to compare the file list against.

        Return True if your adapter successfully loaded a config file.
        Return False only if no engine config exists (bare/standalone mode).
        """
        return bool(self._config)

    def is_shadow_of_nav_page(self, rel: Path, nav_paths: frozenset[str]) -> bool:
        """Return True when *rel* is a locale mirror of a nav-listed page.

        Example: docs/fr/guide/index.md shadows guide/index.md.
        If your engine does not support i18n, always return False.
        """
        if not rel.parts or not self.is_locale_dir(rel.parts[0]):
            return False
        default_rel = Path(*rel.parts[1:]).as_posix()
        return default_rel in nav_paths

    def get_ignored_patterns(self) -> set[str]:
        """Return glob patterns for files the orphan check should skip.

        For suffix-mode i18n plugins, return patterns like {'*.fr.md', '*.it.md'}.
        """
        return set()

    def get_nav_paths(self) -> frozenset[str]:
        """Return the set of .md paths listed in the engine's nav, relative to docs_root."""
        return self._nav_paths

    def get_metadata_files(self) -> frozenset[str]:
        """Return engine-owned metadata files to ignore in findings."""
        return frozenset({"myengine.toml"})

    @property
    def watched_config_files(self) -> frozenset[str]:
        """Return configuration filenames that trigger a VSM rebuild in LSP mode."""
        return frozenset({"myengine.toml"})


    def provides_index(self, directory_path: Path) -> bool:
        """Return whether this engine serves an index page for the directory."""
        index_rel = (directory_path / "index.md").as_posix().lstrip("/")
        return index_rel in self._nav_paths

    def get_extra_content_roots(self, repo_root: Path) -> list[Path]:
        """Return additional markdown roots outside docs_root."""
        return []

    def get_locale_source_roots(self, repo_root: Path) -> list[tuple[Path, str]]:
        """Return locale roots as (root_path, locale_label) tuples."""
        return []

    def get_absolute_url_prefixes(self, repo_root: Path | None = None) -> list[str]:
        """Return project-owned absolute URL prefixes."""
        return []

    # ── Metadata-Driven Routing ────────────────────────────────────────────

    def get_route_info(self, rel: Path) -> RouteMetadata:
        """Return unified routing metadata for a source file.

        The VSM builder calls this to construct RouteMetadata for every
        source file in a single pass.
        """
        posix = rel.as_posix()

        # Determine reachability from nav config.
        if posix in self._nav_paths:
            status: RouteStatus = "REACHABLE"
        else:
            status = "ORPHAN_BUT_EXISTING"

        # Compute canonical URL (adjust to your engine's routing rules).
        stem = rel.with_suffix("").as_posix()
        canonical_url = f"/{stem}/"

        return RouteMetadata(
            canonical_url=canonical_url,
            status=status,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _parse_nav(self) -> frozenset[str]:
        nav = self._config.get("nav", [])
        paths: set[str] = set()
        for entry in nav:
            if isinstance(entry, str) and entry.endswith(".md"):
                paths.add(entry.lstrip("/"))
        return frozenset(paths)
```

---

## Step 2 — Register via Entry Points

Zenzic discovers adapters through the `zenzic.adapters` entry-point group.
Register your adapter in your package's `pyproject.toml`:

```toml title="pyproject.toml"
[project.entry-points."zenzic.adapters"]
myengine = "my_engine_adapter.adapter:MyEngineAdapter"
```

The **key** (left of `=`) becomes the engine name users pass to `--engine` or
set as `engine` in `.zenzic.toml`:

```toml title=".zenzic.toml"
# In the user's .zenzic.toml
[build_context]
engine = "myengine"
```

---

## Step 3 — Implement the Factory Hook (Optional)

By default, Zenzic instantiates your adapter by calling:

```python
adapter_class(context, docs_root)
```

where `context` is a `BuildContext` instance.

If your adapter needs repository-aware config loading, implement
`from_repo(context, docs_root, repo_root)` and load engine config there.

If your adapter needs a different constructor signature, implement a
`from_repo(context, docs_root, repo_root)` classmethod and Zenzic will prefer it:

```python
@classmethod
def from_repo(
    cls,
    context: "BuildContext",
    docs_root: Path,
    repo_root: Path,
) -> "MyEngineAdapter":
    config_path = repo_root / "myengine.toml"
    config = {}
    if config_path.exists():
        import tomllib
        with config_path.open("rb") as f:
            config = tomllib.load(f)
    return cls(config, docs_root)
```

---

## Step 4 — Validate with Zenzic

After installing your package (`uv pip install -e .` or `pip install -e .`),
verify the adapter is discovered:

```bash
# List all installed adapters
zenzic check orphans --engine myengine --help

# Run against a real docs tree
zenzic check orphans --engine myengine
zenzic check all --engine myengine
```

---

## Step 5 — Custom Rules Are Engine-Independent

`[[custom_rules]]` in `.zenzic.toml` run on raw Markdown source and are
completely decoupled from the adapter layer.  A rule that searches for `DRAFT`
will fire identically whether the adapter is MkDocs, Zensical, or your own
engine.  No extra work is required to make custom rules compatible with a new
adapter.

---

## Step 6 — Declare Link-Scheme Bypasses (Optional) {#step-6-bypasses}

If your engine uses a non-standard URI scheme for internal links, implement
`get_link_scheme_bypasses()` to tell the Core which scheme names to exempt from
the Z105 absolute-path check and the unknown-scheme error (Rule R21 — Protocol
Sovereignty):

```python
def get_link_scheme_bypasses(self) -> frozenset[str]:
    """Return URI scheme names this engine uses legitimately.

    The validator adds ``<scheme>:`` to its skip list for each returned name,
    suppressing both the unknown-scheme warning and the Z105 absolute-path check
    for URLs that use that scheme.

    Return ``frozenset()`` if your engine has no special link-scheme bypass.
    """
    return frozenset()
```

Most engines return `frozenset()`. An engine might use custom link schemes to bypass routing (for example, to reference static assets that bypass the central router). The adapter registers these custom schemes to prevent the core engine from flagging them as absolute paths.

!!! info "Rule R21 — Protocol Sovereignty"
    The Core never hardcodes engine names. Engine-specific behaviour is declared in
    the adapter and queried by the Core via this method. Adding a new adapter that
    needs a link-scheme bypass requires **zero changes to `validator.py`**.

---

## Adapter Contract Guarantees

Your adapter must satisfy these invariants, or Zenzic's scanner may produce
incorrect results:

1. `get_route_info()` must return a `RouteMetadata` with a `canonical_url`

   that starts and ends with `/`.

2. `get_route_info()` must set `status` to one of `REACHABLE`,

   `ORPHAN_BUT_EXISTING`, or `IGNORED`.  Never return `CONFLICT` — that
   status is assigned later by `_detect_collisions()`.

3. `get_nav_paths()` returns paths **relative to `docs_root`**, using forward

   slashes, with no leading `/`.

4. `get_nav_paths()` returns only `.md` files (other extensions are ignored by

   the orphan checker).

5. `is_locale_dir()` must return `False` for the **default** locale.  Only

   non-default locale directories should return `True`.

6. All methods must be **pure**: same inputs always produce the same outputs.

   No I/O, no global-state mutation.

7. `resolve_asset()` must never raise — return `None` on any failure.
8. `resolve_anchor()` must never raise — return `False` on any failure.

   The `anchors_cache` argument is read-only; do not mutate it.

9. `has_engine_config()` must never raise — return `False` on any failure.
10. `provides_index(directory_path)` **is the only method permitted to do I/O**.

    It is called once per directory during the discovery phase — never inside
    per-link or per-file hot loops — so a single `Path.exists()` call is
    acceptable.  Return `True` if your engine will generate a landing page for
    the directory (e.g. via `index.md`, `README.md`, or a dynamic config entry
    like `_category_.json` with `"link": {"type": "generated-index"}`).  Never
    raise — return `False` on any I/O failure.

11. `get_link_scheme_bypasses()` must return a `frozenset[str]` of scheme names

    (without the trailing colon) — never `None`, never raise.  Return
    `frozenset()` if your engine has no special link-scheme bypass requirement.

12. `watched_config_files` must return a `frozenset[str]` of configuration

    filenames (e.g. `{"mkdocs.yml", "mkdocs.yaml"}`) that dictate documentation
    structure for LSP hot-reloading — never `None`, never raise.

---

### LSP Hot-Reloading (`watched_config_files`)

To support real-time updates in the Zenzic Language Server (VS Code), your adapter must declare which configuration files dictate the documentation structure (e.g., navigation trees).

When these files are modified by the user, the LSP server will automatically re-instantiate your adapter and rebuild the Virtual Site Map, clearing stale diagnostics like `Z103` (Orphan Link).

You must implement the `watched_config_files` property to return a `frozenset` of filenames:

```python
@property
def watched_config_files(self) -> frozenset[str]:
    """Return the configuration files that trigger a VSM rebuild in LSP mode."""
    return frozenset({"my-framework.yml", "my-framework.json"})
```

If your adapter does not rely on external configuration files (like the `StandaloneAdapter`), return an empty `frozenset()`.

---

## Testing Your Adapter

Use `zenzic.core.adapters.BaseAdapter` as the typing target in your tests to
verify protocol compliance:

```python
from zenzic.core.adapters import BaseAdapter
from my_engine_adapter.adapter import MyEngineAdapter

def test_satisfies_protocol() -> None:
    adapter = MyEngineAdapter(config={}, docs_root=Path("/tmp/docs"))
    assert isinstance(adapter, BaseAdapter)

def test_nav_paths_relative() -> None:
    adapter = MyEngineAdapter(
        config={"nav": ["index.md", "guide/setup.md"]},
        docs_root=Path("/tmp/docs"),
    )
    paths = adapter.get_nav_paths()
    assert "index.md" in paths
    assert "guide/setup.md" in paths
    assert all(not p.startswith("/") for p in paths)
```

---

## Concrete Implementation Examples: Zensical vs. Standalone

To see how these adapter methods are implemented in practice, here is a comparison between the engine-aware `ZensicalAdapter` and the zero-assumption `StandaloneAdapter`.

### `provides_index()` — Does this directory have a landing page

The Core calls `provides_index(directory_path)` once per directory during orphan detection. It answers: *"Will the engine generate a browsable index for this directory, so that files inside it are not structurally orphaned?"*

**`ZensicalAdapter.provides_index()`** — engine awareness:

```python
def provides_index(self, directory_path: Path) -> bool:
    # Physical index files — Zensical serves these directly.
    index_files = ("index.md", "README.md")
    return any((directory_path / f).exists() for f in index_files)
```

**`StandaloneAdapter.provides_index()`** — zero engine assumptions:

```python
def provides_index(self, directory_path: Path) -> bool:
    # No engine config — only a plain index.md signals a landing page.
    return (directory_path / "index.md").exists()
```

**Key difference:** `ZensicalAdapter` knows about both `index.md` and `README.md` because those are Zensical/MkDocs conventions. `StandaloneAdapter` makes no assumptions — it recognises only the universal `index.md` convention.

---

### `get_nav_paths()` — What files are discoverable

`get_nav_paths()` returns the set of file paths reachable via the site's navigation UI. A file absent from this set is a candidate for Z402 (`ORPHAN_BUT_EXISTING`).

**`ZensicalAdapter.get_nav_paths()`** — navigation extraction:

```python
def get_nav_paths(self) -> frozenset[str]:
    # Extracts all paths declared in the nav block
    return frozenset(self._nav_paths)
```

**`StandaloneAdapter.get_nav_paths()`** — intentionally empty:

```python
def get_nav_paths(self) -> frozenset[str]:
    """Empty frozenset — no engine config means no declared nav."""
    return frozenset()
```

When `get_nav_paths()` returns an empty frozenset, `get_route_info()` treats **all** files as `REACHABLE`. This is intentional: in Standalone mode there is no navigation contract, so orphan detection (Z402) is disabled.

---

### `get_link_scheme_bypasses()` — Engine-specific URI schemes

Rule R21 (Protocol Sovereignty) mandates that the Core never hardcodes engine names in validation logic. Engine-specific URI schemes are declared by the adapter and queried by the Core.

**`ZensicalAdapter.get_link_scheme_bypasses()`:**

```python
def get_link_scheme_bypasses(self) -> frozenset[str]:
    # Zensical uses standard links and has no special scheme bypasses.
    return frozenset()
```

**`StandaloneAdapter.get_link_scheme_bypasses()`:**

```python
def get_link_scheme_bypasses(self) -> frozenset[str]:
    """Standalone projects have no engine-specific link-scheme bypass."""
    return frozenset()
```

!!! info "Next Steps"
    Connect adapter code to deployment truth:

    1. Register engine identity in project configuration via `[build_context] engine`

       (see [Adapters & Engine Configuration](../../how-to/configure-adapter.md)).

    2. Validate adapter behavior under strict Zenzic policy:

       `zenzic check all --engine myengine --strict`.
       For run controls, see [CLI Commands: Global flags](../../reference/cli.md#global-flags).

    3. If your engine generates synthetic locale routes, explicitly map Ghost Route

       expectations against the VSM reference:
       [Core Mechanics — VSM](../../explanation/core-mechanics.md#vsm).
