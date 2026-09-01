# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Centralised file-discovery utilities for the Zenzic Core.

Every module that needs to iterate over documentation source files or asset
files must use the helpers defined here.  This ensures that ``excluded_dirs``
(including the ``SYSTEM_EXCLUDED_DIRS`` guardrails merged at config load time)
and ``excluded_file_patterns`` are applied **universally** — scanner, validator,
credential scanner, and orphan-checker all see the exact same file set.

Public API
----------
* :func:`walk_files` — low-level ``os.walk`` with directory pruning.
* :func:`iter_markdown_sources` — yield ``.md`` / ``.mdx`` files honouring
  both directory *and* filename exclusions.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

from zenzic.models.config import ZenzicConfig


if TYPE_CHECKING:
    from zenzic.core.exclusion import LayeredExclusionManager


# Extensions recognised as documentation source files (not assets).
DOC_SUFFIXES: frozenset[str] = frozenset({".md", ".mdx"})


def derive_content_root_prefix(content_root: Path, repo_root: Path | None = None) -> str:
    """Derive a stable logical URL prefix for an external content root.

    The prefix is inferred from filesystem topology so scanner/validator/VSM can
    consume ``list[Path]`` roots without adapter-specific wrappers.
    """
    root = content_root.resolve()

    if repo_root is not None:
        try:
            rel = root.relative_to(repo_root.resolve())
        except ValueError:
            rel = None
        if rel is not None and rel.parts:
            if rel.parts[-1] in {"docs", "current"} and len(rel.parts) >= 2:
                return rel.parts[-2]
            return rel.parts[0]

    if root.name in {"docs", "current"} and root.parent.name:
        return root.parent.name
    return root.name


def build_content_mounts(
    content_roots: list[Path],
    *,
    repo_root: Path | None = None,
) -> list[tuple[Path, str]]:
    """Return ``(content_root, url_prefix)`` mounts from ``list[Path]`` roots."""
    return [
        (root.resolve(), derive_content_root_prefix(root, repo_root=repo_root))
        for root in content_roots
    ]


def walk_files(
    root: Path,
    excluded_dirs: set[str] | frozenset[str],
    exclusion_manager: LayeredExclusionManager,
    config: ZenzicConfig | None = None,
) -> Generator[Path, None, None]:
    """Yield all regular files under *root*, pruning excluded directories.

    Unlike ``Path.rglob("*")``, this uses :func:`os.walk` with in-place
    directory pruning so that large excluded trees (e.g. ``.nox/``,
    ``node_modules/``) are never entered at all.

    The *exclusion_manager* drives directory exclusion decisions via
    :meth:`~LayeredExclusionManager.should_exclude_dir`.  The
    *excluded_dirs* set provides an additional hard-prune layer (used by
    ``find_unused_assets`` for ``excluded_asset_dirs``).

    .. important::
        Docusaurus partial files (names starting with ``_``) are **not**
        excluded here.  Physical I/O pruning would render the credential
        scanner (Z201/Z204) blind to secrets hidden in partials.  Routing
        exclusions (URL mapping, Z402, Z502) happen at the logical layer
        inside the adapter and rule engine.
    """
    repo_root = getattr(exclusion_manager, "_repo_root", None) or root
    resolved_repo_root = repo_root.resolve(strict=False)
    import logging

    logger = logging.getLogger("zenzic.core.discovery")

    for dirpath, dirnames, filenames in os.walk(root):
        filtered_dirnames = []
        for d in dirnames:
            rel_path = None
            if repo_root is not None:
                try:
                    rel_path = (Path(dirpath) / d).relative_to(repo_root).as_posix()
                except ValueError:
                    pass

            if exclusion_manager.should_exclude_dir(d, rel_path):
                continue
            if d in excluded_dirs:
                continue
            if rel_path and rel_path in excluded_dirs:
                continue

            filtered_dirnames.append(d)
        dirnames[:] = sorted(filtered_dirnames)
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            # Security boundary check (Path Sovereignty / Z202 Path Traversal):
            resolved_fpath = fpath.resolve(strict=False)
            try:
                if not resolved_fpath.is_relative_to(resolved_repo_root):
                    logger.warning(
                        "Z202 Path Traversal: skipping file escaping workspace root boundary: %s -> %s",
                        fpath,
                        resolved_fpath,
                    )
                    continue
            except ValueError:
                logger.warning(
                    "Z202 Path Traversal: skipping file escaping workspace root boundary: %s -> %s",
                    fpath,
                    resolved_fpath,
                )
                continue

            yield fpath


def iter_locale_markdown_sources(
    locale_root: Path,
    locale_name: str,
    config: ZenzicConfig,
    exclusion_manager: LayeredExclusionManager,
) -> Generator[tuple[Path, Path], None, None]:
    """Yield ``(abs_path, logical_rel)`` for source files in a Docusaurus locale tree.

    ``logical_rel`` is the path that the core should use as the file's identity
    within the broader documentation namespace — it starts with the locale
    prefix so that the adapter can route it correctly::

        i18n/it/.../current/architecture.mdx  →  (abs_path, Path("it/architecture.mdx"))

    The locale prefix makes ``_map_url(logical_rel)`` produce the correct
    locale-prefixed URL (e.g. ``/it/architecture/``) without any special-casing
    in the adapter.

    Args:
        locale_root: Absolute path to the locale docs root
            (e.g. ``i18n/it/docusaurus-plugin-content-docs/current/``).
        locale_name: ISO locale code used as the path prefix (e.g. ``'it'``).
        config: Loaded Zenzic configuration.
        exclusion_manager: Layered exclusion manager.

    Yields:
        ``(abs_path, logical_rel)`` tuples where
        ``logical_rel = Path(locale_name) / path.relative_to(locale_root)``.
    """
    if not locale_root.is_dir():
        return
    excluded_dirs = set(config.excluded_dirs)
    for md_file in walk_files(locale_root, excluded_dirs, exclusion_manager, config):
        if md_file.suffix not in DOC_SUFFIXES:
            continue
        if exclusion_manager.should_exclude_file(md_file, locale_root):
            continue
        logical_rel = Path(locale_name) / md_file.relative_to(locale_root)
        yield md_file, logical_rel


def iter_extra_content_markdown_sources(
    content_root: Path,
    url_prefix: str,
    config: ZenzicConfig,
    exclusion_manager: LayeredExclusionManager,
) -> Generator[tuple[Path, Path], None, None]:
    """Yield ``(abs_path, logical_rel)`` for files in an extra content root.

    v0.7.x Multi-Root Discovery helper.  Walks a content tree that lives
    outside ``docs_root`` (e.g. Docusaurus's ``blog/`` directory) and yields
    each Markdown file with a *logical* relative path that includes the
    declared URL prefix.  The prefix injection lets the active adapter route
    the file via its existing ``get_route_info()`` logic without a second
    dispatch:

    .. code-block:: text

        <repo>/blog/2026-04-12-foo.mdx, prefix='blog'
            → (abs_path, Path('blog/2026-04-12-foo.mdx'))

    Empty ``url_prefix`` yields the file's path relative to ``content_root``
    unchanged — useful for engines that serve extra content at the site root.

    Args:
        content_root:      Absolute path to the extra content root.
        url_prefix:        URL prefix injected for this mounted root.
        config:            Loaded Zenzic configuration.
        exclusion_manager: Layered exclusion manager.

    Yields:
        ``(abs_path, logical_rel)`` tuples in deterministic sorted order.
    """
    if not content_root.is_dir():
        return
    excluded_dirs = set(config.excluded_dirs)
    prefix_path = Path(url_prefix) if url_prefix else None
    for md_file in walk_files(content_root, excluded_dirs, exclusion_manager, config):
        if md_file.suffix not in DOC_SUFFIXES:
            continue
        if exclusion_manager.should_exclude_file(md_file, content_root):
            continue
        rel = md_file.relative_to(content_root)
        logical_rel = (prefix_path / rel) if prefix_path is not None else rel
        yield md_file, logical_rel


def iter_security_scan_sources(
    docs_root: Path,
    config: ZenzicConfig,
    exclusion_manager: LayeredExclusionManager,
    *,
    content_roots: list[Path] | None = None,
    locale_roots: list[tuple[Path, str]] | None = None,
) -> Generator[Path, None, None]:
    """Yield every doc source the security tier must scan, ignoring user scoping.

    Counterpart to :func:`iter_markdown_sources` for the credential and
    forbidden-term scan (Z201/Z204/Z205): user-configured exclusions
    (``excluded_dirs``, ``excluded_file_patterns``, CLI ``--exclude-dir``)
    scope files out of *quality* analysis only — the security tier is never
    suppressible, by any mechanism, so its discovery walks the corpus through
    the manager's :meth:`~LayeredExclusionManager.security_view`, which keeps
    only the system guardrails and the VCS layer.

    The scan must cover **every** tree ``scan_docs_references`` reaches for
    quality analysis, not just ``docs_root``: an MkDocs monorepo's included
    sub-project docs (``content_roots``) and i18n locale trees
    (``locale_roots``) live outside ``docs_root``, and a user exclusion
    matching a file there would otherwise hide a credential from both the
    corpus and this pass — the exact defect this function exists to close,
    re-opened on a different root. Extra roots are deduplicated against
    ``docs_root`` and each other by resolved path.

    Yields:
        Absolute :class:`~pathlib.Path` objects (deterministic per-root order).
    """
    view = exclusion_manager.security_view()
    roots: list[Path] = [docs_root, *(content_roots or []), *(lr[0] for lr in (locale_roots or []))]
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for md_file in walk_files(root, set(), view, config):
            if md_file.suffix not in DOC_SUFFIXES:
                continue
            if view.should_exclude_file(md_file, root):
                continue
            resolved = md_file.resolve(strict=False)
            if resolved in seen:
                continue
            seen.add(resolved)
            yield md_file


def iter_markdown_sources(
    docs_root: Path,
    config: ZenzicConfig,
    exclusion_manager: LayeredExclusionManager,
) -> Generator[Path, None, None]:
    """Yield absolute paths to ``.md`` / ``.mdx`` files, honouring all exclusions.

    All exclusion decisions are delegated to the *exclusion_manager*,
    which implements the 4-level Layered Exclusion model (System Guardrails,
    VCS, Config, CLI).

    This is the **single authorised entry point** for discovering documentation
    source files.  All modules (scanner, validator, orphan-checker) must use
    this function instead of calling ``rglob`` or ``walk_files`` directly for
    Markdown iteration.

    Args:
        docs_root: Absolute path to the documentation root directory.
        config: Loaded Zenzic configuration (provides ``excluded_dirs``).
        exclusion_manager: Layered Exclusion Manager for full
            4-level exclusion evaluation.

    Yields:
        Absolute :class:`~pathlib.Path` objects for each qualifying source file,
        in deterministic sorted order (imposed by :func:`walk_files`).
    """
    excluded_dirs = set(config.excluded_dirs)
    for md_file in walk_files(docs_root, excluded_dirs, exclusion_manager, config):
        if md_file.suffix not in DOC_SUFFIXES:
            continue
        if exclusion_manager.should_exclude_file(md_file, docs_root):
            continue
        yield md_file
