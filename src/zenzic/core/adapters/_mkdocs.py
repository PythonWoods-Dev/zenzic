# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""MkDocsAdapter — adapter for MkDocs folder-mode and suffix-mode i18n.

MkDocs YAML/config parsing is provided by ``_mkdocs_config`` and reused by
both ``MkDocsAdapter`` and ``ZensicalAdapter``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zenzic.core import regex as re
from zenzic.core.adapters._base import BaseAdapter
from zenzic.core.adapters._mkdocs_config import (
    _PermissiveYamlLoader as _PermissiveYamlLoader,  # noqa: F401
    find_mkdocs_config_file,
    load_mkdocs_config,
    load_mkdocs_config_file,
)
from zenzic.core.adapters._utils import case_sensitive_exists, dedupe_roots, remap_to_default_locale
from zenzic.core.exceptions import ZenzicConfigError
from zenzic.models.config import BuildContext


_log = logging.getLogger(__name__)


if TYPE_CHECKING:
    from zenzic.core.adapters._base import RouteMetadata
    from zenzic.models.vsm import RouteStatus, VirtualSiteMap


def _iter_plugins(doc_config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return normalized plugin declarations from list or mapping syntax.

    MkDocs supports both:
    - list syntax: ``plugins: [search, {i18n: {...}}]``
    - mapping syntax: ``plugins: {search: {}, i18n: {...}}``
    """
    raw = doc_config.get("plugins", [])
    normalized: list[tuple[str, dict[str, Any]]] = []

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                normalized.append((item, {}))
                continue
            if isinstance(item, dict):
                for name, cfg in item.items():
                    normalized.append((name, cfg if isinstance(cfg, dict) else {}))
        return normalized

    if isinstance(raw, dict):
        for name, cfg in raw.items():
            normalized.append((name, cfg if isinstance(cfg, dict) else {}))

    return normalized


def _iter_path_like_values(value: Any) -> list[str]:
    """Extract path-like string values from nested plugin config structures."""
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_iter_path_like_values(item))
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "config", "file", "include", "includes"}:
                out.extend(_iter_path_like_values(item))
        return out
    return out


def _iter_monorepo_include_paths(doc_config: dict[str, Any]) -> list[str]:
    """Extract include-config paths from monorepo-style MkDocs plugins."""
    includes: list[str] = []
    for name, plugin_cfg in _iter_plugins(doc_config):
        if "monorepo" not in name.lower():
            continue
        for key in ("include", "includes", "configs", "projects", "paths"):
            if key not in plugin_cfg:
                continue
            includes.extend(_iter_path_like_values(plugin_cfg[key]))

    nav = doc_config.get("nav")
    if isinstance(nav, list):
        for item in nav:
            if isinstance(item, str) and item.startswith("!include"):
                parts = item.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    includes.append(parts[1].strip())
            elif isinstance(item, dict):
                include_val = item.get("!include")
                if isinstance(include_val, str) and include_val.strip():
                    includes.append(include_val.strip())

    return includes


def _candidate_include_configs(include_path: Path) -> list[Path]:
    """Return candidate mkdocs config files for an include path."""
    if include_path.suffix.lower() in {".yml", ".yaml"}:
        return [include_path]
    if include_path.is_dir():
        return [include_path / "mkdocs.yml", include_path / "mkdocs.yaml"]
    return [include_path / "mkdocs.yml", include_path / "mkdocs.yaml"]


def _discover_monorepo_docs_roots(config_file: Path) -> list[Path]:
    """Recursively discover docs_dir roots from included MkDocs configs."""
    discovered: list[Path] = []
    visited: set[Path] = set()

    def _walk(config_path: Path) -> None:
        resolved_config = config_path.resolve()
        if resolved_config in visited or not resolved_config.is_file():
            return
        visited.add(resolved_config)

        cfg = _load_doc_config_file(resolved_config)
        docs_dir = str(cfg.get("docs_dir") or "docs")
        docs_root = (resolved_config.parent / docs_dir).resolve()
        if docs_root.is_dir():
            discovered.append(docs_root)

        for include in _iter_monorepo_include_paths(cfg):
            include_path = (resolved_config.parent / include).resolve()
            for candidate in _candidate_include_configs(include_path):
                if candidate.is_file():
                    _walk(candidate)

    _walk(config_file)
    return dedupe_roots(discovered)


# ── Config discovery & loading ────────────────────────────────────────────────


def find_config_file(repo_root: Path) -> Path | None:
    """Return the MkDocs config file path, or ``None`` if absent."""
    return find_mkdocs_config_file(repo_root)


def _load_doc_config_file(config_file: Path) -> dict[str, Any]:
    """Load and parse a specific MkDocs config file path."""
    return load_mkdocs_config_file(config_file)


def _load_doc_config(repo_root: Path) -> dict[str, Any]:
    """Load and parse ``mkdocs.yml``, returning ``{}`` on any failure."""
    return load_mkdocs_config(repo_root)


# ── Infrastructure asset path extraction (Z404) ──────────────────────────────

_IMAGE_EXT_RE_MKDOCS = re.compile(r"\.(png|jpg|jpeg|svg|gif|ico|webp)$", re.IGNORECASE)


def check_config_assets(repo_root: Path) -> list[tuple[str, str]]:
    """Check that theme assets declared in ``mkdocs.yml`` exist on disk.

    Checks ``theme.favicon`` and ``theme.logo`` (file-path values only).
    Both fields are resolved relative to ``docs_dir`` (MkDocs default: ``docs/``).
    Icon-name values (e.g. ``material/library``) are silently skipped because
    they reference bundled theme icons, not local files.

    No YAML re-parsing beyond what ``_load_doc_config`` already does.
    No disk I/O in hot-path loops — only two existence checks at most.

    Args:
        repo_root: Repository root (parent of ``mkdocs.yml``).

    Returns:
        List of ``(rel_path, message)`` tuples for each missing asset.
        Empty list when all referenced assets exist or the config is absent.
    """
    doc_config = _load_doc_config(repo_root)
    if not doc_config:
        return []

    docs_dir = str(doc_config.get("docs_dir") or "docs")
    docs_root = repo_root / docs_dir

    theme = doc_config.get("theme") or {}
    if not isinstance(theme, dict):
        # theme: readthedocs  (scalar shorthand) — no file paths possible
        return []

    issues: list[tuple[str, str]] = []

    for field_key, config_key in [("favicon", "theme.favicon"), ("logo", "theme.logo")]:
        value = theme.get(field_key)
        if not value or not isinstance(value, str):
            continue
        # Skip icon names (e.g. "material/cloud") — they have no image extension.
        if not _IMAGE_EXT_RE_MKDOCS.search(value):
            continue
        asset_path = docs_root / value.lstrip("/")
        if not asset_path.exists():
            rel = f"{docs_dir}/{value.lstrip('/')}"
            issues.append(
                (
                    rel,
                    f"{field_key} asset not found on disk: '{rel}' "
                    f"(declared as {config_key}: '{value}' in mkdocs.yml) [Z404]",
                )
            )

    return issues


# ── i18n plugin extraction helpers ───────────────────────────────────────────


def _extract_i18n_locale_patterns(doc_config: dict[str, Any]) -> set[str]:
    """Return filename glob patterns for non-default i18n locales (suffix mode).

    Reads the ``mkdocs-i18n`` plugin block and returns patterns like
    ``{'*.it.md', '*.fr.md'}`` when ``docs_structure: suffix`` is active.
    Returns an empty set for any other configuration (no plugin, folder
    structure, etc.).

    Only valid ISO 639-1 two-letter lowercase codes produce patterns.
    Version tags (``v1``), build tags (``beta``), and BCP 47 region codes
    are silently rejected.
    """
    patterns: set[str] = set()
    for name, i18n_config in _iter_plugins(doc_config):
        if name != "i18n":
            continue
        if i18n_config.get("docs_structure") != "suffix":
            break
        for lang in i18n_config.get("languages") or []:
            if not isinstance(lang, dict):
                continue
            if not lang.get("default", False):
                locale = lang.get("locale", "")
                # ISO 639-1: exactly two lowercase ASCII letters.
                if locale and re.fullmatch(r"[a-z]{2}", locale):
                    patterns.add(f"*.{locale}.md")
        break
    return patterns


def _extract_i18n_locale_dirs(doc_config: dict[str, Any]) -> set[str]:
    """Return locale directory names for non-default i18n locales (folder mode).

    Reads the ``mkdocs-i18n`` plugin block and returns directory names like
    ``{'it', 'fr'}`` when ``docs_structure: folder`` is active.

    Returns an empty set for any other configuration (no plugin, suffix
    structure, missing locale list, etc.).

    Args:
        doc_config: Parsed documentation generator config (e.g. from mkdocs.yml).

    Returns:
        Set of non-default locale directory names, e.g. ``{'it', 'fr'}``.
    """
    dirs: set[str] = set()
    for name, i18n_config in _iter_plugins(doc_config):
        if name != "i18n":
            continue
        if i18n_config.get("docs_structure") != "folder":
            break
        for lang in i18n_config.get("languages") or []:
            if not isinstance(lang, dict):
                continue
            if not lang.get("default", False):
                locale = lang.get("locale", "")
                if locale:
                    dirs.add(locale)
        break
    return dirs


def _extract_i18n_reconfigure_material(doc_config: dict[str, Any]) -> bool:
    """Return ``True`` when the i18n plugin has ``reconfigure_material: true``.

    When this flag is active, ``mkdocs-material`` auto-generates the language
    switcher and the alternate-locale entry points (e.g. ``/it/``) at build
    time.  These routes are **not** listed in ``nav:`` or ``extra.alternate``
    and must therefore be treated as auto-generated REACHABLE routes in the
    VSM — otherwise Zenzic would flag the locale index pages as orphans.

    Only meaningful when ``docs_structure: folder`` is active; returns
    ``False`` for suffix mode and for configs that omit the setting (the
    plugin default is ``false``).

    Args:
        doc_config: Parsed documentation generator config (e.g. from mkdocs.yml).

    Returns:
        ``True`` when ``reconfigure_material: true`` is set on the i18n plugin
        block with ``docs_structure: folder``; ``False`` otherwise.
    """
    for name, i18n_config in _iter_plugins(doc_config):
        if name != "i18n":
            continue
        if i18n_config.get("docs_structure") != "folder":
            return False
        return bool(i18n_config.get("reconfigure_material", False))
    return False


def _detect_redundant_alternate(doc_config: dict[str, Any]) -> bool:
    """Return ``True`` when ``reconfigure_material: true`` and ``extra.alternate`` coexist.

    This combination is redundant: ``reconfigure_material`` delegates the
    language switcher to the i18n plugin, which auto-generates it from the
    ``languages`` list.  A manual ``extra.alternate`` block then competes with
    the auto-generated switcher and causes the switcher to disappear in some
    plugin versions.

    This is a pure diagnostic helper — it reads only the already-parsed config
    dict and has no side effects.

    Args:
        doc_config: Parsed documentation generator config (e.g. from mkdocs.yml).

    Returns:
        ``True`` when both ``reconfigure_material: true`` and ``extra.alternate``
        are present; ``False`` otherwise.
    """
    if not _extract_i18n_reconfigure_material(doc_config):
        return False
    alternate = doc_config.get("extra", {})
    if not isinstance(alternate, dict):
        return False
    return bool(alternate.get("alternate"))


def _extract_i18n_fallback_to_default(doc_config: dict[str, Any]) -> bool:
    """Return the ``fallback_to_default`` value from the i18n plugin block.

    Returns ``True`` (the plugin default) when the setting is absent or
    the plugin block cannot be found.
    """
    for name, i18n_config in _iter_plugins(doc_config):
        if name != "i18n":
            continue
        return bool(i18n_config.get("fallback_to_default", True))
    return True


def _extract_blog_dir(doc_config: dict[str, Any]) -> str | None:
    """Return the blog posts prefix when the ``material/blog`` plugin is active.

    The ``material/blog`` plugin (``mkdocs-material``) dynamically generates
    all routes under ``<blog_dir>/posts/`` at build time — these files are
    **never** listed in the static ``nav:`` section of ``mkdocs.yml``.  The
    MkDocs adapter must treat them as ``REACHABLE`` rather than
    ``ORPHAN_BUT_EXISTING``; otherwise Zenzic raises Z103 for every internal
    link that targets a blog post.

    Args:
        doc_config: Parsed ``mkdocs.yml`` config dict.

    Returns:
        The relative ``<blog_dir>/posts/`` prefix (e.g. ``"blog/posts"``) when
        the blog plugin is active; ``None`` when the plugin is absent.
    """
    for name, blog_cfg in _iter_plugins(doc_config):
        # Accept both short form ``blog`` and fully-qualified ``material/blog``.
        if name not in ("blog", "material/blog"):
            continue
        blog_dir = blog_cfg.get("blog_dir", "blog") if isinstance(blog_cfg, dict) else "blog"
        # Normalise: strip leading/trailing slashes so the prefix is always
        # a plain relative posix string like "blog/posts".
        blog_dir = blog_dir.strip("/")
        return f"{blog_dir}/posts"
    return None


def _validate_i18n_fallback_config(doc_config: dict[str, Any]) -> None:
    """Raise ConfigurationError when fallback_to_default is true but no default locale exists.

    Only active for ``docs_structure: folder`` with ``fallback_to_default: true``.
    No-op for suffix mode, unconfigured projects, or when a default locale is present.

    Raises:
        :class:`~zenzic.core.exceptions.ConfigurationError`: When the i18n plugin
            requires fallback but cannot determine the fallback target locale.
    """
    for name, i18n in _iter_plugins(doc_config):
        if name != "i18n":
            continue
        if i18n.get("docs_structure") != "folder":
            break
        if not i18n.get("fallback_to_default", False):
            break
        default_locale = ""
        locale_dirs: set[str] = set()
        for lang in i18n.get("languages") or []:
            if not isinstance(lang, dict):
                continue
            locale = lang.get("locale", "")
            if not locale:
                continue
            if lang.get("default", False):
                default_locale = locale
            else:
                locale_dirs.add(locale)
        if not locale_dirs and not default_locale:
            break
        if not default_locale:
            raise ZenzicConfigError(
                "i18n plugin has fallback_to_default: true but no language with "
                "default: true — Zenzic cannot determine the fallback target locale.",
                context={"docs_structure": "folder", "fallback_to_default": True},
            )
        break


# ── Nav traversal ─────────────────────────────────────────────────────────────


def _collect_nav_paths(nav: list[Any] | dict[str, Any] | str | None, acc: set[str]) -> None:
    """Recursively walk the mkdocs nav structure and collect all .md paths."""
    if nav is None:
        return
    if isinstance(nav, str):
        acc.add(nav)
        return
    if isinstance(nav, dict):
        for value in nav.values():
            if isinstance(value, str):
                acc.add(value)
            else:
                _collect_nav_paths(value, acc)
        return
    if isinstance(nav, list):
        for item in nav:
            _collect_nav_paths(item, acc)


# ── Adapter ───────────────────────────────────────────────────────────────────


class MkDocsAdapter(BaseAdapter):
    """Adapter for MkDocs folder-mode and suffix-mode i18n.

    In folder mode every non-default locale lives in a top-level directory
    under ``docs/`` whose name equals the locale code (e.g. ``docs/it/``).
    In suffix mode, translated pages are named ``page.it.md`` alongside the
    default ``page.md``.

    Assets are **shared** — ``docs/it/index.md`` may reference
    ``assets/logo.svg`` intending ``docs/assets/logo.svg`` (the build engine
    resolves them relative to the site root, not the locale sub-tree).

    Args:
        context: :class:`~zenzic.models.config.BuildContext` loaded from
            ``.zenzic.toml``.  Provides ``locales`` and ``default_locale``.
            When ``context.locales`` is empty the adapter falls back to
            extracting locale information from *doc_config*.
        docs_root: Resolved absolute path to the ``docs/`` directory.
        doc_config: Pre-parsed documentation generator config dict (e.g. the
            contents of ``mkdocs.yml``).  When provided and
            ``context.locales`` is empty, locale dirs and fallback behaviour
            are derived from this config rather than hard-coded defaults.
    """

    def __init__(
        self,
        context: BuildContext,
        docs_root: Path,
        doc_config: dict[str, Any] | None = None,
        *,
        config_file_found: bool = False,
        repo_root: Path | None = None,
    ) -> None:
        self._docs_root = docs_root
        self._context = context
        self._repo_root = repo_root
        self._doc_config: dict[str, Any] = doc_config if doc_config is not None else {}
        self._config_file_found: bool = config_file_found

        # Validate i18n fallback configuration eagerly so callers get a clear
        # ConfigurationError rather than silent misbehaviour at link-check time.
        _validate_i18n_fallback_config(self._doc_config)

        # Locales: prefer explicit context (from .zenzic.toml); fall back to
        # extraction from the engine config (mkdocs.yml) when absent.
        if context.locales:
            self._locale_dirs: frozenset[str] = frozenset(context.locales)
            self._fallback_to_default: bool = context.fallback_to_default
        else:
            self._locale_dirs = frozenset(_extract_i18n_locale_dirs(self._doc_config))
            self._fallback_to_default = _extract_i18n_fallback_to_default(self._doc_config)

        # When reconfigure_material: true the Material theme auto-generates
        # the language switcher and the locale entry points (e.g. /it/) at
        # build time.  These routes never appear in nav: so classify_route()
        # must treat locale index pages as REACHABLE without nav evidence.
        self._reconfigure_material: bool = _extract_i18n_reconfigure_material(self._doc_config)

        # When the material/blog plugin is active, every .md file under
        # <blog_dir>/posts/ is a live, published route generated dynamically by
        # the plugin — not a static nav entry.  Store the posts prefix so that
        # _classify_route() can recognise and mark them REACHABLE.
        self._blog_posts_prefix: str | None = _extract_blog_dir(self._doc_config)

        # Emit a UX hint when the config is redundant: reconfigure_material
        # auto-generates the switcher, so extra.alternate is both unnecessary
        # and harmful (it competes with the plugin and can hide the switcher).
        if _detect_redundant_alternate(self._doc_config):
            _log.warning(
                "mkdocs.yml: 'extra.alternate' is redundant when "
                "'plugins.i18n.reconfigure_material: true' is set. "
                "The i18n plugin auto-generates the language switcher from the "
                "'languages' list — remove 'extra.alternate' to avoid routing "
                "conflicts that can cause the language switcher to disappear."
            )

    # ── Public contract ────────────────────────────────────────────────────────

    def is_locale_dir(self, part: str) -> bool:
        """Return ``True`` when *part* is a non-default locale directory name."""
        return part in self._locale_dirs

    def resolve_asset(self, missing_abs: Path, docs_root: Path) -> Path | None:
        """Return the default-locale fallback for a missing asset, or ``None``.

        When a file inside a locale sub-tree (e.g. ``docs/it/``) references
        an asset using a path that resolves to ``docs/it/assets/logo.svg``
        (which does not exist), this method checks whether the corresponding
        default-locale path ``docs/assets/logo.svg`` exists and returns it.

        Args:
            missing_abs: Absolute path that was not found on disk.
            docs_root: Resolved absolute ``docs/`` root (for path stripping).

        Returns:
            Resolved absolute :class:`~pathlib.Path` of the fallback asset, or
            ``None`` if no fallback exists.
        """
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

        When a locale file (e.g. ``docs/it/architecture.md``) exists but does
        not contain the requested anchor — because its headings are translated —
        this method checks whether the anchor exists in the default-locale
        equivalent (e.g. ``docs/architecture.md``).  If it does, MkDocs will
        serve the default-locale page for this anchor, so the error is spurious.

        The check is pure: only ``anchors_cache`` (already in memory) is
        consulted.  No disk I/O occurs.

        Args:
            resolved_file: Absolute path of the locale file that was found but
                whose anchor set does not contain *anchor*.
            anchor: The fragment identifier that was not found (without ``#``).
            anchors_cache: Pre-built mapping of absolute ``Path`` → anchor slug
                set (same mapping used by :class:`~zenzic.core.resolver.InMemoryPathResolver`).
            docs_root: Resolved absolute ``docs/`` root (for path stripping).

        Returns:
            ``True`` if the anchor exists in the default-locale equivalent file;
            ``False`` otherwise.
        """
        if not self._fallback_to_default:
            return False
        default_file = remap_to_default_locale(resolved_file, docs_root, self._locale_dirs)
        if default_file is None:
            return False
        return anchor.lower() in anchors_cache.get(default_file, set())

    def is_shadow_of_nav_page(self, rel: Path, nav_paths: frozenset[str]) -> bool:
        """Return ``True`` when *rel* is a locale-mirror of a nav-listed page.

        A file ``it/about/index.md`` is a shadow of ``about/index.md``.  If
        ``about/index.md`` appears in the nav the shadow is not an orphan —
        it inherits its nav membership from the default-locale original.

        Args:
            rel: Path of the candidate file, relative to ``docs_root``.
            nav_paths: Frozenset of ``.md`` paths listed in the nav.

        Returns:
            ``True`` when the file is a shadow of a nav-listed page.
        """
        default_abs = remap_to_default_locale(
            self._docs_root / rel, self._docs_root, self._locale_dirs
        )
        if default_abs is None:
            return False
        return default_abs.relative_to(self._docs_root).as_posix() in nav_paths

    def get_ignored_patterns(self) -> set[str]:
        """Return filename glob patterns for non-default locale files (suffix mode)."""
        return _extract_i18n_locale_patterns(self._doc_config)

    def get_nav_paths(self) -> frozenset[str]:
        """Return ``.md`` paths listed in the nav, relative to ``docs_root``.

        MkDocs resolves directory nav entries (e.g. ``blog/``) to their
        implicit ``index.md`` (e.g. ``blog/index.md``) at build time.  We
        mirror that resolution here so that plugin-managed index pages such as
        ``blog/index.md`` are correctly classified as ``REACHABLE`` instead of
        ``ORPHAN_BUT_EXISTING``.
        """
        raw: set[str] = set()
        _collect_nav_paths(self._doc_config.get("nav"), raw)
        nav_paths: set[str] = set()
        for p in raw:
            p = p.lstrip("/")
            if p.endswith(".md"):
                nav_paths.add(p)
            elif p.endswith("/"):
                # MkDocs resolves 'section/' → 'section/index.md' automatically.
                nav_paths.add(f"{p}index.md")
        return frozenset(nav_paths)

    def has_engine_config(self) -> bool:
        """``True`` when ``mkdocs.yml`` was found on disk **or** locales were declared.

        Returns ``False`` only when both the engine config file is absent
        **and** no locales were declared in ``.zenzic.toml`` — the truly bare
        scenario where the adapter has no nav or i18n information to contribute.
        """
        return self._config_file_found or bool(self._locale_dirs)

    def get_metadata_files(self) -> frozenset[str]:
        """MkDocs configuration files — excluded from Z405/Z903."""
        names: set[str] = {"mkdocs.yml"}
        plugin_names = {name for name, _ in _iter_plugins(self._doc_config)}
        if "awesome-pages" in plugin_names or "mkdocs-awesome-pages-plugin" in plugin_names:
            names.add(".pages")
        return frozenset(names)

    @property
    def use_directory_urls(self) -> bool:
        """Return MkDocs URL mode from config/offline context."""
        if getattr(self._context, "offline_mode", False):
            return False
        return bool(self._doc_config.get("use_directory_urls", True))

    @property
    def watched_config_files(self) -> frozenset[str]:
        """Return MkDocs configuration filenames for LSP hot-reloading."""
        return frozenset({"mkdocs.yml", "mkdocs.yaml"})

    # ── VSM integration ────────────────────────────────────────────────────────

    def _map_url(self, rel: Path) -> str:
        """Map a physical source path to its MkDocs canonical URL.

        Applies the MkDocs ``use_directory_urls`` rule (default ``true``):

        * ``page.md``           → ``/page/``
        * ``dir/index.md``      → ``/dir/``
        * ``dir/README.md``     → ``/dir/``       (same URL as index.md → CONFLICT)
        * ``index.md``          → ``/``           (root)
        * ``page.md`` (no-dir)  → ``/page.html``

        Non-Markdown static assets (e.g. ``.jpg``, ``.png``, ``.css``) are
        served at their exact path — ``use_directory_urls`` does not apply.

        The Double-Index case (``index.md`` **and** ``README.md`` coexist in
        the same directory) produces two routes with the identical URL, which
        ``_detect_collisions()`` will mark as ``CONFLICT``.

        Args:
            rel: Path of the source file relative to ``docs_root``.

        Returns:
            Canonical URL string (always starts and ends with ``/``).
        """
        from zenzic.core.discovery import DOC_SUFFIXES

        if rel.suffix.lower() not in DOC_SUFFIXES:
            return "/" + rel.as_posix()

        if getattr(self._context, "offline_mode", False):
            use_dir = False
        else:
            use_dir = self._doc_config.get("use_directory_urls", True)
        stem = rel.with_suffix("")
        parts = list(stem.parts)
        if not parts:
            return "/"
        # index.md and README.md both collapse to the parent directory URL
        if parts[-1] in ("index", "README"):
            parts = parts[:-1]
        if not parts:
            return "/"
        if use_dir:
            return "/" + "/".join(parts) + "/"
        return "/" + "/".join(parts) + ".html"

    def _classify_route(self, rel: Path, nav_paths: frozenset[str]) -> RouteStatus:
        """Classify a MkDocs route as REACHABLE, ORPHAN_BUT_EXISTING, or IGNORED.

        Classification rules (in priority order):

        0. No nav declared (``nav_paths`` empty) → all files ``REACHABLE``
           (MkDocs auto-includes every page when ``nav:`` is absent), except
           ``README.md`` which is always ``IGNORED``.
        1. ``README.md`` **not** listed in nav → ``IGNORED``.
        2. File in nav_paths (or is a locale shadow of a nav page) → ``REACHABLE``.
        3. ``reconfigure_material: true`` and file is a top-level locale entry
           point (e.g. ``it/index.md``) → ``REACHABLE`` (auto-generated route).
           This check fires only when rules 0-2 have not already resolved the
           status, so an explicit nav entry for ``it/index.md`` is never
           overridden.
        3b. ``material/blog`` plugin active and file is under ``<blog_dir>/posts/``
            → ``REACHABLE``.  Blog posts are dynamically indexed by the plugin and
            are never listed in the static ``nav:``; they are published, reachable
            pages and must not be classified as orphans.
        4. Otherwise → ``ORPHAN_BUT_EXISTING``.

        Args:
            rel:       Source path relative to ``docs_root``.
            nav_paths: Nav-listed ``.md`` paths from ``get_nav_paths()``.

        Returns:
            ``RouteStatus`` literal (never ``'CONFLICT'``).
        """
        rel_posix = rel.as_posix()

        from zenzic.core.discovery import DOC_SUFFIXES

        if rel.suffix.lower() not in DOC_SUFFIXES:
            return "REACHABLE"

        # When no nav is declared in mkdocs.yml, MkDocs auto-includes every
        # page — equivalent to every file being REACHABLE.  Only README.md
        # is still excluded (MkDocs never auto-promotes it).
        if not nav_paths:
            if rel.name == "README.md":
                return "IGNORED"
            return "REACHABLE"

        # README.md not in nav → IGNORED (MkDocs does not auto-promote it)
        if rel.name == "README.md" and rel_posix not in nav_paths:
            return "IGNORED"

        if rel_posix in nav_paths:
            return "REACHABLE"

        # Locale shadows inherit their nav membership from the default locale
        if self.is_shadow_of_nav_page(rel, nav_paths):
            return "REACHABLE"

        # When reconfigure_material: true, the Material theme auto-generates
        # the language switcher and synthetic entry points for every non-default
        # locale (e.g. docs/it/index.md → /it/).  These pages are never listed
        # in nav: but they are live routes — mark them REACHABLE so Zenzic does
        # not report them as orphans.
        if self._reconfigure_material and rel.name in ("index.md", "README.md"):
            parts = rel.parts
            if len(parts) == 2 and parts[0] in self._locale_dirs:  # e.g. it/index.md
                return "REACHABLE"

        # material/blog plugin: every .md under <blog_dir>/posts/ is a live,
        # dynamically-indexed page — never listed in nav: but always REACHABLE.
        if self._blog_posts_prefix and rel_posix.startswith(f"{self._blog_posts_prefix}/"):
            return "REACHABLE"

        return "ORPHAN_BUT_EXISTING"

    def get_route_info(self, rel: Path) -> RouteMetadata:
        """Return unified routing metadata for a MkDocs source file.

        Delegates to ``_map_url()`` and ``_classify_route()`` internally,
        wrapping the results in :class:`RouteMetadata`.

        MkDocs does not support frontmatter ``slug:`` — the slug field is
        always ``None``.  Locale entry points auto-generated by
        ``reconfigure_material`` are marked ``is_proxy=True``.
        """
        from zenzic.core.adapters._base import RouteMetadata

        nav_paths = self.get_nav_paths()
        canonical_url = self._map_url(rel)
        status = self._classify_route(rel, nav_paths)

        # Detect proxy routes: reconfigure_material auto-generates locale
        # entry points that have no physical nav entry.
        is_proxy = False
        if self._reconfigure_material and rel.name in ("index.md", "README.md"):
            parts = rel.parts
            if len(parts) == 2 and parts[0] in self._locale_dirs:
                is_proxy = True

        return RouteMetadata(
            canonical_url=canonical_url,
            status=status,
            is_proxy=is_proxy,
        )

    def provides_index(self, directory_path: Path) -> bool:
        """Return ``True`` when MkDocs will serve an index page for this directory.

        MkDocs treats ``index.md`` (and ``README.md``) as the index
        page for the enclosing directory, rendering it at the directory URL.

        I/O is permitted here — this method is called once per directory during
        the discovery phase, never inside per-link or per-file hot loops.

        Args:
            directory_path: Absolute path to the directory to inspect.

        Returns:
            ``True`` if an ``index.md`` or ``README.md`` exists in the directory.
        """
        return any((directory_path / f).exists() for f in ("index.md", "README.md"))

    def get_link_scheme_bypasses(self) -> frozenset[str]:
        """MkDocs has no engine-specific link-scheme bypass."""
        return frozenset()

    def get_extra_content_roots(self, repo_root: Path) -> list[Path]:
        """Discover plugin-managed external docs roots from included MkDocs configs."""
        config_file = find_config_file(repo_root)
        if config_file is None:
            return []
        roots = [
            root
            for root in _discover_monorepo_docs_roots(config_file)
            if root != self._docs_root.resolve()
        ]
        return dedupe_roots(roots)

    def get_locale_source_roots(self, repo_root: Path) -> list[tuple[Path, str]]:  # noqa: ARG002
        """MkDocs locale files are scanned inside docs_root; no external locale roots."""
        return []

    def get_absolute_url_prefixes(self, repo_root: Path | None = None) -> list[str]:  # noqa: ARG002
        """MkDocs is single-instance and exports no absolute URL prefixes."""
        return []

    def get_entry_points(self, vsm: VirtualSiteMap) -> list[str]:
        """Return canonical URLs serving as root entry points from nav configuration."""
        nav_paths = self.get_nav_paths()
        if not nav_paths:
            return ["/"] if "/" in vsm else []

        entry_points = set()
        for p in nav_paths:
            ep = self._map_url(Path(p))
            if ep in vsm:
                entry_points.add(ep)

        if "/" in vsm:
            entry_points.add("/")

        return sorted(entry_points)

    @classmethod
    def from_repo(
        cls,
        context: BuildContext,
        docs_root: Path,
        repo_root: Path,
    ) -> MkDocsAdapter:
        """Construct from a live repository root.

        Loads ``mkdocs.yml`` from *repo_root* and falls back to an empty config
        dict when the file is absent or contains invalid YAML.  The
        ``config_file_found`` flag distinguishes "file absent" from
        "file present but unparseable" — only the former triggers standalone
        fallback in the factory.
        """
        config_file_found = find_config_file(repo_root) is not None
        return cls(
            context,
            docs_root,
            _load_doc_config(repo_root),
            config_file_found=config_file_found,
            repo_root=repo_root,
        )
