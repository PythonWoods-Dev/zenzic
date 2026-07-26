# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""ZensicalAdapter — authoritative adapter for the Zensical build engine.

The adapter always enforces Zensical routing semantics. Configuration input can
come from either ``zensical.toml`` (native) or ``mkdocs.yml`` (compat input)
without changing the adapter class.

Native ``zensical.toml`` layout::

    [project]
    site_name = "My Docs"
    docs_dir  = "docs"
    nav = [
        "index.md",
        {"Guide" = "guide.md"},
        {"API" = [
            "api/index.md",
            {"Endpoints" = "api/endpoints.md"},
        ]},
    ]
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from zenzic.core import regex as re


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # PEP 680 backport
from typing import TYPE_CHECKING, Any

from zenzic.core.adapters._base import BaseAdapter
from zenzic.core.adapters._mkdocs_config import find_mkdocs_config_file, load_mkdocs_config
from zenzic.core.adapters._utils import case_sensitive_exists, remap_to_default_locale
from zenzic.core.exceptions import ZenzicConfigError
from zenzic.models.config import BuildContext


_log = logging.getLogger(__name__)

_UNSUPPORTED_MKDOCS_KEYS = {
    "remote_branch",
    "remote_name",
    "exclude_docs",
    "draft_docs",
    "not_in_nav",
    "validation",
    "strict",
    "hooks",
    "watch",
}


if TYPE_CHECKING:
    from zenzic.core.adapters._base import RouteMetadata
    from zenzic.models.vsm import RouteStatus


# ── Config discovery & loading ────────────────────────────────────────────────


def find_zensical_config(repo_root: Path) -> Path | None:
    """Return the Zensical native config file path, or ``None`` if absent."""
    zensical_toml = repo_root / "zensical.toml"
    return zensical_toml if zensical_toml.exists() else None


def _load_zensical_config(repo_root: Path) -> dict[str, Any]:
    """Load and parse ``zensical.toml``, returning ``{}`` on any failure."""
    config_file = find_zensical_config(repo_root)
    if config_file is None:
        return {}
    try:
        with config_file.open("rb") as f:
            return tomllib.load(f)
    except Exception:  # noqa: BLE001
        return {}


# ── Infrastructure asset path extraction (Z404 & Z405) ──────────────────────

_IMAGE_EXT_RE_ZENSICAL = re.compile(r"\.(?:png|jpg|jpeg|svg|gif|ico|webp)$", re.IGNORECASE)


def _extract_config_declared_assets(doc_config: dict[str, Any]) -> set[str]:
    """Extract theme favicon, logo, extra_css, extra_javascript relative asset paths."""
    assets: set[str] = set()

    # Native zensical.toml format
    project = doc_config.get("project") or {}
    if isinstance(project, dict):
        for key in ("favicon", "logo"):
            val = project.get(key)
            if val and isinstance(val, str) and not val.startswith(("http://", "https://")):
                assets.add(val.lstrip("/"))

    # mkdocs.yml format (compat mode)
    theme = doc_config.get("theme") or {}
    if isinstance(theme, dict):
        for key in ("favicon", "logo"):
            val = theme.get(key)
            if val and isinstance(val, str) and not val.startswith(("http://", "https://")):
                assets.add(val.lstrip("/"))

    for key in ("extra_css", "extra_javascript"):
        items = doc_config.get(key) or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and not item.startswith(("http://", "https://")):
                    assets.add(item.lstrip("/"))

    return assets


def check_config_assets(repo_root: Path) -> list[tuple[str, str]]:
    """Check that theme assets declared in ``zensical.toml`` or ``mkdocs.yml`` exist on disk.

    Checks ``favicon`` and ``logo`` (file-path values only).
    Both fields are resolved relative to ``docs_dir`` (default: ``docs/``).

    Args:
        repo_root: Repository root (parent of config file).

    Returns:
        List of ``(rel_path, message)`` tuples for each missing asset.
        Empty list when all referenced assets exist or the config is absent.
    """
    config_file = find_zensical_config(repo_root)
    if config_file is not None:
        cfg = _load_zensical_config(repo_root)
        config_src = "zensical"
    elif find_mkdocs_config_file(repo_root) is not None:
        cfg = load_mkdocs_config(repo_root)
        config_src = "mkdocs"
    else:
        return []

    if config_src == "zensical":
        project = cfg.get("project") or {}
        docs_dir = str(project.get("docs_dir") or "docs") if isinstance(project, dict) else "docs"
        docs_root = repo_root / docs_dir
        theme_dict = project if isinstance(project, dict) else {}
    else:
        docs_dir = str(cfg.get("docs_dir") or "docs")
        docs_root = repo_root / docs_dir
        theme_dict = cfg.get("theme") or {}
        if not isinstance(theme_dict, dict):
            theme_dict = {}

    issues: list[tuple[str, str]] = []

    for field_key in ("favicon", "logo"):
        value = theme_dict.get(field_key)
        if not value or not isinstance(value, str):
            continue
        if not _IMAGE_EXT_RE_ZENSICAL.search(value):
            continue
        asset_path = docs_root / value.lstrip("/")
        if not asset_path.exists():
            rel = f"{docs_dir}/{value.lstrip('/')}"
            issues.append(
                (
                    rel,
                    f"{field_key} asset not found on disk: '{rel}' "
                    f"(declared as {field_key}: '{value}') [Z404]",
                )
            )

    return issues


def _extract_nav_paths(items: object) -> set[str]:
    """Recursively extract ``.md`` file paths from nav-style structures.

    Handles nav variants used by both ``zensical.toml`` and ``mkdocs.yml``:

    * Plain string: ``"page.md"``
    * Directory entry: ``"section/"`` → expands to ``"section/index.md"``
    * Titled page: ``{"Title" = "page.md"}``
    * Section:      ``{"Section" = ["page.md", …]}``
    * External URL: ``{"GitHub" = "https://…"}``  — skipped.

    Args:
        items: Nav payload (list/dict/string) from the active config source.

    Returns:
        Set of ``.md`` paths, relative to ``docs_root``, without leading slash.
    """
    paths: set[str] = set()
    if isinstance(items, str):
        if items.endswith(".md"):
            paths.add(items.lstrip("/"))
        elif items.endswith("/"):
            paths.add(f"{items.lstrip('/')}index.md")
        return paths

    if isinstance(items, dict):
        for val in items.values():
            paths |= _extract_nav_paths(val)
        return paths

    if isinstance(items, list):
        for item in items:
            paths |= _extract_nav_paths(item)

    return paths


def _extract_blog_dir_zensical(doc_config: dict[str, Any]) -> str | None:
    """Extract blog posts prefix when a blog plugin is active in Zensical/MkDocs config."""
    plugins = doc_config.get("plugins") or []
    if isinstance(plugins, list):
        for item in plugins:
            if isinstance(item, str) and item in ("blog", "material/blog"):
                return "blog/posts"
            elif isinstance(item, dict):
                for name, cfg in item.items():
                    if name in ("blog", "material/blog"):
                        blog_dir = (
                            cfg.get("blog_dir", "blog") if isinstance(cfg, dict) else "blog"
                        )
                        return f"{blog_dir.strip('/')}/posts"
    return None


# ── Adapter ───────────────────────────────────────────────────────────────────


class ZensicalAdapter(BaseAdapter):
    """Adapter for the Zensical build engine.

    The adapter can be constructed from native ``zensical.toml`` config or from
    ``mkdocs.yml`` input while preserving Zensical routing/classification logic.
    Navigation is read from ``[project].nav`` (native) or ``nav`` (compat).
    """

    def __init__(
        self,
        context: BuildContext,
        docs_root: Path,
        zensical_config: dict[str, Any] | None = None,
        *,
        config_source: str = "zensical",
    ) -> None:
        self._docs_root = docs_root
        self._zensical_config: dict[str, Any] = (
            zensical_config if zensical_config is not None else {}
        )
        self._config_source = config_source
        # Locale configuration sourced entirely from BuildContext (.zenzic.toml).
        self._locale_dirs: frozenset[str] = frozenset(context.locales)
        self._fallback_to_default: bool = context.fallback_to_default

        if self._config_source == "mkdocs":
            _project = self._zensical_config
        else:
            _project = self._zensical_config.get("project", {})
        if not isinstance(_project, dict):
            _project = {}

        # Pre-compute nav state from active config source.
        _raw_nav = _project.get("nav", [])
        self._nav_paths: frozenset[str] = frozenset(_extract_nav_paths(_raw_nav))
        # True only when the user supplied an explicit, non-empty nav list.
        self._has_explicit_nav: bool = bool(_raw_nav)
        self._blog_posts_prefix: str | None = _extract_blog_dir_zensical(self._zensical_config)

        # Offline Mode Tactical Fix
        if context.offline_mode:
            self._use_directory_urls = False
        else:
            self._use_directory_urls = bool(_project.get("use_directory_urls", True))

    # ── Public contract ────────────────────────────────────────────────────────

    def is_locale_dir(self, part: str) -> bool:
        """Return ``True`` when *part* is a non-default locale directory name."""
        return part in self._locale_dirs

    def resolve_asset(self, missing_abs: Path, docs_root: Path) -> Path | None:
        """Return the default-locale fallback for a missing asset, or ``None``."""
        if not self._fallback_to_default:
            return None
        fallback = remap_to_default_locale(missing_abs, docs_root, self._locale_dirs)
        return fallback if fallback is not None and case_sensitive_exists(fallback) else None

    def resolve_anchor(
        self,
        resolved_file: Path,
        anchor: str,
        anchors_cache: dict[Path, set[str]],
        docs_root: Path,
    ) -> bool:
        """Return ``True`` if an anchor miss should be suppressed via i18n fallback."""
        if not self._fallback_to_default:
            return False
        default_file = remap_to_default_locale(resolved_file, docs_root, self._locale_dirs)
        if default_file is None:
            return False
        return anchor.lower() in anchors_cache.get(default_file, set())

    def is_shadow_of_nav_page(self, rel: Path, nav_paths: frozenset[str]) -> bool:
        """Return ``True`` when *rel* is a locale-mirror of a nav-listed page."""
        default_abs = remap_to_default_locale(
            self._docs_root / rel, self._docs_root, self._locale_dirs
        )
        if default_abs is None:
            return False
        return default_abs.relative_to(self._docs_root).as_posix() in nav_paths

    def get_ignored_patterns(self) -> set[str]:
        """Empty set — Zensical does not use MkDocs suffix-mode i18n patterns."""
        return set()

    def has_engine_config(self) -> bool:
        """``True`` — adapter is instantiated only when a supported config exists."""
        return True

    def get_metadata_files(self) -> frozenset[str]:
        """Engine configuration and infrastructure asset files excluded from Z405/Z903."""
        names: set[str] = (
            {"mkdocs.yml"} if self._config_source == "mkdocs" else {"zensical.toml"}
        )
        config_assets = _extract_config_declared_assets(self._zensical_config)
        names.update(config_assets)
        return frozenset(names)

    @property
    def watched_config_files(self) -> frozenset[str]:
        """Return Zensical configuration filenames for LSP hot-reloading."""
        if self._config_source == "mkdocs":
            return frozenset({"mkdocs.yml", "mkdocs.yaml"})
        return frozenset({"zensical.toml"})

    # ── VSM integration ────────────────────────────────────────────────────────

    def _map_url(self, rel: Path) -> str:
        """Map a physical source path to its Zensical canonical URL.

        Non-Markdown asset files (e.g. ``.png``, ``.webp``, ``.svg``) preserve
        their exact relative path and file extension.
        """
        from zenzic.core.discovery import DOC_SUFFIXES

        if rel.suffix.lower() not in DOC_SUFFIXES:
            return "/" + rel.as_posix()

        if not self._use_directory_urls:
            # Flat URL mode: preserve suffix, no directory collapsing.
            return "/" + rel.as_posix()

        stem = rel.with_suffix("")
        parts = list(stem.parts)
        if not parts:
            return "/"
        if parts[-1] in ("index", "README"):
            parts = parts[:-1]
        if not parts:
            return "/"
        return "/" + "/".join(parts) + "/"

    def _classify_route(self, rel: Path, nav_paths: frozenset[str]) -> RouteStatus:
        """Classify a Zensical route by filesystem, asset type, and nav rules."""
        from zenzic.core.discovery import DOC_SUFFIXES

        rel_posix = rel.as_posix()

        # 1. Private directory segments starting with '_'
        if any(part.startswith("_") for part in rel.parts):
            return "IGNORED"

        # 2. Non-Markdown static assets are served directly — always REACHABLE
        if rel.suffix.lower() not in DOC_SUFFIXES:
            return "REACHABLE"

        # 3. Root/directory index pages (index.md or README.md at root)
        if rel_posix in ("index.md", "README.md"):
            return "REACHABLE"

        # 4. Listed in nav or locale shadow
        if not self._has_explicit_nav or rel_posix in nav_paths or self.is_shadow_of_nav_page(rel, nav_paths):
            return "REACHABLE"

        # 5. Blog plugin dynamic routes
        if self._blog_posts_prefix and rel_posix.startswith(f"{self._blog_posts_prefix}/"):
            return "REACHABLE"

        return "ORPHAN_BUT_EXISTING"


    def get_nav_paths(self) -> frozenset[str]:
        """Return ``.md`` paths from ``[project].nav`` in ``zensical.toml``.

        Supports all supported nav variants — plain strings, titled
        pages, nested sections (see :func:`_extract_nav_paths`).

        Returns:
            Frozenset of nav-listed ``.md`` paths, relative to ``docs_root``
            and without leading slash.  Empty frozenset when no explicit
            ``[project].nav`` is declared.
        """
        return self._nav_paths

    def get_route_info(self, rel: Path) -> RouteMetadata:
        """Return unified routing metadata for a Zensical source file.

        Zensical does not support frontmatter ``slug:`` — the slug field is
        always ``None``.  Files under ``_private/`` directories are ``IGNORED``.
        """
        from zenzic.core.adapters._base import RouteMetadata

        nav_paths = self.get_nav_paths()
        return RouteMetadata(
            canonical_url=self._map_url(rel),
            status=self._classify_route(rel, nav_paths),
        )

    def provides_index(self, directory_path: Path) -> bool:
        """Return ``True`` when Zensical will serve an index page for this directory.

        Zensical uses ``index.md`` as the canonical index file for a directory,
        rendering it at the directory URL without a filename suffix.

        I/O is permitted here — this method is called once per directory during
        the discovery phase, never inside per-link or per-file hot loops.

        Args:
            directory_path: Absolute path to the directory to inspect.

        Returns:
            ``True`` if an ``index.md`` exists in the directory.
        """
        return (directory_path / "index.md").exists()

    def get_link_scheme_bypasses(self) -> frozenset[str]:
        """Zensical has no engine-specific link-scheme bypass."""
        return frozenset()

    def get_extra_content_roots(self, repo_root: Path) -> list[Path]:  # noqa: ARG002
        """Zensical does not define additional content roots outside docs_dir."""
        return []

    def get_locale_source_roots(self, repo_root: Path) -> list[tuple[Path, str]]:  # noqa: ARG002
        """Zensical locale roots are currently declared inside docs_dir."""
        return []

    def get_absolute_url_prefixes(self, repo_root: Path | None = None) -> list[str]:  # noqa: ARG002
        """Zensical is single-instance and exports no absolute URL prefixes."""
        return []

    @classmethod
    def from_repo(
        cls,
        context: BuildContext,
        docs_root: Path,
        repo_root: Path,
    ) -> ZensicalAdapter:
        """Construct from a live repository root.

        Resolution order:

        1. ``zensical.toml`` (native source)
        2. ``mkdocs.yml`` (compat input, Zensical semantics preserved)
        """
        if find_zensical_config(repo_root) is not None:
            return cls(
                context,
                docs_root,
                _load_zensical_config(repo_root),
                config_source="zensical",
            )

        if find_mkdocs_config_file(repo_root) is not None:
            mkdocs_config = load_mkdocs_config(repo_root)
            # Warn about unsupported keys
            for key in _UNSUPPORTED_MKDOCS_KEYS:
                if key in mkdocs_config:
                    _log.warning(
                        "Zensical ignores MkDocs '%s' parameter — it will not affect the build.",
                        key,
                    )

            return cls(
                context,
                docs_root,
                mkdocs_config,
                config_source="mkdocs",
            )

        raise ZenzicConfigError(
            "engine 'zensical' declared in .zenzic.toml but no configuration file was found",
            context={
                "repo_root": str(repo_root),
                "hint": "create zensical.toml (or provide mkdocs.yml as compat input)",
            },
        )
