# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""StandaloneAdapter — no-op adapter for projects with no recognised build engine."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from zenzic.core.adapters._base import BaseAdapter


if TYPE_CHECKING:
    from zenzic.core.adapters._base import RouteMetadata


class StandaloneAdapter(BaseAdapter):
    """Adapter for projects with no recognised build engine (Standalone Mode).

    Returned by :func:`~zenzic.core.adapters.get_adapter` when neither a
    ``mkdocs.yml`` nor explicit locales are detected.  Provides neutral,
    no-op behaviour so Zenzic operates as a standalone document integrity analyzer without
    any i18n awareness.

    In Standalone Mode, navigation-based checks (orphans) are disabled
    because there is no declared nav to compare against.

    All methods are pure and perform no I/O.
    """

    def is_locale_dir(self, part: str) -> bool:  # noqa: ARG002
        """Always ``False`` — no locale directories without an engine config."""
        return False

    def resolve_asset(self, missing_abs: Path, docs_root: Path) -> Path | None:  # noqa: ARG002
        """Always ``None`` — no fallback logic without a locale tree."""
        return None

    def resolve_anchor(  # noqa: ARG002
        self,
        resolved_file: Path,
        anchor: str,
        anchors_cache: dict[Path, set[str]],
        docs_root: Path,
    ) -> bool:
        """Always ``False`` — no i18n anchor fallback without a locale tree."""
        return False

    def is_shadow_of_nav_page(self, rel: Path, nav_paths: frozenset[str]) -> bool:  # noqa: ARG002
        """Always ``False`` — no shadow pages without a nav."""
        return False

    def get_ignored_patterns(self) -> set[str]:
        """Empty set — no suffix-mode i18n patterns."""
        return set()

    def get_nav_paths(self) -> frozenset[str]:
        """Empty frozenset — no engine config means no declared nav."""
        return frozenset()

    def has_engine_config(self) -> bool:
        """``False`` — StandaloneAdapter is active only when no engine was detected."""
        return False

    def get_metadata_files(self) -> frozenset[str]:
        """StandaloneAdapter has no engine config file."""
        return frozenset()

    @property
    def use_directory_urls(self) -> bool:
        """Standalone mode defaults to directory-style canonical URLs."""
        return True

    def _map_url(self, rel: Path) -> str:
        """Filesystem-derived clean URL — same rule as Zensical."""
        stem = rel.with_suffix("")
        parts = list(stem.parts)
        if not parts:
            return "/"
        if parts[-1] in ("index", "README"):
            parts = parts[:-1]
        if not parts:
            return "/"
        return "/" + "/".join(parts) + "/"

    def get_route_info(self, rel: Path) -> RouteMetadata:
        """Return route metadata derived purely from the filesystem.

        StandaloneAdapter has no engine config, no nav, no slug support.
        Every file is ``REACHABLE`` with a filesystem-derived URL.
        """
        from zenzic.core.adapters._base import RouteMetadata

        return RouteMetadata(
            canonical_url=self._map_url(rel),
            status="REACHABLE",
        )

    def provides_index(self, directory_path: Path) -> bool:
        """Return ``True`` when a plain ``index.md`` exists in the directory.

        For standalone (no-engine) projects, the conventional ``index.md`` is the
        sole indicator that a directory landing page will be served.

        I/O is permitted here — this method is called once per directory during
        the discovery phase, never inside per-link or per-file hot loops.

        Args:
            directory_path: Absolute path to the directory to inspect.

        Returns:
            ``True`` if an ``index.md`` exists in the directory.
        """
        return any(
            (directory_path / name).exists()
            for name in ("index.md", "index.mdx", "README.md", "README.mdx")
        )

    def get_link_scheme_bypasses(self) -> frozenset[str]:
        """Standalone projects have no engine-specific link-scheme bypass."""
        return frozenset()

    def get_extra_content_roots(self, repo_root: Path) -> list[Path]:  # noqa: ARG002
        """Standalone projects do not define extra content trees."""
        return []

    def get_locale_source_roots(self, repo_root: Path) -> list[tuple[Path, str]]:  # noqa: ARG002
        """Standalone projects do not define locale source trees."""
        return []

    def get_absolute_url_prefixes(self, repo_root: Path | None = None) -> list[str]:  # noqa: ARG002
        """Standalone mode owns no absolute URL prefixes."""
        return []
