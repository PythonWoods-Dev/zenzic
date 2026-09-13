# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Pure in-memory path resolver for Markdown documentation link validation.

Zero I/O guarantee: all file membership and anchor lookups are performed
against pre-built in-memory mappings passed at construction time.
No ``open()``, no ``Path.exists()``, no ``subprocess``.

The resolver is engine-agnostic. It knows nothing about MkDocs, Zensical, or
any build system — only about paths, anchors, and whether a link is
resolvable within a given in-memory file tree.

Performance contract: 5 000 ``resolve()`` calls must complete in < 100 ms.
This is achieved by keeping the hot path free of ``pathlib.Path`` allocations:

- The credential scanner uses a string prefix check (O(1), no Path decomposition).
- File lookup uses a flat pre-computed ``dict[str, Path]`` (one ``dict.get``
  replaces three ``Path`` constructions and three membership tests).
- ``_build_target`` returns a plain ``str`` via ``os.path.normpath`` (pure
  C string manipulation, no pathlib overhead).

Typical usage (caller owns I/O, resolver owns logic)::

    # I/O layer (CLI / plugin) builds the maps once
    md_contents: dict[Path, str] = {
        Path("/docs/index.md"): "# Home\\n",
        Path("/docs/guide/install.md"): "# Install\\n## Quick Start\\n",
    }
    anchors_cache = {p: anchors_in_file(c) for p, c in md_contents.items()}

    # Pure resolver — no further I/O
    resolver = InMemoryPathResolver(
        root_dir=Path("/docs"),
        md_contents=md_contents,
        anchors_cache=anchors_cache,
    )
    outcome = resolver.resolve(Path("/docs/index.md"), "guide/install.md#quick-start")
    assert isinstance(outcome, Resolved)
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Literal, NamedTuple
from urllib.parse import unquote, urlsplit


# ─── Outcome types (discriminated union) ──────────────────────────────────────


class PathTraversal(NamedTuple):
    """The resolved path escapes the documentation root — credential scanner rejection.

    This outcome is produced whenever ``..`` segments (or an absolute href)
    cause the normalised target to land outside ``root_dir``.

    Example trigger: ``[evil](../../../../etc/passwd)``

    Attributes:
        raw_href: The original href string exactly as it appeared in the source.
    """

    raw_href: str


class FileNotFound(NamedTuple):
    """No file matching the link target exists in ``md_contents``.

    Attributes:
        path_part: The decoded, normalised path component of the href
            (no fragment, no query string).
    """

    path_part: str


class AnchorMissing(NamedTuple):
    """The target file exists but the requested anchor slug is absent.

    Attributes:
        path_part: Decoded path component of the href.
        anchor: The fragment identifier that could not be found (without ``#``).
        resolved_file: The absolute path of the file that was found but whose
            heading set does not contain ``anchor``.
    """

    path_part: str
    anchor: str
    resolved_file: Path


class Resolved(NamedTuple):
    """Successful resolution: file exists and anchor (if any) is valid.

    Attributes:
        target: Absolute canonical path of the resolved target file.
    """

    target: Path


# Public union type — callers should pattern-match on the concrete type.
ResolveOutcome = PathTraversal | FileNotFound | AnchorMissing | Resolved


def is_site_alias_href(path_part: str) -> bool:
    """Return ``True`` for the ``@site/`` alias family, which is root-relative."""
    return path_part.startswith("@site/")


def is_emitted_verbatim(path_part: str) -> bool:
    """Return ``True`` if MkDocs emits *path_part* into the HTML unchanged.

    Measured against a real ``mkdocs build`` rather than inferred: a relative
    link is rewritten when its literal path names a file in the source tree
    (``target/page.md``, ``assets/pic.png``), and passed through when it does
    not -- which covers the extensionless form, the trailing-slash directory
    form, and ``.html``.  Those three are the spellings whose depth the
    generator never corrects, so they are the ones the browser resolves against
    the page URL.
    """
    if path_part.endswith("/"):
        return True
    suffix = PurePosixPath(path_part).suffix.lower()
    return suffix == "" or suffix in (".html", ".htm")


def href_resolution_base(source_file: Path, path_part: str, *, use_directory_urls: bool) -> Path:
    """The directory a relative *path_part* resolves against, as a browser does.

    **This is the single definition of the boundary.** Every consumer reads it;
    no consumer computes a base of its own. Before consolidation the same
    decision existed in four implementations -- ``resolve_href_target`` here,
    ``VSMBrokenLinkRule._to_canonical_url``, ``vsm.py``'s route resolver, and two
    inline arithmetics in ``incremental.py`` -- and they did not agree.

    With ``use_directory_urls`` (MkDocs' default) a page ``a/b/leaf.md`` is
    served at ``/a/b/leaf/``: one path segment deeper than its source directory
    ``a/b/``. The generator rewrites a relative link only when its literal path
    names a file in the tree, so any spelling it emits verbatim
    (:func:`is_emitted_verbatim`) is resolved by the browser against that deeper
    URL directory and needs one ``..`` more than source-tree arithmetic
    suggests. ``index.md`` / ``README.md`` serve at their own directory and gain
    no segment, so they are exempt.

    Pure arithmetic -- ``Path.parent`` / ``Path.with_suffix`` only. No ``stat``,
    no ``resolve()``, no symlink traversal: callers rely on this being lexical.

    Args:
        source_file: Absolute path of the file containing the link.
        path_part:   Decoded, backslash-normalised path component of the href.
        use_directory_urls: The site generator's setting, read from the adapter
            (never from ``ZenzicConfig``, which carries no such field).

    Returns:
        ``source_file.with_suffix("")`` when the page URL is one segment deeper,
        otherwise ``source_file.parent``.
    """
    if (
        use_directory_urls
        and path_part
        and not path_part.startswith("/")
        and not is_site_alias_href(path_part)
        and is_emitted_verbatim(path_part)
        and source_file.stem not in ("index", "README")
    ):
        return source_file.with_suffix("")
    return source_file.parent


def page_url_depth(source_file: Path, docs_root: Path, *, use_directory_urls: bool) -> int:
    """How many path segments the page's own URL has — what a relative href can absorb.

    ``a/b/leaf.md`` is served at ``/a/b/leaf/`` with directory URLs: three
    segments, so three ``..`` hops reach the site root and a fourth cannot land
    inside the site at all.  ``a/b/index.md`` is served at ``/a/b/`` and gains no
    segment.  With flat URLs the page keeps its own directory's depth.

    Pure arithmetic on the path; no filesystem access.
    """
    try:
        rel = source_file.relative_to(docs_root)
    except ValueError:
        return 0
    parts = list(rel.parts)
    if not parts:
        return 0
    if rel.stem in ("index", "README") or not use_directory_urls:
        return len(parts) - 1
    return len(parts)


def traversal_intent(path_part: str, *, page_url_depth: int = 0) -> Literal["system"] | None:
    """Whether *path_part* names an OS system location, as a fact about the href.

    **One signal, deliberately.** An earlier design added a second -- more
    leading ``..`` hops than the page URL has segments -- on the reasoning that
    intent should never depend on where the href resolves. That reasoning is
    right for *classification* and wrong for *containment*, and the difference
    is what the test suite caught:

    * ``../../sibling-repo/README.md`` leaves ``docs_root`` and names nothing
      systemic. No hop count identifies it, because whether two hops escape
      depends on where the page sits -- which is a containment question, and
      containment needs the resolved target and the configured roots.
    * Making the hop signal forgiving enough for the blog (whose plugin serves
      ``docs/blog/posts/X.md`` at ``/blog/YYYY/MM/DD/slug/``, so neither the
      path depth nor the URL depth is derivable from the other) made it blind to
      the case above -- a Tier-0 false negative.

    So containment stays where it was: resolved-target arithmetic against
    ``docs_root`` and ``repo_root``, which are engine configuration rather than
    anything an author controls. This function answers only the question that
    *is* textual -- "does this href name a system location?" -- and it exists so
    the broken-link path and the security tier consult **one** decision instead
    of each guessing what the other will claim.

    ``page_url_depth`` is accepted and unused, kept so callers that already
    compute it need not change if a depth-aware signal is ever justified.

    Delegates to ``_classify_traversal_intent``, which classifies by destination
    rather than by substring, percent-decodes repeatedly, and is case- and
    separator-insensitive -- so ``..`` with a backslash, ``%2e%2e`` and ``ETC``
    are covered, while a section legitimately named ``usr/`` is not. Neither can
    see a symlink inside ``docs/`` pointing out; that is beyond any text-only
    instrument.
    """
    if not path_part:
        return None
    normalised = path_part.replace("\\", "/")
    hops = 0
    for segment in normalised.split("/"):
        if segment == "..":
            hops += 1
        elif segment in ("", "."):
            continue
        else:
            break

    # Only an href that actually attempts to leave is a candidate. A plain
    # relative link into a section named `etc/` leaves nothing, and claiming it
    # makes the security tier own the href -- so broken-link checking skips it
    # as "security's" and the broken link is reported by nobody.
    if hops == 0 and not path_part.startswith("/"):
        return None

    from zenzic.core.validator import _classify_traversal_intent

    return "system" if _classify_traversal_intent(path_part) == "suspicious" else None


def resolve_href_target(
    source_file: Path,
    path_part: str,
    docs_root_str: str,
    repo_root_str: str,
    *,
    use_directory_urls: bool = True,
) -> str:
    """Resolve a decoded, backslash-normalised href path to an absolute path string.

    Applies the same alias rules as :meth:`InMemoryPathResolver._build_target`,
    the single source of truth for these rules: a leading
    ``/`` resolves against ``docs_root``; ``@site/docs/`` maps to ``docs_root``;
    ``@site/`` (not followed by ``docs/``) maps to ``repo_root``; anything else
    resolves relative to ``source_file``'s own directory. Pure string
    arithmetic (``os.path.normpath``) — no I/O, no ``Path.exists()``.

    ``docs_root_str``/``repo_root_str`` are pre-computed ``str(Path)`` forms,
    matching this module's hot-path convention of never allocating a new
    string from a ``Path`` on every call — callers compute them once.

    Used both by :class:`InMemoryPathResolver` (markdown-link resolution
    against pre-loaded content) and by :mod:`zenzic.core.incremental`'s
    non-markdown asset existence check, so both consumers agree on what an
    ``@site/`` alias means instead of one of them re-deriving it independently.
    """
    if path_part.startswith("/"):
        raw = docs_root_str + os.sep + path_part.lstrip("/")
    elif path_part.startswith("@site/docs/"):
        raw = docs_root_str + os.sep + path_part[len("@site/docs/") :]
    elif path_part.startswith("@site/"):
        raw = repo_root_str + os.sep + path_part[len("@site/") :]
    else:
        raw = (
            str(href_resolution_base(source_file, path_part, use_directory_urls=use_directory_urls))
            + os.sep
            + path_part
        )
    return os.path.normpath(raw)


# ─── InMemoryPathResolver ──────────────────────────────────────────────────────


class InMemoryPathResolver:
    """Engine-agnostic, pure in-memory resolver for Markdown internal links.

    Resolves ``[text](href)`` link targets against a pre-built snapshot of the
    documentation tree.  The same instance is safe to call repeatedly because
    it holds no mutable state after construction.

    The resolver enforces three invariants:

    1. **Zero I/O** — no filesystem calls after construction.
    2. **Windows normalisation** — backslash separators in hrefs are
       converted to ``/`` before any processing.
    3. **Credential Scanner** — any href whose normalised path resolves outside
       ``root_dir`` produces :class:`PathTraversal`.

    **Performance design:** the ``resolve()`` hot path allocates zero
    ``pathlib.Path`` objects after construction.  Containment is checked via
    a pre-computed string prefix; file lookup is a single ``dict.get()`` on a
    flat map built once in ``__init__``.

    Args:
        root_dir: Absolute, canonical root of the documentation tree.
            Must contain no ``..`` segments and must not be a symlink —
            the credential scanner relies on this boundary being trustworthy.
        md_contents: Mapping of absolute resolved ``Path`` → raw Markdown text.
        anchors_cache: Mapping of absolute resolved ``Path`` → set of anchor
            slugs pre-computed from headings.
    """

    __slots__ = (
        "_root_dir",
        "_root_str",
        "_root_prefix",
        "_repo_root_str",
        "_repo_root_prefix",
        "_repo_root_nc_str",
        "_repo_root_nc_prefix",
        "_md_contents",
        "_anchors_cache",
        "_lookup_map",
        "_use_directory_urls",
        "_allowed_root_pairs",
        "_allowed_root_pairs_nc",
    )

    def __init__(
        self,
        root_dir: Path,
        md_contents: dict[Path, str],
        anchors_cache: dict[Path, set[str]],
        repo_root: Path | None = None,
        allowed_roots: list[Path] | None = None,
        use_directory_urls: bool = True,
    ) -> None:
        self._root_dir: Path = self._coerce_path(root_dir)

        # Directory URLs put every non-index page one path segment deeper than
        # its source directory, which changes what a relative link the site
        # generator does NOT rewrite resolves to.  See _url_base_for.
        self._use_directory_urls: bool = bool(use_directory_urls)

        # Pre-compute string forms of root_dir once so the hot path never
        # touches pathlib during the credential scanner check.
        self._root_str: str = str(self._root_dir)
        self._root_prefix: str = self._root_str + os.sep

        # Multi-root: the primary docs_root is always authorised.
        # Additional roots (e.g. i18n locale directories passed by the
        # validator) extend the boundary so that cross-locale relative links
        # are validated rather than mis-classified as PathTraversal.
        # Stored as (root_str, root_prefix) tuples for zero-allocation O(1)
        # prefix checks in the hot path — identical design to _root_prefix.
        _extra = [self._coerce_path(r) for r in (allowed_roots or [])]
        _seen: set[str] = set()
        _pairs: list[tuple[str, str]] = []
        for _r in [self._root_dir, *_extra]:
            _s = str(_r)
            if _s not in _seen:
                _seen.add(_s)
                _pairs.append((_s, _s + os.sep))
        self._allowed_root_pairs: tuple[tuple[str, str], ...] = tuple(_pairs)
        # Normcase variants for the portability fix (KL-002 / CEO-203):
        # os.path.normcase maps paths to the filesystem's canonical case form
        # (lowercase on NTFS/APFS, identity on Linux).  Used only in the
        # Boundary check so that mixed-case legitimate paths on
        # case-insensitive filesystems are not mis-classified as traversals.
        self._allowed_root_pairs_nc: tuple[tuple[str, str], ...] = tuple(
            (os.path.normcase(s), os.path.normcase(p)) for s, p in self._allowed_root_pairs
        )

        # repo_root is the project root for @site/ alias resolution.
        # Defaults to root_dir when not provided (no @site/ links expected).
        _repo = self._coerce_path(repo_root) if repo_root is not None else self._root_dir
        self._repo_root_str: str = str(_repo)
        self._repo_root_prefix: str = self._repo_root_str + os.sep
        self._repo_root_nc_str: str = os.path.normcase(self._repo_root_str)
        self._repo_root_nc_prefix: str = os.path.normcase(self._repo_root_prefix)

        # Store coerced maps for anchor validation (Path keys needed there).
        self._md_contents: dict[Path, str] = {
            self._coerce_path(k): v for k, v in md_contents.items()
        }
        self._anchors_cache: dict[Path, set[str]] = {
            self._coerce_path(k): v for k, v in anchors_cache.items()
        }

        # ── Flat lookup map: str(variant) → canonical Path ────────────────────
        # For every file in md_contents, pre-register three lookup keys:
        #   1. str(file)                — exact match          (guide/install.md)
        #   2. str(file.with_suffix("")) — implicit .md suffix  (guide/install)
        #   3. str(file.parent)          — directory index       (guide/)
        #      (only when file.name == "index.md")
        #
        # Result: _lookup(target_str) is a single O(1) dict.get() with zero
        # Path allocations, replacing three Path constructions + three lookups.
        lookup_map: dict[str, Path] = {}
        for canonical in self._md_contents:
            key = str(canonical)
            lookup_map[key] = canonical
            if canonical.suffix:
                lookup_map[str(canonical.with_suffix(""))] = canonical
            if canonical.name == "index.md":
                lookup_map[str(canonical.parent)] = canonical
        self._lookup_map: dict[str, Path] = lookup_map

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve(self, source_file: Path, href: str) -> ResolveOutcome:
        """Resolve *href* as seen from *source_file*.

        The hot path is allocation-free: all intermediate representations are
        plain strings until the final ``Resolved(target=...)`` NamedTuple.

        Args:
            source_file: Absolute path of the file that contains the link.
            href: Raw link target string as extracted from the Markdown source.
                May contain percent-encoding, a fragment, and/or Windows
                backslashes — all are normalised internally.

        Returns:
            :class:`Resolved` when the target exists and any anchor is valid.
            :class:`FileNotFound` when the target path is not in ``md_contents``.
            :class:`AnchorMissing` when the file exists but the anchor does not.
            :class:`PathTraversal` when the path escapes ``root_dir``.
        """
        source_file = self._coerce_path(source_file)

        parsed = urlsplit(href)
        path_part = unquote(self._normalize_href(parsed.path))
        fragment = parsed.fragment

        # _build_target returns a str — no Path allocation in the hot path.
        target_str = self._build_target(source_file, path_part)

        # ── Directory-URL depth correction ────────────────────────────────────
        # MkDocs rewrites a relative link only when its literal path exists in
        # the source tree (measured against a real build: `page.md` and asset
        # paths are rewritten; extensionless, trailing-slash and `.html` forms
        # are emitted verbatim).  A verbatim link is resolved by the browser
        # against the page's *URL* directory, and with use_directory_urls every
        # non-index page is served one segment deeper than its source directory
        # -- `a/b/leaf.md` at `/a/b/leaf/`.  So a verbatim link needs one more
        # `..` than source-tree arithmetic suggests.  Index pages serve at
        # their own directory and gain no segment, so they are exempt.
        # ── Credential scanner: O(1) normcase string prefix check ──────────────────────────
        # @site/ links resolve relative to repo_root; all other links must stay
        # within an authorised root.  For @site/ we keep the single repo_root
        # boundary; for regular links we check all allowed_roots (docs_root +
        # any i18n locale directories) so that cross-locale relative links are
        # not mis-classified as path traversals.
        # os.path.normcase is applied to the target ONLY for the boundary
        # comparison — case-insensitive filesystems (APFS/NTFS) otherwise
        # produce false-positive PathTraversal for legitimately-capitalised
        # path segments.  The original target_str is preserved for file lookup.
        _target_nc = os.path.normcase(target_str)
        is_site_alias = path_part.startswith("@site/")
        if is_site_alias:
            path_ok = _target_nc == self._repo_root_nc_str or _target_nc.startswith(
                self._repo_root_nc_prefix
            )
        else:
            path_ok = any(
                _target_nc == nc_str or _target_nc.startswith(nc_prefix)
                for nc_str, nc_prefix in self._allowed_root_pairs_nc
            )
        if not path_ok:
            return PathTraversal(raw_href=href)

        # ── Lookup: single dict.get() — O(1), zero Path constructions ────────
        resolved = self._lookup_map.get(target_str)
        if resolved is None:
            return FileNotFound(path_part=path_part)

        # ── Anchor validation ─────────────────────────────────────────────────
        if fragment:
            anchors = self._anchors_cache.get(resolved, set())
            if fragment.lower() not in anchors:
                return AnchorMissing(
                    path_part=path_part,
                    anchor=fragment,
                    resolved_file=resolved,
                )

        return Resolved(target=resolved)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _coerce_path(p: object) -> Path:
        """Force-cast any incoming value to ``pathlib.Path``.

        Called on every path arriving from an external mapping.  A ``str``,
        a ``PurePosixPath``, or any other object with a meaningful ``__str__``
        is coerced silently rather than raising an ``AttributeError`` deep in
        the resolution pipeline.

        Args:
            p: Any object that should represent a filesystem path.

        Returns:
            A ``pathlib.Path`` wrapping the canonical string form of *p*.
        """
        if isinstance(p, Path):
            return p
        return Path(str(p))

    @staticmethod
    def _normalize_href(href: str) -> str:
        """Replace Windows backslash separators with forward slashes.

        Authors on Windows may write ``..\\guide.md`` or ``sub\\page.md``.
        Normalising to ``/`` ensures identical resolution on POSIX hosts.

        Args:
            href: Raw href string from the Markdown source.

        Returns:
            Equivalent href using only ``/`` as path separator.
        """
        return href.replace("\\", "/")

    def _build_target(self, source_file: Path, path_part: str) -> str:
        """Compute the normalised absolute target path as a plain string.

        Returns a ``str`` (not a ``Path``) so the caller can use it directly
        in string comparisons and dict lookups without any further allocation.

        ``os.path.normpath`` is pure C string arithmetic — no ``stat()``,
        no ``readlink()``, no kernel calls.  It collapses all ``.`` and ``..``
        segments, which is what makes the credential scanner work: ``../../../../etc/passwd``
        is reduced to ``/etc/passwd`` before the prefix check, so the traversal
        is always caught.

        Args:
            source_file: The absolute path of the file containing the link.
            path_part: Decoded, backslash-normalised path component of the href.

        Returns:
            Normalised absolute path string with all ``.`` and ``..`` resolved.
        """
        return resolve_href_target(
            source_file,
            path_part,
            self._root_str,
            self._repo_root_str,
            use_directory_urls=self._use_directory_urls,
        )
