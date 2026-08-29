# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Shared command-setup factory for ``zenzic check`` sub-commands.

Provides :func:`setup_command` which consolidates the repetitive preamble
(repo-root discovery, config loading, target resolution, exclusion-manager
construction) that appears at the top of every check command.  Extracted from
``_check.py`` as part of Phase 82 CLI decomposition (ADR-082).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.scanner import find_repo_root
from zenzic.models.config import ZenzicConfig

from . import _shared
from ._target_resolver import _apply_target


def setup_command(
    path: str | None = None,
    *,
    config_file: Path | None = None,
    engine_override: str | None = None,
    offline: bool = False,
    exclude_url: Sequence[str] | None = None,
    extra_exclude_dirs: list[str] | None = None,
    extra_include_dirs: list[str] | None = None,
) -> tuple[ZenzicConfig, Path, Path, LayeredExclusionManager, Path | None, bool]:
    """Discover repo root, load config, resolve optional *path* target.

    Returns ``(config, repo_root, docs_root, exclusion_mgr, single_file, loaded_from_file)``.

    ``single_file`` is ``None`` in directory mode, or the resolved absolute
    ``.md`` / ``.mdx`` path in single-file mode.
    ``loaded_from_file`` reflects whether ``.zenzic.toml`` was present on disk.
    """
    _search_from: Path | None = None
    if path is not None:
        _pre = Path(path).resolve()
        _search_from = _pre.parent if _pre.is_file() else _pre

    repo_root = find_repo_root(search_from=_search_from)
    config, loaded_from_file = ZenzicConfig.load(repo_root, config_file=config_file)

    config = _shared._apply_engine_override(config, engine_override)
    if offline:
        config.build_context.offline_mode = True
    if exclude_url:
        config = config.model_copy(
            update={"excluded_external_urls": config.excluded_external_urls + list(exclude_url)}
        )

    single_file: Path | None = None
    if path is not None:
        config, single_file, docs_root, _ = _apply_target(repo_root, config, path)
        try:
            docs_root.relative_to(repo_root)
        except ValueError:
            repo_root = docs_root
    else:
        docs_root = (repo_root / config.docs_dir).resolve()

    # Apply optional extra exclusion/inclusion overrides (used by check_all).
    if extra_exclude_dirs:
        config = config.model_copy(
            update={"excluded_dirs": list(config.excluded_dirs) + extra_exclude_dirs}
        )
    if extra_include_dirs:
        config = config.model_copy(
            update={
                "force_include_dirs": list(getattr(config, "force_include_dirs", []))
                + extra_include_dirs
            }
        )

    exclusion_mgr = _shared._build_exclusion_manager(config, repo_root, docs_root)

    return config, repo_root, docs_root, exclusion_mgr, single_file, loaded_from_file
