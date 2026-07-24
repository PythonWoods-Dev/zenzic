# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Virtual Site Map (VSM) data model.

The VSM is the single source of truth for routing: it maps every physical
Markdown source file to the canonical URL the build engine will serve,
together with a reachability status and the set of heading anchors.

Design principles (The Zenzic Way):
- Pure data, no I/O.  ``Route`` is a frozen dataclass; ``VSM`` is a plain dict.
- ``build_vsm()`` is the only I/O entry point; it delegates URL mapping to the
  adapter and collision detection to ``_detect_collisions()``.
- Status values match the Routing Table Specification in the project brief.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from urllib.request import url2pathname

from zenzic.core.adapters._base import BaseAdapter
from zenzic.core.discovery import build_content_mounts
from zenzic.models.diagnostics import ZenzicDiagnostic


def _uri_to_path(uri: str) -> Path:
    """Convert a file:// URI to a cross-platform pathlib.Path."""
    parsed = urlsplit(uri)
    return Path(url2pathname(parsed.path))


_log = logging.getLogger(__name__)


# ─── Status type ──────────────────────────────────────────────────────────────

RouteStatus = Literal["REACHABLE", "ORPHAN_BUT_EXISTING", "IGNORED", "CONFLICT"]


# ─── Route ────────────────────────────────────────────────────────────────────


@dataclass
class Route:
    """One entry in the Virtual Site Map.

    Attributes:
        url:     Canonical URL path (e.g. ``/guide/installation/``).
        source:  Physical path of the Markdown source file, relative to
                 ``docs_root`` (e.g. ``guide/installation.md``).
        status:  Routing status:

                 ``REACHABLE``
                     The page is reachable via the site navigation (listed in
                     nav for MkDocs, or all files for Zensical).
                 ``ORPHAN_BUT_EXISTING``
                     The file exists on disk but is **not** referenced in the
                     nav.  The build engine will still render it (it is
                     accessible via direct URL), but it has no navigation
                     entry — it is invisible to browsing users.
                 ``IGNORED``
                     The file should not be served (e.g. ``README.md`` not
                     in nav for MkDocs, files in ``_private/`` dirs for
                     Zensical).
                 ``CONFLICT``
                     Two or more source files map to the same canonical URL.
                     The build result is undefined/engine-dependent.

        anchors: Heading anchor slugs extracted from the source file
                 (e.g. ``{'installation', 'quick-start'}``).
        aliases: Additional URL aliases or redirects for this page (reserved
                 for future use; populated by adapters that support redirect
                 declarations).
        diagnostics: Strictly typed diagnostic findings for this route.
    """

    url: str
    source: str
    status: RouteStatus
    anchors: set[str] = field(default_factory=set)
    aliases: set[str] = field(default_factory=set)
    proxy_sources: frozenset[str] = field(default_factory=frozenset)
    diagnostics: list[ZenzicDiagnostic] = field(default_factory=list)

    # Convenience ──────────────────────────────────────────────────────────────

    @property
    def is_reachable(self) -> bool:
        """``True`` when status is ``REACHABLE``."""
        return self.status == "REACHABLE"

    @property
    def is_conflict(self) -> bool:
        """``True`` when status is ``CONFLICT``."""
        return self.status == "CONFLICT"


# ─── VSM type alias ────────────────────────────────────────────────────────────

# Canonical URL → Route.  All routes (including IGNORED) are included so that
# links to ignored files (e.g. _private/ in Zensical) can be caught as
# UNREACHABLE_LINK by the validator.
VSM = dict[str, Route]


# ─── Collision detection (pure, adapter-independent) ─────────────────────────


def _detect_collisions(routes: list[Route]) -> None:
    """Mark conflicting routes in-place.

    Two routes conflict when they share the same canonical URL.  Both are
    marked ``CONFLICT`` (the first one too, to avoid silent shadowing).

    Pure function: no I/O, mutates only the ``status`` field of the provided
    ``Route`` objects.

    Args:
        routes: List of ``Route`` objects (mutated in-place).
    """
    seen: dict[str, Route] = {}
    for route in routes:
        if route.url in seen:
            route.status = "CONFLICT"
            seen[route.url].status = "CONFLICT"
        else:
            seen[route.url] = route


# ─── VSM builder (I/O boundary) ───────────────────────────────────────────────


def build_vsm(
    adapter: BaseAdapter,
    docs_root: Path,
    md_contents: dict[Path, str],
    *,
    anchors_cache: dict[Path, set[str]] | None = None,
    extra_content_roots: list[Path] | None = None,
    repo_root: Path | None = None,
) -> VirtualSiteMap:
    """Build the Virtual Site Map from a pre-loaded file map.

    This is the I/O boundary: all file content has already been loaded into
    ``md_contents`` by the caller (``validate_links_async``).  No disk reads
    occur here.

     Routing strategy is strict metadata-driven: every file is dispatched via
     ``adapter.get_route_info(rel)``.

     Multi-root resolution accepts external content trees as ``list[Path]``.
     URL prefixes are derived deterministically from filesystem topology.

    Workflow:

    1. Iterate over every ``.md`` file in ``md_contents``.
    2. Compute routing metadata via the preferred API.
    3. Run ``_detect_collisions()`` across all routes.
    4. Build and return the ``VSM`` dict.

    Args:
        adapter:             Build-engine adapter implementing ``get_route_info(rel)``.
        docs_root:           Resolved absolute path to the ``docs/`` directory.
        md_contents:         Pre-loaded mapping of absolute ``Path`` → raw Markdown.
        anchors_cache:       Pre-computed ``Path`` → anchor slug set.  When
                             ``None``, anchors are left as empty sets.
        extra_content_roots: Optional external markdown roots injected by caller.
        repo_root:           Optional repository root used for stable prefix
                     derivation when building external content mounts.

    Returns:
        ``VSM`` mapping canonical URL → ``Route`` (IGNORED entries omitted).
    """
    ac = anchors_cache or {}
    extra_mounts = build_content_mounts(list(extra_content_roots or []), repo_root=repo_root)

    routes: list[Route] = []
    for abs_path, _content in md_contents.items():
        # ── Resolve the logical rel and source label ────────────────────────
        # Files under docs_root use their ordinary relative path. Files under
        # external content roots carry a deterministic prefix segment derived
        # from the content mount.
        if abs_path.is_relative_to(docs_root):
            rel = abs_path.relative_to(docs_root)
        else:
            matched_root: tuple[Path, str] | None = None
            for root, prefix in extra_mounts:
                if abs_path.is_relative_to(root):
                    matched_root = (root, prefix)
                    break
            if matched_root is None:
                continue
            root, prefix = matched_root
            inner = abs_path.relative_to(root)
            rel = (Path(prefix) / inner) if prefix else inner
        rel_posix = rel.as_posix()

        meta = adapter.get_route_info(rel)
        url = meta.canonical_url
        status: RouteStatus = meta.status

        route = Route(
            url=url,
            source=rel_posix,
            status=status,
            anchors=set(ac.get(abs_path, set())),
        )
        routes.append(route)

    if hasattr(adapter, "get_virtual_routes"):
        for vr in adapter.get_virtual_routes(md_contents):
            # Layer 2 defensive check (layer 1 already enforced in __post_init__)
            if not vr.source_files:  # pragma: no cover
                _log.error("VirtualRoute %r escaped invariant — skipped", vr.url)
                continue
            routes.append(
                Route(
                    url=vr.url,
                    source="<virtual>",
                    status="REACHABLE",
                    proxy_sources=vr.source_files,
                )
            )

    _detect_collisions(routes)

    vsm_instance = VirtualSiteMap({r.url: r for r in routes})
    for abs_path, content in md_contents.items():
        vsm_instance.reindex_outgoing_links(
            abs_path,
            content,
            docs_root,
            extra_mounts,
            adapter,
        )

    return vsm_instance


class VirtualSiteMap(dict[str, Route]):
    """The Virtual Site Map wrapper class.

    Now owns the incoming_links reverse index (canonical URL -> set of paths).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.incoming_links: dict[str, set[Path]] = {}

    def remove_outgoing_links(self, path: Path) -> None:
        """Discard `path` from every entry in the reverse index."""
        for dependent_set in self.incoming_links.values():
            dependent_set.discard(path)

    def reindex_outgoing_links(
        self,
        path: Path,
        content: str,
        docs_root: Path,
        extra_mounts: list[tuple[Path, str]],
        adapter: BaseAdapter,
    ) -> None:
        """Rebuild the reverse-index entries emitted by `path`."""
        self.remove_outgoing_links(path)

        from zenzic.core.rules import _extract_inline_links_with_lines
        from zenzic.core.validator import PolyglotExtractor

        def _register(url: str) -> None:
            canonical = resolve_link_to_canonical(
                path,
                url,
                docs_root,
                extra_mounts,
                adapter,
            )
            if canonical:
                self.incoming_links.setdefault(canonical, set()).add(path)

        for url, _lineno, _raw in _extract_inline_links_with_lines(content):
            _register(url)

        for node in PolyglotExtractor().extract(content):
            if node.href:
                _register(node.href)


def resolve_link_to_canonical(
    source_file: Path,
    url: str,
    docs_root: Path,
    extra_mounts: list[tuple[Path, str]],
    adapter: BaseAdapter,
) -> str | None:
    import os
    from urllib.parse import unquote, urlsplit

    _bypass_schemes = (
        "mailto:",
        "tel:",
        "javascript:",
        "data:",
        "irc:",
        "xmpp:",
        "http://",
        "https://",
    )
    if url.startswith(_bypass_schemes) or url == "#" or url.startswith("#"):
        return None

    parsed = urlsplit(url)
    path_part = unquote(parsed.path.replace("\\", "/"))
    if not path_part:
        return None

    # Resolve relative to source_file parent or docs_root
    if path_part.startswith("/"):
        target_path = docs_root / path_part.lstrip("/")
    elif path_part.startswith("@site/docs/"):
        target_path = docs_root / path_part[len("@site/docs/") :]
    elif path_part.startswith("@site/"):
        target_path = docs_root.parent / path_part[len("@site/") :]
    else:
        target_path = source_file.parent / path_part

    # Clean up target_path (collapse segments)
    target_path = Path(os.path.normpath(str(target_path)))

    # Determine the relative path used by the adapter
    if target_path.is_relative_to(docs_root):
        rel = target_path.relative_to(docs_root)
    else:
        matched_root: tuple[Path, str] | None = None
        for root, prefix in extra_mounts:
            if target_path.is_relative_to(root):
                matched_root = (root, prefix)
                break
        if matched_root is None:
            return None
        root, prefix = matched_root
        inner = target_path.relative_to(root)
        rel = (Path(prefix) / inner) if prefix else inner

    meta = adapter.get_route_info(rel)
    return meta.canonical_url


class VirtualBufferOverlay:
    """Virtual Site Map overlay for in-memory buffers.

    Allows the Uniform Resolver Pipeline (URP) to resolve against memory buffers,
    bypassing L1-L4 filesystem discovery.
    """

    def __init__(self, vsm: VirtualSiteMap) -> None:
        self.vsm: VirtualSiteMap = vsm
        self.buffers: dict[str, str] = {}
        self.anchors_cache: dict[Path, set[str]] = {}

    # ── Buffer management ─────────────────────────────────────────────────────

    def update(self, uri: str, content: str) -> None:
        """Register or refresh an in-memory buffer, updating anchors."""

        from zenzic.core.validator import anchors_in_file

        self.buffers[uri] = content
        if uri.startswith("file://"):
            path = _uri_to_path(uri).resolve()
            self.anchors_cache[path] = anchors_in_file(content)

    def register_file_links(self, path: Path, content: str) -> None:
        """No-op. Reverse index is managed by VirtualSiteMap during build_vsm."""
        pass

    def remove(self, uri: str) -> None:
        """Evict a buffer."""
        self.buffers.pop(uri, None)
        if uri.startswith("file://"):
            path = _uri_to_path(uri).resolve()
            self.anchors_cache.pop(path, None)

    def dependents_of(self, canonical_url: str) -> frozenset[Path]:
        """Return the set of files that contain a link resolving to ``canonical_url``."""
        if hasattr(self.vsm, "incoming_links"):
            return frozenset(self.vsm.incoming_links.get(canonical_url, set()))
        return frozenset()

    # ── VSM proxy ─────────────────────────────────────────────────────────────

    def get(self, key: str, default: Route | None = None) -> Route | None:
        return self.vsm.get(key, default)

    def items(self) -> list[tuple[str, Route]]:
        return list(self.vsm.items())

    def __getitem__(self, key: str) -> Route:
        return self.vsm[key]

    def __contains__(self, key: str) -> bool:
        return key in self.vsm
