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


# ── Infrastructure asset path extraction (Z404) ──────────────────────────────

_IMAGE_EXT_RE_ZENSICAL = re.compile(r"\.(?:png|jpg|jpeg|svg|gif|ico|webp)$", re.IGNORECASE)


def check_config_assets(repo_root: Path) -> list[tuple[str, str]]:
    """Check that theme assets declared in ``zensical.toml`` exist on disk.

    Checks ``[project].favicon`` and ``[project].logo`` (file-path values only).
    Both fields are resolved relative to ``[project].docs_dir`` (default: ``docs/``).

    Args:
        repo_root: Repository root (parent of ``zensical.toml``).

    Returns:
        List of ``(rel_path, message)`` tuples for each missing asset.
        Empty list when all referenced assets exist or the config is absent.
    """
    zensical_cfg = _load_zensical_config(repo_root)
    if not zensical_cfg:
        return []

    project = zensical_cfg.get("project") or {}
    if not isinstance(project, dict):
        return []

    docs_dir = str(project.get("docs_dir") or "docs")
    docs_root = repo_root / docs_dir

    issues: list[tuple[str, str]] = []

    for field_key in ("favicon", "logo"):
        value = project.get(field_key)
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
                    f"(declared as [project].{field_key}: '{value}' in zensical.toml) [Z404]",
                )
            )

    return issues


def _extract_nav_paths(items: object) -> set[str]:
    """Recursively extract ``.md`` file paths from nav-style structures.

    Handles nav variants used by both ``zensical.toml`` and ``mkdocs.yml``:

    * Plain string: ``"page.md"``
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
        return paths

    if isinstance(items, dict):
        for val in items.values():
            paths |= _extract_nav_paths(val)
        return paths

    if isinstance(items, list):
        for item in items:
            paths |= _extract_nav_paths(item)

    return paths


# ── Adapter ───────────────────────────────────────────────────────────────────


class ZensicalAdapter(BaseAdapter):
    """Adapter for the Zensical build engine.

    The adapter can be constructed from native ``zensical.toml`` config or from
    ``mkdocs.yml`` input while preserving Zensical routing/classification logic.
    Navigation is read from ``[project].nav`` (native) or ``nav`` (compat).

    Native ``zensical.toml`` example::

        [project]
        site_name = "My Docs"
        nav = [
            "index.md",
            {"Guide" = "guide.md"},
            {"API" = ["api/index.md", {"Endpoints" = "api/endpoints.md"}]},
        ]

    Locale information is sourced from ``[build_context]`` in ``.zenzic.toml``
    (the :class:`~zenzic.models.config.BuildContext`).  Zensical does not yet
    expose its own i18n configuration in ``zensical.toml``; when it does, this
    adapter will be updated to read it directly.

    Args:
        context: Build context from ``.zenzic.toml``.
        docs_root: Resolved absolute path to the ``docs/`` directory.
        zensical_config: Parsed config payload from the active input source.
        config_source: Internal source marker (``"zensical"`` or ``"mkdocs"``).
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
        """Return ``True`` if an anchor miss should be suppressed via i18n fallback.

        Locale configuration is sourced from ``BuildContext`` (``.zenzic.toml``).

        Args:
            resolved_file: Absolute path of the locale file whose anchor set
                does not contain *anchor*.
            anchor: Fragment identifier that was not found (without ``#``).
            anchors_cache: Pre-built ``Path`` → anchor slug set mapping.
            docs_root: Resolved absolute ``docs/`` root.

        Returns:
            ``True`` if the anchor exists in the default-locale equivalent file.
        """
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
        """Engine configuration files excluded from Z903."""
        if self._config_source == "mkdocs":
            return frozenset({"mkdocs.yml"})
        return frozenset({"zensical.toml"})

    @property
    def watched_config_files(self) -> frozenset[str]:
        """Return Zensical configuration filenames for LSP hot-reloading."""
        if self._config_source == "mkdocs":
            return frozenset({"mkdocs.yml", "mkdocs.yaml"})
        return frozenset({"zensical.toml"})

    # ── VSM integration ────────────────────────────────────────────────────────

    def _map_url(self, rel: Path) -> str:
        """Map a physical source path to its Zensical canonical URL.

        Zensical always serves clean directory-style URLs.  Both ``index.md``
        and ``README.md`` collapse to the parent directory URL (Zensical treats
        ``README.md`` as an implicit index).

        With ``use_directory_urls = true`` (default)::

            page.md        → /page/
            dir/index.md   → /dir/
            dir/README.md  → /dir/   (same URL → CONFLICT if both exist)
            index.md       → /

        With ``use_directory_urls = false``::

            page.md        → /page.html
            dir/index.md   → /dir/index.html
            index.md       → /index.html

        Files inside ``_private``-prefixed path segments are mapped normally
        here; ``_classify_route()`` marks them ``IGNORED``.

        Args:
            rel: Path of the source file relative to ``docs_root``.

        Returns:
            Canonical URL string with leading slash.
        """
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
        """Classify a Zensical route by filesystem and nav rules.

        Priority chain:

        1. ``IGNORED`` — any path segment starts with ``_``.
        2. ``ORPHAN_BUT_EXISTING`` — an explicit ``[project].nav`` is defined
           in ``zensical.toml`` and *rel* is not listed in it.  The file is
           served (Zensical is filesystem-based) but is not sidebar-navigable.
        3. ``REACHABLE`` — all other files when no explicit nav is declared.

        Args:
            rel:       Source path relative to ``docs_root``.
            nav_paths: Frozenset of nav-listed paths from ``get_nav_paths()``.

        Returns:
            ``'IGNORED'``, ``'ORPHAN_BUT_EXISTING'``, or ``'REACHABLE'``.
        """
        if any(part.startswith("_") for part in rel.parts):
            return "IGNORED"
        if self._has_explicit_nav and rel.as_posix() not in nav_paths:
            return "ORPHAN_BUT_EXISTING"
        return "REACHABLE"

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
