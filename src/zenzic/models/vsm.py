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
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from urllib.request import url2pathname

from zenzic.core import regex as re
from zenzic.core.adapters._base import BaseAdapter
from zenzic.core.validator import repo_relative_label
from zenzic.models.diagnostics import ZenzicDiagnostic


_ENCODED_DRIVE = re.compile(r"^/([A-Za-z])%3[Aa](/|$)")


def uri_to_path(uri: str) -> Path:
    """Convert a ``file://`` URI to a cross-platform :class:`Path`.

    The single implementation. Three private copies of this function existed
    -- here, in ``core.incremental`` and in ``lsp.server`` -- and all three
    carried the same Windows defect, so fixing one left the engine crashing
    on the next request. A structural test now asserts ``url2pathname`` is
    called from exactly one module under ``src/``.

    VS Code spells a Windows drive as ``file:///d%3A/...`` -- lowercase letter,
    percent-encoded colon. ``url2pathname`` on Windows splits on the colon
    *before* unquoting, so the encoded form hides the drive and the result is
    a bogus rooted path (``\\d:\\a\\...``) that ``Path.as_uri()`` later
    rejects as relative. Only the drive colon is decoded here; everything else
    is left to ``url2pathname`` so ordinary escapes are not decoded twice.
    """
    path = urlsplit(uri).path
    m = _ENCODED_DRIVE.match(path)
    if m:
        path = f"/{m.group(1).upper()}:{m.group(2)}{path[m.end() :]}"
    return Path(url2pathname(path))


_uri_to_path = uri_to_path  # local callers below


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


def stale_manifest_message(rel_posix: str) -> str:
    """Return the one wording for ``Z115``, for every surface that reports it.

    The CLI (``core/scanner.py``) and the editor (``core/incremental.py``)
    construct this finding independently, because they analyse on different
    paths. Two copies of a sentence is how the two paths start disagreeing —
    this module already carries comments about a capability living in CI and
    not in the editor. The sentence lives here; both callers import it.
    """
    return (
        f"'{rel_posix}' is not declared in the route manifest "
        "(.zenzic-vsm.json), so it routes as IGNORED and every link to it is "
        "reported unreachable. Re-run the generator that writes the manifest."
    )


def build_vsm(
    adapter: BaseAdapter,
    docs_root: Path,
    md_contents: dict[Path, str],
    *,
    anchors_cache: dict[Path, set[str]] | None = None,
    extra_mounts: list[tuple[Path, str]] | None = None,
    static_assets: Iterable[Path] | set[Path] | list[Path] | None = None,
) -> VirtualSiteMap:
    """Build the Virtual Site Map from a pre-loaded file map.

    This function performs no I/O of any kind, and that is now true rather than
    merely claimed. It said "No disk reads occur here" while taking
    ``extra_content_roots`` and calling ``build_content_mounts()`` on them,
    which calls ``Path.resolve()`` twice per root -- filesystem metadata
    syscalls, and dependent on the process working directory for a relative
    path. The claim held only for a project with no external content roots,
    which is to say it held wherever nobody had looked.

    Mounts are therefore computed by the caller now and passed in as
    ``extra_mounts``: ``(resolved_root, url_prefix)`` pairs, from
    ``build_content_mounts()``. Every caller already does I/O and already holds
    ``repo_root``; this function does not, and no longer needs it.

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
        extra_mounts:        Optional ``(content_root, url_prefix)`` pairs for
                     markdown trees outside ``docs_root``, already resolved by
                     the caller via ``build_content_mounts()``.
        static_assets:       Optional collection of non-Markdown static asset Paths.

    Returns:
        ``VSM`` mapping canonical URL → ``Route``. **Every** route is included,
        IGNORED among them — this line claimed the opposite until 2026-09-19
        while the comment above ``VSM`` (line ~127) stated the truth and the
        code agreed with the comment. Inclusion is deliberate: a link pointing
        at an ignored page must be reported as ``UNREACHABLE_LINK``, and an
        omitted route would be reported as a missing file instead, naming the
        wrong defect.
    """

    ac = anchors_cache or {}
    extra_mounts = list(extra_mounts or [])

    routes: list[Route] = []
    md_sources_seen: set[str] = set()
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
        md_sources_seen.add(rel_posix)

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

    if static_assets:
        for abs_path in static_assets:
            if abs_path in md_contents:
                continue
            if abs_path.is_relative_to(docs_root):
                rel = abs_path.relative_to(docs_root)
            else:
                matched_root = None
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
            status = meta.status

            route = Route(
                url=url,
                source=rel_posix,
                status=status,
                anchors=set(),
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

    # Manifest drift, computed here because this is the one place that holds
    # both sets: what the adapter declares and what the scan actually read.
    # The undeclared page does get a route — with status IGNORED — so the
    # symptom is `Z101 UNREACHABLE_LINK` on a correct link, not a missing file.
    #
    # **Only the "on disk, undeclared" half is detected, and that is a decided
    # limit rather than an open task.** The mirror case — a manifest entry whose
    # source has been deleted — cannot be distinguished here from an entry whose
    # source the user excluded, because `md_contents` arrives already filtered by
    # the exclusion layers. Telling the two apart needs one of two things this
    # function may not have: a `stat` per declared entry (this function performs
    # no I/O, and that is enforced by tests/test_build_vsm_is_pure.py), or the
    # unfiltered walk, which no caller retains. A false "your manifest lists a
    # page that no longer exists" is worse than the silence it would replace,
    # so the silence stands and is documented for users on the Z115 rule card.
    _declared = adapter.declared_sources()
    if _declared is not None:
        vsm_instance.undeclared_sources = sorted(md_sources_seen - _declared)

    from zenzic.core.validator import PolyglotExtractor

    extractor = PolyglotExtractor()
    for abs_path, content in md_contents.items():
        vsm_instance.reindex_outgoing_links(
            abs_path,
            content,
            docs_root,
            extra_mounts,
            adapter,
            extractor=extractor,
        )

    return vsm_instance


class VirtualSiteMap(dict[str, Route]):
    """The Virtual Site Map wrapper class.

    Now owns the incoming_links reverse index (canonical URL -> set of paths).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.incoming_links: dict[str, set[Path]] = {}
        self.outgoing_links: dict[str, list[str]] = {}
        # Source paths present in the scanned corpus that the adapter's
        # declared routing table does not list — see BaseAdapter.declared_sources().
        # Always [] for an adapter that derives routes from the filesystem.
        self.undeclared_sources: list[str] = []

    def remove_outgoing_links(self, path: Path, canonical_url: str = "") -> None:
        """Discard `path` from every entry in the reverse index and clear its outgoing links."""
        for dependent_set in self.incoming_links.values():
            dependent_set.discard(path)
        if canonical_url and canonical_url in self.outgoing_links:
            self.outgoing_links[canonical_url] = []

    def reindex_outgoing_links(
        self,
        path: Path,
        content: str,
        docs_root: Path,
        extra_mounts: list[tuple[Path, str]],
        adapter: BaseAdapter,
        canonical_url: str = "",
        extractor: Any = None,
        extracted_links: Any = None,
    ) -> None:
        """Rebuild the reverse-index entries emitted by `path`."""
        if not canonical_url:
            # Fallback O(N) lookup if not provided.
            #
            # The mounts are consulted here, and were not until 2026-09-19. A
            # file outside `docs_root` is a mounted source, and its route is
            # recorded under the logical path the mount gives it -- so falling
            # back to `path.absolute().as_posix()` compared an absolute path
            # against `blog/post.md` and matched nothing, every time. It was
            # also the last filesystem call left inside this module: `absolute()`
            # reads the process working directory, which made the reverse index
            # depend on where the command was run from.
            # `is_relative_to` rather than a `try`, because the label itself now
            # comes from the authority and this branch is the *extra* work the
            # fallback did: a mounted source is outside `docs_root` and takes the
            # logical path its mount gives it. Both are pure computation -- no
            # filesystem call is added here, which `build_vsm` does not permit.
            rel_posix = repo_relative_label(path, docs_root)
            if not path.is_relative_to(docs_root):
                for _root, _prefix in extra_mounts:
                    if path.is_relative_to(_root):
                        _inner = path.relative_to(_root)
                        rel_posix = (
                            (Path(_prefix) / _inner).as_posix() if _prefix else _inner.as_posix()
                        )
                        break
            canonical_url = next((url for url, r in self.items() if r.source == rel_posix), "")

        self.remove_outgoing_links(path, canonical_url=canonical_url)

        targets: set[str] = set()

        def _register(url: str) -> None:
            if not url or url.startswith(("http://", "https://", "data:", "mailto:", "#")):
                return
            canonical = resolve_link_to_canonical(
                path,
                url,
                docs_root,
                extra_mounts,
                adapter,
            )
            if canonical:
                self.incoming_links.setdefault(canonical, set()).add(path)
                targets.add(canonical)

        if extracted_links is not None:
            for item in extracted_links:
                if item.url and item.node_type != "ref_link":
                    _register(item.url)
        else:
            if extractor is None:
                from zenzic.core.validator import PolyglotExtractor

                extractor = PolyglotExtractor()
            for item in extractor.extract_all_links(content):
                if item.url and item.node_type != "ref_link":
                    _register(item.url)

        if canonical_url:
            self.outgoing_links[canonical_url] = sorted(targets)


def resolve_link_to_canonical(
    source_file: Path,
    url: str,
    docs_root: Path,
    extra_mounts: list[tuple[Path, str]],
    adapter: BaseAdapter,
) -> str | None:
    from urllib.parse import unquote, urlsplit

    from zenzic.core.validator import LINK_BYPASS_SCHEMES

    # `startswith("#")` rather than `== "#"`, which is the one place this differs
    # from the security tier's otherwise identical check. Here a fragment can
    # never name a route, so skipping every fragment is right. There it is not:
    # see `SECURITY_BYPASS_SCHEMES`.
    if url.startswith(LINK_BYPASS_SCHEMES) or url.startswith("#"):
        return None

    parsed = urlsplit(url)
    path_part = unquote(parsed.path.replace("\\", "/"))
    if not path_part:
        return None

    # The alias rules (`/`, `@site/docs/`, `@site/`, else page-relative) and the
    # directory-URL depth boundary are defined once in
    # `zenzic.core.resolver.resolve_href_target`.  This used to be a fourth
    # independent copy of them, and the copies did not agree.
    from zenzic.core.resolver import resolve_href_target

    use_dir_urls = bool(getattr(adapter, "use_directory_urls", True))
    target_path = Path(
        resolve_href_target(
            source_file,
            path_part,
            str(docs_root),
            str(docs_root.parent),
            use_directory_urls=use_dir_urls,
        )
    )

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

    # `rel` is a resolved *href target*, and that is not always a source file.
    # A link written in the form the site serves -- `./page/`, `../section/` --
    # resolves to a URL-shaped path carrying no document suffix, and
    # `get_route_info` is specified over source files: its adapters correctly read
    # a suffix-less path as a static asset and return it verbatim, giving
    # `/section/page` where the route table keys the page at `/section/page/`. The
    # VSM then failed to find a page it was itself routing and dropped the edge --
    # 235 occurrences on this project's own corpus, and 234 of 797 reverse-index
    # entries pointing at a target that was not a route key.
    #
    # So the URL for a URL-shaped target is formed here rather than by asking the
    # source-file mapper a question it is not defined for. This is deliberately the
    # only place it happens: the adapters' contract is left intact, and a target
    # that *does* carry a suffix -- `feed.xml`, `rss.xsl`, an image -- still goes
    # through the adapter and still resolves to no route, which is correct because
    # it is not a page.
    if use_dir_urls and not rel.suffix:
        slug = rel.as_posix().strip("/")
        if slug in ("", "."):
            return "/"
        return f"/{slug}/"

    meta = adapter.get_route_info(rel)
    return meta.canonical_url


class VirtualBufferOverlay:
    """Virtual Site Map overlay for in-memory buffers.

    Allows the Uniform Resolver Pipeline (URP) to resolve against memory buffers,
    bypassing L1-L4 filesystem discovery.
    """

    def __init__(self, vsm: VirtualSiteMap, *, tabs: str | None) -> None:
        self.vsm: VirtualSiteMap = vsm
        self.buffers: dict[str, str] = {}
        self.anchors_cache: dict[Path, set[str]] = {}
        #: The project's content-tab anchor style. Required rather than
        #: defaulted: this overlay feeds the editor's anchor resolution, and a
        #: default would make the editor disagree with the CLI about whether a
        #: link to a content tab resolves.
        self._tabs = tabs

    # ── Buffer management ─────────────────────────────────────────────────────

    def update(self, uri: str, content: str) -> None:
        """Register or refresh an in-memory buffer, updating anchors."""

        from zenzic.core.validator import anchors_in_file

        self.buffers[uri] = content
        if uri.startswith("file://"):
            path = _uri_to_path(uri).resolve()
            self.anchors_cache[path] = anchors_in_file(content, tabs=self._tabs)

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
