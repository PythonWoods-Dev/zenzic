# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Filesystem scanning utilities: repo root discovery, orphan page detection,
placeholder scanning, and the Two-Pass Reference Pipeline.

v0.2.0 additions
----------------
* ``ReferenceScanner`` — stateful per-file scanner implementing the three-phase
  pipeline (Harvest → Cross-Check → Integrity Report).
* ``check_image_alt_text`` — pure function that flags images without alt text.
* ``scan_docs_references`` — I/O wrapper that runs ReferenceScanner over every
  .md file under docs/ and returns consolidated results.
"""

from __future__ import annotations

import fnmatch
import posixpath
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit

from zenzic.core import regex as re
from zenzic.core.credentials import (
    SecurityFinding,
    scan_line_for_forbidden_terms,
    scan_lines_with_lookback,
    scan_url_for_secrets,
)
from zenzic.core.discovery import (
    DOC_SUFFIXES,
    build_content_mounts,
    iter_extra_content_markdown_sources,
    iter_locale_markdown_sources,
    iter_markdown_sources,
    walk_files,
)
from zenzic.core.reporter import Finding
from zenzic.core.rules import AdaptiveRuleEngine, BaseRule
from zenzic.core.validator import LinkValidator, PolyglotExtractor
from zenzic.models.config import (
    ZenzicConfig,
)
from zenzic.models.references import IntegrityReport, ReferenceFinding, ReferenceMap


if TYPE_CHECKING:
    from zenzic.core.adapters._base import BaseAdapter
    from zenzic.core.exclusion import LayeredExclusionManager


# ─── Code-asset suffix guard (Z405 exemption) ────────────────────────────────
# Source code files are never documentation assets. When docs_dir is the repo
# root (standalone mode), walking src/ would otherwise produce Z405 findings
# for every .py/.ts file not referenced by any Markdown page. These files are
# logically application code — exempt from unused-asset enforcement.
# Discovery still walks them so the InMemoryPathResolver can resolve links
# that cross the docs/source boundary (e.g. README linking to a source file).
CODE_ASSET_SUFFIXES: frozenset[str] = frozenset(
    {
        # Python
        ".py",
        ".pyi",
        # TypeScript / JavaScript variants not already in SYSTEM_EXCLUDED_FILE_PATTERNS
        ".ts",
        ".tsx",
        ".jsx",
        ".mjs",
        ".cjs",
        # Systems languages
        ".rs",
        ".go",
        ".c",
        ".cpp",
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".hh",
        ".cs",
        ".swift",
        # JVM
        ".java",
        ".kt",
        ".kts",
        ".scala",
        # Scripting
        ".rb",
        ".php",
        ".lua",
        ".pl",
        ".pm",
        # Functional
        ".ex",
        ".exs",
        ".hs",
        ".lhs",
        # Data / query
        ".sql",
        # Build / infra
        ".nix",
        ".tf",
    }
)


# ─── Reference pipeline regexes ───────────────────────────────────────────────

# Reference definition: [id]: url  (up to 3 leading spaces per CommonMark §4.7)
# Optional title on the same line is ignored (we only need the URL for credential scan).
_RE_REF_DEF = re.compile(r"^ {0,3}\[([^\]]+)\]:\s+(\S+)")

# Reference link usage: [text][id] or [text][] (collapsed reference).
_RE_REF_LINK = re.compile(r"(\[([^\]]*)\]\[([^\]]*)\])")

# Shortcut reference link: [text] with semantic filters applied in code to
# exclude image refs and full/collapsed ref tails.
_RE_REF_SHORTCUT = re.compile(r"\[([^\]]+)\]")

# Inline image: ![alt](url)
_RE_IMAGE_INLINE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# HTML image tag — captures the entire tag for alt extraction
_RE_HTML_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_RE_HTML_ALT = re.compile(r'\balt=["\']([^"\']*)["\']', re.IGNORECASE)


_MARKDOWN_ASSET_LINK_RE = re.compile(
    r"\[.*?\]\((.*?)\)|<img.*?src=[\"'](.*?)[\"'].*?>|<a.*?href=[\"'](.*?)[\"'].*?>"
)
# Inline code span — erased before link extraction to avoid false positives.
_INLINE_CODE_RE = re.compile(r"`[^`]+`")


def find_repo_root(*, fallback_to_cwd: bool = False, search_from: Path | None = None) -> Path:
    """Walk upward from *search_from* (or CWD) until a Zenzic project root marker is found.

    Root markers (first match wins, checked in order):
    - ``.git/``  — universal VCS marker.
    - ``.zenzic.toml`` — Zenzic's own configuration file.

    Using engine-neutral markers keeps the Core independent of any specific
    documentation build engine (e.g. ``mkdocs.yml`` is intentionally excluded).

    This is more robust than ``Path(__file__).parents[N]`` because it works
    regardless of where the CLI is invoked from inside the repo.

    Args:
        fallback_to_cwd: When *True* and no root marker is found, return the
            starting path instead of raising.  Use this only for bootstrap
            commands (``zenzic init``) that are explicitly designed to create a
            project root from scratch — the "Genesis Fallback".
        search_from: Optional starting path for the upward search.  When
            provided, the search begins here instead of ``Path.cwd()``.
            CEO-052 "The Sovereign Root Fix": pass the explicit target path so
            the project config follows the target, not the caller.

    Raises:
        RuntimeError: if no root marker is found in any ancestor and
            ``fallback_to_cwd`` is *False*.
    """
    start = search_from.resolve() if search_from is not None else Path.cwd().resolve()
    for candidate in [start, *start.parents]:
        if (
            (candidate / ".git").is_dir()
            or (candidate / ".zenzic.toml").is_file()
            or (candidate / "zensical.toml").is_file()
            or (candidate / "mkdocs.yml").is_file()
        ):
            return candidate

    if fallback_to_cwd:
        return start

    raise RuntimeError(
        "Could not locate repo root: no .git directory or .zenzic.toml found in any "
        f"ancestor of {start}. Run Zenzic from inside the repository."
    )


# ─── Pure / I/O-agnostic functions ────────────────────────────────────────────


def calculate_orphans(all_md: set[str], nav_paths: set[str] | frozenset[str]) -> list[str]:
    """Pure function: return sorted list of .md paths present in all_md but absent from nav_paths.

    Args:
        all_md: Set of all .md src_uri paths (relative to docs root).
        nav_paths: Set of .md src_uri paths explicitly listed in the nav.

    Returns:
        Sorted list of orphaned paths.
    """
    return sorted(all_md - nav_paths)


def _map_credential_to_finding(sf: SecurityFinding, repo_root: Path) -> Finding:
    """Convert a :class:`SecurityFinding` into a reporter :class:`Finding`.

    This is the **sole authorised bridge** between the credential detection layer
    and the ZenzicReporter.  It is extracted as a standalone pure function so
    that mutation testing can target it directly (see the Mutation Gate in
    ``CONTRIBUTING.md``, Obligation 4 — "The Invisible", "The Amnesiac", and
    "The Silencer" mutants must all be killed here).

    Args:
        sf: A secret detection result from :func:`~zenzic.core.credentials.scan_line_for_secrets`,
            :func:`~zenzic.core.credentials.scan_url_for_secrets`, or
            :func:`~zenzic.core.credentials.scan_line_for_forbidden_terms`.
        repo_root: Absolute path to the repo root directory used to compute
            a project-relative display path.

    Returns:
        A :class:`~zenzic.core.reporter.Finding` ready for the ZenzicReporter
        pipeline.  Z204 FORBIDDEN_TERM findings use ``severity="security_breach"``
        with code ``"Z204"``; all other credential scanner findings use ``"Z201"``.
    """
    try:
        rel = str(sf.file_path.relative_to(repo_root))
    except ValueError:
        rel = str(sf.file_path)

    if sf.secret_type == "FORBIDDEN_TERM":
        return Finding(
            rel_path=rel,
            line_no=sf.line_no,
            code="Z204",
            severity="security_breach",
            message=f"Forbidden term detected — remove from documentation: '{sf.match_text}'",
            source_line=sf.url,
            col_start=sf.col_start,
            match_text=sf.match_text,
        )

    return Finding(
        rel_path=rel,
        line_no=sf.line_no,
        code="Z201",
        severity="security_breach",
        message=f"Secret detected ({sf.secret_type}) — rotate immediately.",
        source_line=sf.url,
        col_start=sf.col_start,
        match_text=sf.match_text,
    )


# Strips YAML frontmatter (leading ---...--- block).
_FRONTMATTER_RE: re.RegexPattern = re.compile(r"\A\s*---\s*\n.*?\n---\s*\n?", re.DOTALL)
# Strips MDX comments {/* ... */} — invisible in the rendered page.
_MDX_COMMENT_RE: re.RegexPattern = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
# Strips HTML comments <!-- ... --> — also invisible.
_HTML_COMMENT_RE: re.RegexPattern = re.compile(r"<!--.*?-->", re.DOTALL)


def _first_content_line(text: str) -> int:
    """Return the 1-based line number of the first prose content line.

    Skips, in order:

    1. Leading HTML comments (``<!-- … -->``) — may span multiple lines.
    2. Leading MDX comments (``{/* … */}``) — may span multiple lines.
    3. YAML frontmatter (``--- … ---`` block).
    4. Blank lines interspersed among the above.

    This ensures Z502 short-content findings point at actual prose, not at
    SPDX licence headers (``<!-- SPDX-FileCopyrightText: … -->``) or at the
    frontmatter delimiters (``---``).
    """
    lines = text.splitlines()
    n = len(lines)
    i = 0

    # ── Phase 1: skip leading comments and blank lines ────────────────
    in_html = False
    in_mdx = False
    while i < n:
        stripped = lines[i].strip()
        if in_html:
            if "-->" in lines[i]:
                in_html = False
            i += 1
            continue
        if in_mdx:
            if "*/" in lines[i]:
                in_mdx = False
            i += 1
            continue
        if stripped.startswith("<!--"):
            if "-->" not in lines[i]:
                in_html = True
            i += 1
            continue
        if stripped.startswith("{/*"):
            if "*/" not in lines[i]:
                in_mdx = True
            i += 1
            continue
        if stripped == "":
            i += 1
            continue
        break  # first non-comment, non-blank line

    # ── Phase 2: skip YAML frontmatter block (--- … ---) ─────────────
    if i < n and lines[i].strip() == "---":
        i += 1  # skip opening ---
        while i < n and lines[i].strip() != "---":
            i += 1
        if i < n:
            i += 1  # skip closing ---

    # ── Phase 3: skip blank lines after frontmatter ───────────────────
    while i < n and lines[i].strip() == "":
        i += 1

    return i + 1  # 1-based


def _visible_word_count(text: str) -> int:
    """Return the number of prose words in *text*, excluding invisible markup.

    Strips MDX and HTML comments **first**, then YAML frontmatter.  The ordering
    is load-bearing: MDX files often open with a ``{/* SPDX … */}`` licence
    header *before* the ``---`` block.  If frontmatter stripping runs first,
    ``_FRONTMATTER_RE`` (anchored to ``\\A``) fails to match because ``{`` is not
    whitespace, leaving the entire YAML block counted as prose words.  Stripping
    comments first guarantees the frontmatter lands at the start of the string
    where the regex can anchor correctly.
    """
    # Strip invisible comments first — they may precede YAML frontmatter.
    text = _MDX_COMMENT_RE.sub("", text)
    text = _HTML_COMMENT_RE.sub("", text)
    # Frontmatter is now at \A — strip it.
    text = _FRONTMATTER_RE.sub("", text)
    return len(text.split())


def check_asset_references(text: str, page_dir: str = "") -> set[str]:
    """Pure function: extract normalised asset paths referenced in markdown text.

    Delegates AST Reference Link Definition parsing ([label]: dest) and HTML node
    extraction to PolyglotExtractor.

    Args:
        text: Raw markdown content.
        page_dir: POSIX directory of the page relative to docs root (e.g. ``"guide"``).
                  Pass an empty string for pages at the root.

    Returns:
        Set of normalised asset paths relative to docs root.
    """
    from zenzic.core.validator import PolyglotExtractor

    extractor = PolyglotExtractor()
    referenced: set[str] = set()

    # 1. AST Reference Link Definitions ([label]: dest) from PolyglotExtractor
    for ref_node in extractor.extract_ref_defs(text):
        url = ref_node.dest
        if not url or url.startswith(("http://", "https://", "data:", "#")):
            continue
        clean_url = unquote(url.split("?")[0].split("#")[0])
        base = page_dir if page_dir else "."
        normalized = posixpath.normpath(posixpath.join(base, clean_url))
        if not normalized.startswith(".."):
            referenced.add(normalized)

    # 2. Native HTML tags (<a>, <img>) from PolyglotExtractor
    for html_node in extractor.extract(text):
        html_url: str | None = html_node.href
        if not html_url or html_url.startswith(("http://", "https://", "data:", "#")):
            continue
        clean_url = unquote(html_url.split("?")[0].split("#")[0])
        base = page_dir if page_dir else "."
        normalized = posixpath.normpath(posixpath.join(base, clean_url))
        if not normalized.startswith(".."):
            referenced.add(normalized)

    # 3. Standard inline markdown links [text](url)
    for match in _MARKDOWN_ASSET_LINK_RE.finditer(text):
        url = match.group(1) or match.group(2) or match.group(3)
        if not url or url.startswith(("http://", "https://", "data:", "#")):
            continue
        clean_url = unquote(url.split("?")[0].split("#")[0])
        base = page_dir if page_dir else "."
        normalized = posixpath.normpath(posixpath.join(base, clean_url))
        if not normalized.startswith(".."):  # skip paths that escape the docs root
            referenced.add(normalized)
    return referenced


def calculate_unused_assets(all_assets: set[str], used_assets: set[str]) -> list[str]:
    """Pure function: return sorted list of assets not referenced by any page.

    Args:
        all_assets: Set of all known asset paths (relative to docs root).
        used_assets: Set of asset paths referenced in documentation pages.

    Returns:
        Sorted list of unused asset paths.
    """
    return sorted(all_assets - used_assets)


# ─── CLI / I/O wrappers ───────────────────────────────────────────────────────


def find_orphans(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    config: ZenzicConfig,
    has_engine_config: bool | None = None,
    nav_paths: frozenset[str] | None = None,
    is_locale_dir: Callable[[str], bool] | None = None,
    ignored_patterns: set[str] | None = None,
    adapter: BaseAdapter | None = None,
    repo_root: Path | None = None,
) -> list[Path]:
    """Return docs/*.md files whose adapter status is ORPHAN_BUT_EXISTING.

    Args:
        docs_root: Resolved path to the documentation root.
        exclusion_manager: Layered exclusion manager (mandatory).
        config: Zenzic configuration model.
        has_engine_config: ``True`` when nav-based checks are meaningful.
        nav_paths: Nav-listed markdown paths (adapter-provided).
        is_locale_dir: Callback that identifies locale directory names.
        ignored_patterns: Adapter-specific filename patterns to skip.
        adapter: Adapter instance used for route classification.
        repo_root: Optional repository root used to build the adapter
            when adapter and other callbacks are omitted.

    Returns:
        List of Path objects relative to docs_root that are not in the nav.
    """
    if not docs_root.exists() or not docs_root.is_dir():
        return []

    if (
        adapter is None
        or has_engine_config is None
        or nav_paths is None
        or is_locale_dir is None
        or ignored_patterns is None
    ):
        if adapter is None:
            if repo_root is None:
                raise TypeError("find_orphans requires adapter or repo_root for adapter discovery")
            from zenzic.core.adapters._factory import get_adapter

            adapter = get_adapter(config.build_context, docs_root, repo_root)
        if has_engine_config is None:
            has_engine_config = adapter.has_engine_config()
        if nav_paths is None:
            nav_paths = adapter.get_nav_paths()
        if is_locale_dir is None:
            is_locale_dir = adapter.is_locale_dir
        if ignored_patterns is None:
            ignored_patterns = adapter.get_ignored_patterns()

    assert adapter is not None
    assert nav_paths is not None
    assert is_locale_dir is not None
    assert ignored_patterns is not None
    assert has_engine_config is not None

    if not has_engine_config:
        return []

    orphans: list[Path] = []
    for md_file in iter_markdown_sources(docs_root, config, exclusion_manager):
        rel = md_file.relative_to(docs_root)
        if rel.parts and is_locale_dir(rel.parts[0]):
            continue
        if any(fnmatch.fnmatch(md_file.name, pat) for pat in ignored_patterns):
            continue
        if adapter.get_route_info(rel).status == "ORPHAN_BUT_EXISTING":
            orphans.append(rel)

    return orphans


def find_unused_assets(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    config: ZenzicConfig,
    locale_roots: list[tuple[Path, str]] | None = None,
    content_roots: list[Path] | None = None,
    adapter_metadata_files: frozenset[str] = frozenset(),
) -> list[Path]:
    """Return asset files in docs/ that are not referenced by any markdown file.

    Args:
        docs_root: Resolved path to the documentation root.
        exclusion_manager: Layered exclusion manager (mandatory).
        config: Zenzic configuration model.
        locale_roots: Optional locale translation roots injected by caller.
        content_roots: Optional external markdown roots injected by caller.
        adapter_metadata_files: Filenames (basename only) that the active adapter
            consumes as configuration — excluded from Z903 (Level 1b guardrail).

    Returns:
        List of Path objects relative to docs_root that are unused.
    """
    if not docs_root.exists() or not docs_root.is_dir():
        return []

    all_assets: set[str] = set()
    # Asset-specific prune set: excluded_asset_dirs are layered on top of
    # the exclusion_manager's directory decisions.
    asset_extra_prune = set(config.excluded_asset_dirs)
    for file_path in walk_files(docs_root, asset_extra_prune, exclusion_manager):
        if file_path.is_dir() or file_path.is_symlink() or file_path.suffix in DOC_SUFFIXES:
            continue
        # Apply VCS and core engine exclusions
        if exclusion_manager.should_exclude_file(file_path, docs_root):
            continue
        rel_path = file_path.relative_to(docs_root)
        # Z405 must never consider dotfiles or files in dotdirectories as document assets
        if rel_path.name.startswith(".") or any(
            part.startswith(".") for part in rel_path.parts[:-1]
        ):
            continue
        if rel_path.suffix in {".css", ".js", ".yml", ".sarif", ".license", ".j2"}:
            continue
        if rel_path.suffix in CODE_ASSET_SUFFIXES:
            continue
        if rel_path.name in {"robots.txt", "_redirects", "CNAME", "sitemap.xml"}:
            continue
        if any(part in config.excluded_asset_dirs for part in rel_path.parts):
            continue
        rel_posix = rel_path.as_posix()
        if rel_posix in adapter_metadata_files or rel_path.name in adapter_metadata_files:
            continue
        if any(fnmatch.fnmatch(rel_posix, pat) for pat in config.excluded_build_artifacts):
            continue
        all_assets.add(rel_posix)

    if not all_assets:
        return []

    # Remove explicitly excluded assets.
    # Every entry in excluded_assets is treated as an fnmatch pattern
    # (relative to docs_dir).  Literal paths work as-is because fnmatch
    # treats a string without metacharacters as a literal match.
    excluded_patterns = [e.lstrip("/") for e in config.excluded_assets]
    if excluded_patterns:
        all_assets = {
            a for a in all_assets if not any(fnmatch.fnmatch(a, pat) for pat in excluded_patterns)
        }

    if not all_assets:
        return []

    used_assets: set[str] = set()
    for md_file in iter_markdown_sources(docs_root, config, exclusion_manager):
        content = md_file.read_text(encoding="utf-8")
        rel_md = md_file.relative_to(docs_root)
        page_dir = rel_md.parent.as_posix()
        if page_dir == ".":
            page_dir = ""
        used_assets |= check_asset_references(content, page_dir)

    # Also collect asset references cited from locale translation trees.
    if locale_roots:
        for locale_root, locale_name in locale_roots:
            for md_file, logical_rel in iter_locale_markdown_sources(
                locale_root, locale_name, config, exclusion_manager
            ):
                content = md_file.read_text(encoding="utf-8")
                page_dir = logical_rel.parent.as_posix()
                if page_dir == ".":
                    page_dir = ""
                used_assets |= check_asset_references(content, page_dir)

    if content_roots:
        for content_root, url_prefix in build_content_mounts(content_roots):
            for md_file, logical_rel in iter_extra_content_markdown_sources(
                content_root, url_prefix, config, exclusion_manager
            ):
                content = md_file.read_text(encoding="utf-8")
                page_dir = logical_rel.parent.as_posix()
                if page_dir == ".":
                    page_dir = ""
                used_assets |= check_asset_references(content, page_dir)

    return [Path(p) for p in calculate_unused_assets(all_assets, used_assets)]


def find_missing_directory_indices(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    config: ZenzicConfig,
    provides_index: Callable[[Path], bool],
) -> list[Path]:
    """Return directories that contain ``.md`` / ``.mdx`` source files but no
    engine-provided index page, indicating a potential 404 at the directory URL.

    The check is engine-aware via the injected ``provides_index`` callback so
    the scanner stays independent from adapter resolution.

    The docs root itself is excluded — a missing ``docs/index.*`` is reported
    only when it actually causes a 404 visible to end-users (i.e. sub-dirs).

    I/O is permitted here: this function is part of the discovery phase and
    calls :meth:`provides_index` exactly once per candidate directory.

    Args:
        docs_root: Resolved absolute path to the documentation root.
        exclusion_manager: Mandatory layered exclusion manager.
        config: Zenzic configuration model.
        provides_index: Callback that answers whether a directory has an index.

    Returns:
        List of :class:`~pathlib.Path` objects relative to *docs_root*,
        sorted lexicographically, for directories that lack an index page.
    """
    if not docs_root.exists() or not docs_root.is_dir():
        return []

    # Collect the set of unique parent directories that contain at least one
    # Markdown source file (excluding docs_root itself — the root index is a
    # separate concern handled in DIRETTIVA CEO 011).
    dirs_with_docs: set[Path] = set()
    for file_path in walk_files(docs_root, set(), exclusion_manager):
        if file_path.suffix.lower() in DOC_SUFFIXES and file_path.parent != docs_root:
            dirs_with_docs.add(file_path.parent)

    if not dirs_with_docs:
        return []

    missing: list[Path] = []
    for dir_abs in sorted(dirs_with_docs):
        if not provides_index(dir_abs):
            try:
                missing.append(dir_abs.relative_to(docs_root))
            except ValueError:
                missing.append(dir_abs)

    return missing


# ─── Two-Pass Reference Pipeline ──────────────────────────────────────────────

# Harvest event type aliases (yielded by ReferenceScanner.harvest())
# (lineno, "DEF",           (ref_id_norm, url))      — definition accepted
# (lineno, "DUPLICATE_DEF", (ref_id_norm, url))      — duplicate ignored
# (lineno, "IMG",           (alt_text, url))          — image found
# (lineno, "MISSING_ALT",   url)                      — image without alt-text
# (lineno, "SECRET",        SecurityFinding)          — secret detected by credential scanner

HarvestEvent = tuple[int, str, Any]


def _skip_frontmatter(
    fh: Any,
) -> Generator[tuple[int, str], None, None]:
    """Yield ``(lineno, line)`` pairs from an open file handle, skipping YAML frontmatter.

    Frontmatter is a leading ``---`` block that ends with ``---`` or ``...``.
    Every other line — including lines inside fenced code blocks — is yielded.
    This is the raw stream used by the credential scanner so that secrets embedded inside
    code examples are never invisible.

    Args:
        fh: An open text file handle positioned at the start of the file.

    Yields:
        ``(1-based line number, raw line string)`` for every non-frontmatter line.
    """
    in_frontmatter = False
    frontmatter_checked = False

    for lineno, line in enumerate(fh, start=1):
        stripped = line.strip()

        if not frontmatter_checked:
            frontmatter_checked = True
            if stripped == "---":
                in_frontmatter = True
                continue

        if in_frontmatter:
            if stripped in ("---", "..."):
                in_frontmatter = False
            continue

        yield lineno, line


def _iter_content_lines(
    file_path: Path,
) -> Generator[tuple[int, str], None, None]:
    """Stream non-code, non-frontmatter lines from a Markdown file one at a time.

    Opens the file in text mode and iterates line-by-line (no .read() /
    .readlines()).  Two categories of lines are silently skipped:

    * **YAML frontmatter**: A leading ``---`` block (line 1 only) is skipped in
      its entirety up to and including the closing ``---`` or ``...`` delimiter.
      This prevents reference definitions embedded in YAML from being harvested
      as Markdown content.
    * **Fenced code blocks**: Lines inside ``` or ~~~ fences are skipped so that
      example URLs inside code never trigger false positives.

    Use :func:`_skip_frontmatter` when the credential scanner needs to scan every line,
    including lines inside fenced blocks.

    Args:
        file_path: Path to the Markdown source file.

    Yields:
        ``(1-based line number, raw line string)`` for every content line.
    """
    in_block = False

    with file_path.open(encoding="utf-8") as fh:
        for lineno, line in _skip_frontmatter(fh):
            stripped = line.strip()

            # ── Fenced code block skip ────────────────────────────────────
            if not in_block:
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_block = True
                    continue
            else:
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    in_block = False
                continue  # always skip lines inside fenced block

            yield lineno, line


class ReferenceScanner:
    """Per-file stateful scanner implementing the Three-Phase Reference Pipeline.

    State lives entirely inside the instance via ``self.ref_map``.  There is no
    global scope pollution: create one ``ReferenceScanner`` per file.

    Usage::

        scanner = ReferenceScanner(Path("docs/guide.md"))

        # Pass 1 — drive the generator; bail immediately on SECRET events
        for event in scanner.harvest():
            lineno, event_type, data = event
            if event_type == "SECRET":
                raise SystemExit(2)  # or typer.Exit(2) in CLI layer

        # Pass 2 — resolve reference links (ref_map must be fully populated)
        cross_check_findings = scanner.cross_check()

        # Pass 3 — compute integrity score and collect all findings
        report = scanner.get_integrity_report(cross_check_findings)
    """

    def __init__(self, file_path: Path, config: ZenzicConfig | None = None) -> None:
        self.file_path = file_path
        self.ref_map: ReferenceMap = ReferenceMap()
        self._config = config or ZenzicConfig()
        self.suspicious_domains: list[ReferenceFinding] = []

    # ── Pass 1: Harvesting & Credential Scanner ────────────────────────────────

    def harvest(self) -> Generator[HarvestEvent, None, None]:
        """Pass 1: stream the file, extract reference definitions, run the credential scanner.

        Populates ``self.ref_map.definitions`` as a side effect.  Security
        findings are yielded immediately as ``("SECRET", SecurityFinding)``
        events so callers can abort with Exit Code 2 before Pass 2 begins.

        Uses two independent line streams from the same file:

        * **Credential stream** — every line except YAML frontmatter, including lines
          inside fenced code blocks.  Ensures that credentials in ``bash`` or
          unlabelled code examples are never invisible to the credential scanner.
        * **Content stream** — lines outside fenced blocks (``_iter_content_lines``).
          Used for reference-definition harvesting and alt-text detection so that
          example URLs inside code blocks never produce false positives.

        Reference definitions (``[id]: url``) are always outside fenced blocks by
        CommonMark §4.7 convention, so scanning them on the content stream is
        sufficient.  The credential scanner additionally scans every definition URL via
        ``scan_url_for_secrets`` to catch embedded secrets in reference URLs.

        Yields:
            ``(lineno, event_type, data)`` tuples.  See module-level type alias
            ``HarvestEvent`` for the full list of event types and data shapes.
        """
        # ── 1.a Credential scanner pass: scan EVERY line including YAML frontmatter ─
        # ZRT-001 fix: the credential scanner must have priority over ALL content, including
        # YAML frontmatter.  Frontmatter values (aws_key, api_token, ...) are
        # real secrets — we use raw enumerate() so no line is ever skipped.
        # The Content Stream (1.b below) still uses _iter_content_lines which
        # skips frontmatter correctly to avoid false-positive ref-def hits.
        secret_line_nos: set[int] = set()
        credential_events: list[HarvestEvent] = []
        with self.file_path.open(encoding="utf-8") as fh:
            for finding in scan_lines_with_lookback(enumerate(fh, start=1), self.file_path):
                credential_events.append((finding.line_no, "SECRET", finding))
                secret_line_nos.add(finding.line_no)

        # ── 1.a.2 Privacy Gate: scan for Z204 FORBIDDEN_TERM ─────────────────
        # Separate pass over the same file with the merged forbidden_patterns
        # list (populated from .zenzic.local.toml by config.load()).  Only
        # lines not already flagged by the credential scan are emitted to
        # avoid duplicate SecurityFinding entries for the same line.
        fp = self._config.forbidden_patterns if self._config else []
        if fp:
            fp_compiled = self._config.forbidden_patterns_compiled if self._config else None
            with self.file_path.open(encoding="utf-8") as fh:
                for lineno, raw_line in enumerate(fh, start=1):
                    if lineno in secret_line_nos:
                        continue
                    for finding in scan_line_for_forbidden_terms(
                        raw_line,
                        fp,
                        self.file_path,
                        lineno,
                        compiled_pattern=fp_compiled,
                    ):
                        credential_events.append((finding.line_no, "SECRET", finding))
                        secret_line_nos.add(finding.line_no)

        # ── 1.b Content pass: harvest ref-defs and alt-text (fences skipped) ─
        content_events: list[HarvestEvent] = []
        for lineno, line in _iter_content_lines(self.file_path):
            def_match = _RE_REF_DEF.match(line)
            if def_match:
                raw_id, url = def_match.group(1), def_match.group(2)
                accepted = self.ref_map.add_definition(raw_id, url, lineno)
                norm_id = raw_id.lower().strip()

                if accepted:
                    content_events.append((lineno, "DEF", (norm_id, url)))

                    # ── 1.c Credential scanner: scan URL for secrets ──────────────
                    for finding in scan_url_for_secrets(url, self.file_path, lineno):
                        # Only emit if scan_line_for_secrets hasn't already
                        # emitted a SECRET for this line (avoid duplicates).
                        if lineno not in secret_line_nos:
                            credential_events.append((lineno, "SECRET", finding))
                            secret_line_nos.add(lineno)
                else:
                    content_events.append((lineno, "DUPLICATE_DEF", (norm_id, url)))
                continue

            # Alt-text checking is now delegated to MissingAltTextRule (Z403)

        # Yield all events in line-number order
        yield from sorted(credential_events + content_events, key=lambda e: e[0])

    # ── Pass 2: Cross-Check & Validation ──────────────────────────────────────

    def cross_check(self) -> list[ReferenceFinding]:
        """Pass 2: resolve reference links against the populated ReferenceMap.

        Must be called **after** ``harvest()`` has been fully consumed so that
        ``self.ref_map.definitions`` is complete.

        Returns:
            List of :class:`ReferenceFinding` for dangling references (links
            that use an undefined ID).
        """
        findings: list[ReferenceFinding] = []

        for lineno, line in _iter_content_lines(self.file_path):
            # Blank out inline code to avoid false matches inside `[code][spans]`
            clean = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line)

            for m in _RE_REF_LINK.finditer(clean):
                text = m.group(2)
                ref_id = m.group(3) if m.group(3) else text  # collapsed ref
                url = self.ref_map.resolve(ref_id)
                if url is None:
                    norm_id = ref_id.lower().strip()
                    findings.append(
                        ReferenceFinding(
                            file_path=self.file_path,
                            line_no=lineno,
                            issue="Z301",
                            detail=(
                                f"Reference '[{text}][{ref_id}]' uses undefined ID '{norm_id}'."
                            ),
                            is_warning=False,
                        )
                    )

            # Shortcut reference links: [text] (CommonMark §4.7)
            for m in _RE_REF_SHORTCUT.finditer(clean):
                if m.start() > 0 and clean[m.start() - 1] == "]":
                    continue
                tail = clean[m.end() : m.end() + 1]
                if tail in "[(":
                    continue
                if tail == ":" and clean[: m.start()].strip() == "":
                    continue
                ref_id = m.group(1)
                self.ref_map.resolve(ref_id)  # mark as used if defined

        return findings

    # ── Pass 3: Cleanup & Metrics ──────────────────────────────────────────────

    def get_integrity_report(
        self,
        cross_check_findings: list[ReferenceFinding] | None = None,
        security_findings: list[SecurityFinding] | None = None,
    ) -> IntegrityReport:
        """Pass 3: compute integrity score and consolidate all findings.

        Args:
            cross_check_findings: Findings from :meth:`cross_check` (dangling
                refs).  Pass ``None`` or omit to skip.
            security_findings: Credential scanner findings collected during
                :meth:`harvest`.  Pass ``None`` or omit to skip.

        Returns:
            :class:`IntegrityReport` with the integrity score and the full
            ordered list of findings (errors first, warnings last).
        """
        findings: list[ReferenceFinding] = list(cross_check_findings or [])

        # Orphan definitions — defined but never used (warning)
        for norm_id in sorted(self.ref_map.orphan_definitions):
            url, def_line = self.ref_map.definitions[norm_id]
            findings.append(
                ReferenceFinding(
                    file_path=self.file_path,
                    line_no=def_line,
                    issue="Z302",
                    detail=(f"Reference '[{norm_id}]: {url}' is defined but never used."),
                    is_warning=True,
                )
            )

        # Duplicate definitions — subsequent occurrences ignored (warning)
        for norm_id in sorted(self.ref_map.duplicate_ids):
            url, def_line = self.ref_map.definitions[norm_id]
            findings.append(
                ReferenceFinding(
                    file_path=self.file_path,
                    line_no=def_line,
                    issue="Z303",
                    detail=(
                        f"Reference ID '[{norm_id}]' is defined more than once. "
                        "First definition wins (CommonMark §4.7)."
                    ),
                    is_warning=True,
                )
            )

        findings.extend(self.suspicious_domains)

        return IntegrityReport(
            file_path=self.file_path,
            score=self.ref_map.integrity_score,
            findings=findings,
            security_findings=list(security_findings or []),
        )


# ─── I/O wrapper: scan all docs ───────────────────────────────────────────────


def _scan_single_file(
    md_file: Path,
    config: ZenzicConfig,
    rule_engine: AdaptiveRuleEngine | None = None,
) -> tuple[IntegrityReport, ReferenceScanner | None]:
    """Run the Three-Phase Pipeline on one Markdown file.

    Returns the scanner alongside the report so callers that need the
    populated ``ref_map`` (e.g. for external URL registration) can reuse it
    without triggering a second read of the file.

    Args:
        md_file: Absolute path to the Markdown file to process.
        config: Zenzic configuration.
        rule_engine: Optional :class:`~zenzic.core.rules.AdaptiveRuleEngine` to apply
            after the reference pipeline.  When provided, the file is read once
            more as a string for the rule pass (rules receive the full text, not
            the line-by-line generator output).  When ``None`` or empty, the
            rule pass is skipped entirely.

    Returns:
        ``(report, scanner)`` where ``scanner`` is ``None`` when the credential scanner
        detected secrets (no external URLs should be registered from such files).
    """
    scanner = ReferenceScanner(md_file, config)
    security_findings: list[SecurityFinding] = []

    # Pass 1 — harvest; collect security findings
    for _lineno, event_type, data in scanner.harvest():
        if event_type == "SECRET":
            security_findings.append(data)

    # Pass 2 — cross-check (always runs; security findings are observer-only)
    cross_findings: list[ReferenceFinding] = scanner.cross_check()

    # Pass 3 — integrity report
    report = scanner.get_integrity_report(cross_findings, security_findings)

    # Rule Engine pass — applied after reference pipeline, only when configured.
    if rule_engine:
        text = md_file.read_text(encoding="utf-8")

        # Build SuppressionTracker for this file — required for Z603 DEAD_SUPPRESSION.
        # Importing here (deferred) avoids circular imports at module level.
        from zenzic.core.suppressions import SuppressionTracker

        # Pre-compute global suppression codes for this specific file
        # to prevent consuming redundant inline directives (ADR-084).
        globally_suppressed_codes: dict[str, list[str]] = {}
        if getattr(config, "governance", None):
            repo_root = config.origin_file.parent if config.origin_file is not None else Path.cwd()
            try:
                rel_path = md_file.relative_to(repo_root).as_posix()
            except ValueError:
                rel_path = md_file.as_posix()

            if config.governance.per_file_ignores:
                import fnmatch

                for pattern, codes in config.governance.per_file_ignores.items():
                    if fnmatch.fnmatch(rel_path, pattern):
                        for c in codes:
                            globally_suppressed_codes.setdefault(str(c).strip().upper(), []).append(
                                pattern
                            )

            if config.governance.directory_policies:
                import zenzic.core.regex as re
                from zenzic.core.exclusion import translate_glob_to_re2

                for pattern, codes in config.governance.directory_policies.items():
                    try:
                        compiled = re.compile(translate_glob_to_re2(pattern))
                        if compiled.fullmatch(rel_path):
                            for c in codes:
                                globally_suppressed_codes.setdefault(
                                    str(c).strip().upper(), []
                                ).append(pattern)
                    except Exception:
                        pass

        tracker = SuppressionTracker(
            md_file,
            text,
            globally_suppressed_codes=globally_suppressed_codes,
            global_tracker=getattr(config, "_global_tracker", None),
        )
        report.suppression_tracker = tracker

        # Use the tracker-aware variant so that:
        #   1. Suppressed findings are silently dropped.
        #   2. Each matching directive is marked consumed=True.
        report.rule_findings = rule_engine.run_with_tracker(md_file, text, tracker)

        # Z603 DEAD_SUPPRESSION — emit for every directive never consumed above.
        report.rule_findings += tracker.get_dead_suppressions()

    # Return scanner only when the file is secure — callers must not register
    # URLs from files that failed the credential scanner (they may embed leaked credentials).
    secure_scanner: ReferenceScanner | None = None if security_findings else scanner
    return report, secure_scanner


def _run_vsm_and_urp_pass(
    reports: list[IntegrityReport],
    md_files: list[Path],
    docs_root: Path,
    config: ZenzicConfig,
    rule_engine: AdaptiveRuleEngine | None,
    locale_roots: list[tuple[Path, str]] | None = None,
    content_roots: list[Path] | None = None,
    repo_root: Path | None = None,
    static_assets: set[Path] | None = None,
) -> None:
    """Run VSM building, VSMBrokenLinkRule, and URP checks over all scanned files."""
    from zenzic.core.adapter import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.resolver import InMemoryPathResolver, Resolved
    from zenzic.core.rules import (
        AdaptiveRuleEngine,
        ResolutionContext,
        RuleFinding,
        VSMBrokenLinkRule,
    )
    from zenzic.core.validator import (
        LinkInfo,
        PolyglotExtractor,
        _build_link_graph,
        _find_cycles_iterative,
        anchors_in_file,
    )
    from zenzic.models.vsm import build_vsm

    if not rule_engine:
        rule_engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])

    if repo_root is None:
        repo_root = find_repo_root(fallback_to_cwd=True, search_from=docs_root)

    adapter = get_adapter(config.build_context, docs_root, repo_root)

    anchors_cache: dict[Path, set[str]] = {}
    md_contents: dict[Path, str] = {}
    for f in md_files:
        if f.is_file():
            try:
                text = f.read_text(encoding="utf-8")
                md_contents[f] = text
                anchors_cache[f] = anchors_in_file(text)
            except OSError:
                pass

    vsm = build_vsm(
        adapter,
        docs_root,
        md_contents,
        anchors_cache=anchors_cache,
        extra_content_roots=content_roots,
        repo_root=repo_root,
        static_assets=static_assets,
    )

    orphaned_urls: set[str] = set()
    dead_end_urls: set[str] = set()
    if hasattr(adapter, "get_entry_points"):
        from zenzic.core.topology import detect_dead_ends, detect_orphans

        entry_points = adapter.get_entry_points(vsm)
        orphaned_urls = set(detect_orphans(vsm, entry_points))
        dead_end_urls = set(detect_dead_ends(vsm))

    links_cache: dict[Path, list[LinkInfo]] = {
        f: [
            LinkInfo(
                url=item.url,
                lineno=item.line_no,
                col_start=item.col_start,
                match_text=item.raw_text,
            )
            for item in PolyglotExtractor().extract_all_links(text)
            if item.node_type != "ref_def" and not item.suppressed
        ]
        for f, text in md_contents.items()
    }
    resolver = InMemoryPathResolver(docs_root, md_contents, anchors_cache, repo_root=repo_root)

    link_graph = _build_link_graph(links_cache, resolver, frozenset(md_contents.keys()))

    cycle_nodes = set(_find_cycles_iterative(link_graph))

    inc_engine = IncrementalAnalysisEngine(config, rule_engine, adapter, docs_root, repo_root)
    inc_engine.anchors_cache = anchors_cache

    use_dir_urls = getattr(config, "use_directory_urls", True)

    for r in reports:
        if not r.file_path.is_file():
            continue

        try:
            text = r.file_path.read_text(encoding="utf-8")
        except OSError:
            continue

        extracted_links = PolyglotExtractor().extract_all_links(text)
        context = ResolutionContext(
            docs_root=docs_root,
            source_file=r.file_path,
            use_directory_urls=use_dir_urls,
            config=config,
            adapter=adapter,
        )

        vsm_findings = rule_engine.run_vsm(
            r.file_path, text, vsm, anchors_cache, context, extracted_links=extracted_links
        )
        urp_findings = inc_engine._run_urp_checks(
            vsm,
            r.file_path,
            text,
            tracker=r.suppression_tracker,
            extracted_links=extracted_links,
            resolver=resolver,
        )

        if r.suppression_tracker is not None:
            active_vsm = [
                f
                for f in vsm_findings
                if not r.suppression_tracker.is_suppressed(f.line_no, f.rule_id)
            ]
            active_urp = [
                f
                for f in urp_findings
                if not r.suppression_tracker.is_suppressed(f.line_no, f.rule_id)
            ]
        else:
            active_vsm = vsm_findings
            active_urp = urp_findings

        r.rule_findings.extend(active_vsm)
        r.rule_findings.extend(active_urp)

        try:
            rel_posix = r.file_path.relative_to(docs_root).as_posix()
        except ValueError:
            rel_posix = r.file_path.absolute().as_posix()
        canonical_url = next(
            (route.url for route in vsm.values() if route.source == rel_posix), ""
        )
        if canonical_url:
            if canonical_url in orphaned_urls:
                if (
                    r.suppression_tracker is None
                    or not r.suppression_tracker.is_suppressed(1, "Z410")
                ):
                    r.rule_findings.append(
                        RuleFinding(
                            r.file_path,
                            1,
                            "Z410",
                            f"Document is isolated and unreachable from defined entry points: '{canonical_url}'",
                            severity="warning",
                            matched_line="",
                        )
                    )
            if canonical_url in dead_end_urls:
                if (
                    r.suppression_tracker is None
                    or not r.suppression_tracker.is_suppressed(1, "Z411")
                ):
                    r.rule_findings.append(
                        RuleFinding(
                            r.file_path,
                            1,
                            "Z411",
                            f"Document has no outgoing links and forms a structural dead end: '{canonical_url}'",
                            severity="warning",
                            matched_line="",
                        )
                    )

        if cycle_nodes and r.file_path in links_cache:
            for link in links_cache[r.file_path]:
                if not link.url.startswith(("http://", "https://", "mailto:", "#")):
                    match resolver.resolve(r.file_path, link.url):
                        case Resolved(target=target):
                            if target.as_posix() in cycle_nodes:
                                if (
                                    r.suppression_tracker is None
                                    or not r.suppression_tracker.is_suppressed(link.lineno, "Z106")
                                ):
                                    r.rule_findings.append(
                                        RuleFinding(
                                            r.file_path,
                                            link.lineno,
                                            "Z106",
                                            f"'{link.url}' is part of a circular link cycle",
                                            severity="error",
                                            matched_line="",
                                            col_start=link.col_start,
                                            match_text=link.match_text,
                                        )
                                    )

    if config.absolute_path_allowlist:
        used_allowlist: set[str] = set()
        for text in md_contents.values():
            for ext_link in PolyglotExtractor().extract_all_links(text):
                if ext_link.url.startswith("/"):
                    for prefix in config.absolute_path_allowlist:
                        if ext_link.url.startswith(prefix):
                            used_allowlist.add(prefix)
        unused = set(config.absolute_path_allowlist) - used_allowlist
        if unused and reports:
            config_file = repo_root / ".zenzic.toml"
            target_path = (
                config.origin_file
                if config.origin_file is not None
                else (config_file if config_file.is_file() else reports[0].file_path)
            )
            for entry in sorted(unused):
                reports[0].rule_findings.append(
                    RuleFinding(
                        target_path,
                        1,
                        "Z110",
                        f"{target_path.name}:1: Stale absolute_path_allowlist entry '{entry}': no link matched this prefix across all scanned files",
                        severity="warning",
                    )
                )


def _build_rule_engine(config: ZenzicConfig) -> AdaptiveRuleEngine | None:
    """Construct a :class:`~zenzic.core.rules.AdaptiveRuleEngine` from the config.

    Load order is deterministic:

    1. Built-in always-active rules (Z107, Z505, Z506).
    2. Z601 BRAND_OBSOLESCENCE — activated only when ``obsolete_names`` is set.
    3. Core rules registered via the ``zenzic.rules`` entry-point group.
    4. Regex rules from ``[[custom_rules]]``.
    5. External plugin rules explicitly listed in ``plugins = [...]``.

    Returns ``None`` when no rules are available.
    """
    from zenzic.core.rules import (  # deferred to keep import graph clean
        BrandObsolescenceRule,
        CircularAnchorRule,
        CredentialScannerRule,
        CustomRule,
        EmptyLinkRule,
        MalformedFrontmatterRule,
        MissingAltTextRule,
        PluginRegistry,
        UntaggedCodeBlockRule,
    )

    # Built-in rules are always active (no config gate required).
    built_in: list[BaseRule] = [
        CredentialScannerRule(),
        EmptyLinkRule(),
        MissingAltTextRule(),
        CircularAnchorRule(),
        MalformedFrontmatterRule(),
        UntaggedCodeBlockRule(),
    ]

    from zenzic.core.rules import (
        EmptySectionRule,
        ExcessiveSentenceLengthRule,
        HeadingHierarchyRule,
        PlaceholderRule,
        ShortContentRule,
    )

    built_in.append(ShortContentRule(config.placeholder_max_words))
    built_in.append(PlaceholderRule(config.placeholder_patterns_compiled))
    built_in.append(HeadingHierarchyRule())
    built_in.append(ExcessiveSentenceLengthRule(config.max_sentence_length))
    built_in.append(EmptySectionRule())
    if config.project_metadata.obsolete_names:
        built_in.append(BrandObsolescenceRule(config.project_metadata))

    registry = PluginRegistry()
    rules: list[BaseRule] = list(built_in)
    rules.extend(registry.load_core_rules())
    rules.extend(
        CustomRule(
            id=cr.id,
            pattern=cr.pattern,
            message=cr.message,
            severity=cr.severity,
        )
        for cr in config.custom_rules
    )
    rules.extend(registry.load_selected_rules(config.plugins))

    # 6. Auto-discover custom AST rules (v2) from .zenzic/rules/*.py
    repo_root = config.origin_file.parent if config.origin_file is not None else Path.cwd()
    custom_rules_dir = repo_root / ".zenzic" / "rules"
    if custom_rules_dir.is_dir():
        import importlib.util
        import sys

        from zenzic.core.rules import BaseRule, RuleFinding
        from zenzic.rules.base import BaseASTRule

        class FailedCustomRule(BaseRule):
            def __init__(self, rule_id: str, error_msg: str) -> None:
                self._rule_id = rule_id
                self.error_msg = error_msg

            @property
            def rule_id(self) -> str:
                return self._rule_id

            def check(self, file_path: Path, text: str) -> list[RuleFinding]:
                raise RuntimeError(self.error_msg)

        for py_file in sorted(custom_rules_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            rule_id_fallback = py_file.stem.upper()
            try:
                module_name = f"zenzic_custom_rule_{py_file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    found_rule = False
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseASTRule)
                            and attr is not BaseASTRule
                        ):
                            try:
                                rules.append(attr())  # type: ignore[call-arg]
                                found_rule = True
                            except Exception as exc:
                                rules.append(
                                    FailedCustomRule(
                                        rule_id=attr_name.upper(),
                                        error_msg=f"Failed to instantiate custom rule class '{attr_name}': {exc}",
                                    )
                                )
                                found_rule = True
                    if not found_rule:
                        # No subclass of BaseASTRule found in file
                        pass
            except Exception as exc:
                rules.append(
                    FailedCustomRule(
                        rule_id=rule_id_fallback,
                        error_msg=f"Failed to load custom rule module from {py_file}: {exc}",
                    )
                )

    # Deduplicate by rule_id while preserving declaration priority.
    deduped: list[BaseRule] = []
    seen: set[str] = set()
    for rule in rules:
        rid = rule.rule_id
        if rid in seen:
            continue
        seen.add(rid)
        deduped.append(rule)

    if not deduped:
        return None
    return AdaptiveRuleEngine(deduped)


def _emit_telemetry(*, mode: str, workers: int, n_files: int, elapsed: float) -> None:
    """Write a one-line performance summary to stderr.

    Only called when ``verbose=True`` is passed to :func:`scan_docs_references`.
    Writes to stderr so it never contaminates stdout-captured output.

    The speedup estimate for parallel mode assumes a linear model relative to
    the sequential baseline: ``speedup ≈ workers × 0.7`` (accounting for
    overhead and I/O serialisation).  This is a rough heuristic for display
    purposes only.

    Args:
        mode:     ``"Sequential"`` or ``"Parallel"``.
        workers:  Effective worker count used.
        n_files:  Number of ``.md`` files scanned.
        elapsed:  Wall-clock seconds from scan start to completion.
    """
    import sys

    engine_label = (
        f"Adaptive (Parallel, {workers} worker{'s' if workers != 1 else ''})"
        if mode == "Parallel"
        else "Adaptive (Sequential)"
    )
    time_str = f"{elapsed:.2f}s"
    speedup_str = ""
    if mode == "Parallel" and workers > 1:
        estimated = round(min(workers * 0.7, workers - 0.1), 1)
        speedup_str = f"  Estimated speedup: {estimated}x"

    print(
        f"[zenzic] Engine: {engine_label}  "
        f"Files: {n_files}  "
        f"Execution time: {time_str}"
        f"{speedup_str}",
        file=sys.stderr,
    )


def scan_docs_references(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    repo_root: Path | None = None,
    config: ZenzicConfig | None = None,
    validate_links: bool = False,
    workers: int | None = 1,
    verbose: bool = False,
    locale_roots: list[tuple[Path, str]] | None = None,
    content_roots: list[Path] | None = None,
    show_progress: bool = False,
) -> tuple[list[IntegrityReport], list[str]]:
    """Run the Three-Phase Pipeline over every .md file in docs/.

    This is the single unified entry point for all scan modes.  The engine
    selects sequential or parallel execution automatically based on the number
    of files found (**Hybrid Adaptive Mode**):

    * **Sequential** — used when ``workers=1`` (the default) or when the repo
      has fewer than :data:`ADAPTIVE_PARALLEL_THRESHOLD` files.  Zero
      process-spawn overhead; supports external URL validation.
    * **Parallel** — activated when ``workers != 1`` *and* the file count
      meets or exceeds :data:`ADAPTIVE_PARALLEL_THRESHOLD`.  Distributes each
      file to an independent worker process via ``ProcessPoolExecutor``.
      External URL validation is performed in the main process after all
      workers complete.

    The threshold default (50 files) is a conservative heuristic: below it,
    ``ProcessPoolExecutor`` spawn overhead (~200–400 ms on a cold interpreter)
    exceeds the parallelism benefit.  Override with ``workers=N`` to select a
    specific pool size when parallel mode is active.

    **Determinism guarantee:** results are always sorted by ``file_path``
    regardless of execution mode.

    **Credential scanner behaviour:** enforced per-worker in parallel mode; per-file in
    sequential mode.  Files with security findings are excluded from link
    validation in both modes.

    **Read behaviour:** total I/O remains :math:`O(N)` in the number of files,
    but individual files may be read multiple times.  In sequential mode the
    scanner typically performs separate credential and content passes, and some
    rules may trigger an additional ``read_text()`` call.  In parallel mode the
    same per-worker behaviour applies; when ``validate_links=True`` an extra
    lightweight sequential pass in the main process registers external URLs
    after workers complete (workers discard scanners).

    Args:
        docs_root:      Documentation root to scan.
        config:         Optional Zenzic configuration.
        validate_links: When ``True``, perform async HTTP validation of all
                        external reference URLs found across the docs tree.
                        Disabled by default.
        workers:        Number of worker processes for parallel mode.
                        ``1`` (default) always uses sequential execution.
                        ``None`` lets ``ProcessPoolExecutor`` pick based on
                        ``os.cpu_count()``.  Values must be ``None`` or
                        greater than or equal to ``1``.
        verbose:        When ``True``, print a single telemetry line to stderr
                        after the scan completes.  Shows the engine mode, worker
                        count, elapsed time, and estimated speedup (parallel
                        mode only).  Defaults to ``False``.
        locale_roots:   Optional locale trees injected by caller.
        content_roots:  Optional extra markdown roots injected by caller.
        show_progress:  When ``True``, display a rich progress bar on stderr.

    Returns:
        A ``(reports, link_errors)`` tuple where:

        - ``reports`` is the sorted list of :class:`IntegrityReport` objects,
          one per ``.md`` file.
        - ``link_errors`` is a sorted list of human-readable HTTP error strings
          (empty when ``validate_links=False`` or all URLs pass).
    """
    import time

    if workers is not None and workers < 1:
        raise ValueError("workers must be None or an integer >= 1")

    if not docs_root.exists() or not docs_root.is_dir():
        return [], []

    if config is None:
        config, _ = ZenzicConfig.load(docs_root)

    rule_engine = _build_rule_engine(config)
    md_files = list(iter_markdown_sources(docs_root, config, exclusion_manager))

    static_assets: set[Path] = set()
    if docs_root.is_dir():
        for fpath in walk_files(docs_root, set(config.excluded_dirs), exclusion_manager, config):
            if fpath.suffix.lower() not in DOC_SUFFIXES and not fpath.is_symlink():
                if not exclusion_manager.should_exclude_file(fpath, docs_root):
                    static_assets.add(fpath)

    # Build locale path remap: actual_abs_path → virtual_path_under_docs_root.
    # virtual_path = docs_root / locale_name / rel_within_locale
    # This maps locale files to logical paths so the reporter displays
    # "it/architecture.mdx" rather than the full i18n/ absolute path.
    _locale_path_remap: dict[Path, Path] = {}
    if locale_roots:
        for locale_root, locale_name in locale_roots:
            for abs_path, logical_rel in iter_locale_markdown_sources(
                locale_root, locale_name, config, exclusion_manager
            ):
                _locale_path_remap[abs_path] = docs_root / logical_rel
                md_files.append(abs_path)

    if content_roots:
        for content_root, url_prefix in build_content_mounts(content_roots):
            for abs_path, logical_rel in iter_extra_content_markdown_sources(
                content_root, url_prefix, config, exclusion_manager
            ):
                _locale_path_remap[abs_path] = docs_root / logical_rel
                md_files.append(abs_path)

    if not md_files:
        return [], []

    use_parallel = workers != 1 and len(md_files) >= ADAPTIVE_PARALLEL_THRESHOLD

    # Initialise Visual Progress Bar context if requested.
    progress = None
    task_id = None
    task_validate_id = None
    if show_progress:
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        )
        progress.start()
        _mode_label = "parallel" if use_parallel else "sequential"
        task_id = progress.add_task(
            f"[cyan]Parsing[/cyan] [dim]{len(md_files)} files ({_mode_label})...[/dim]",
            total=len(md_files),
        )
        if validate_links:
            task_validate_id = progress.add_task(
                "[blue]Validating links...[/blue]",
                total=None,  # indeterminate until parsing completes
                start=False,
            )

    _t0 = time.monotonic()

    try:
        if use_parallel:
            import concurrent.futures
            import os

            actual_workers = workers if workers is not None else os.cpu_count() or 1
            work_items = [(f, config, rule_engine) for f in md_files]
            # GA-1 fix: use actual_workers for the executor (not the raw `workers`
            # marker) so max_workers always matches what telemetry reports.
            with concurrent.futures.ProcessPoolExecutor(max_workers=actual_workers) as executor:
                # CEO-298 fail-fast + ZRT-002: use wait(FIRST_COMPLETED) to process
                # results in completion order and cancel queued tasks immediately on
                # the first security breach (Z201–Z203).
                # ZRT-002 preserved: if no future completes within _WORKER_TIMEOUT_S,
                # all remaining workers are emitted as Z902 (deadlock guard).
                futures_map = {executor.submit(_worker, item): item[0] for item in work_items}
                raw: list[IntegrityReport] = []
                _abort = False
                _pending: set[concurrent.futures.Future[IntegrityReport]] = set(futures_map)
                while _pending:
                    done, _pending = concurrent.futures.wait(
                        _pending,
                        timeout=_WORKER_TIMEOUT_S,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    if not done:
                        # ZRT-002 deadlock guard: no worker completed within the
                        # timeout window — treat all stalled workers as Z902.
                        for fut in _pending:
                            raw.append(_make_timeout_report(futures_map[fut]))
                            fut.cancel()
                            if progress and task_id is not None:
                                progress.advance(task_id)
                        break
                    for fut in done:
                        md_file = futures_map[fut]
                        if _abort:
                            if progress and task_id is not None:
                                progress.advance(task_id)
                            continue  # discard results after a security breach
                        try:
                            report = fut.result()
                            raw.append(report)
                            if report.security_findings:
                                # CEO-298: cancel all still-queued (PENDING) tasks.
                                # RUNNING workers cannot be interrupted — they
                                # complete and their results are discarded above.
                                _abort = True
                                for pending_fut in _pending:
                                    pending_fut.cancel()
                                    if progress and task_id is not None:
                                        progress.advance(task_id)
                        except concurrent.futures.CancelledError:
                            pass  # intentional abort — no report emitted
                        except Exception as exc:  # noqa: BLE001
                            raw.append(_make_error_report(md_file, exc))

                        if progress and task_id is not None:
                            progress.advance(task_id)

            reports: list[IntegrityReport] = sorted(raw, key=lambda r: r.file_path)

            _run_vsm_and_urp_pass(
                reports,
                md_files,
                docs_root,
                config,
                rule_engine,
                repo_root=repo_root,
                locale_roots=locale_roots,
                content_roots=content_roots,
                static_assets=static_assets,
            )

            # Remap locale file paths to their logical display paths.
            if _locale_path_remap:
                for _r in reports:
                    if _r.file_path in _locale_path_remap:
                        _r.file_path = _locale_path_remap[_r.file_path]
                    for _sf in _r.security_findings:
                        if _sf.file_path in _locale_path_remap:
                            _sf.file_path = _locale_path_remap[_sf.file_path]

            elapsed = time.monotonic() - _t0
            if verbose:
                _emit_telemetry(
                    mode="Parallel",
                    workers=actual_workers,
                    n_files=len(md_files),
                    elapsed=elapsed,
                )

            if not validate_links:
                return reports, []

            # Phase B in main process: lightweight sequential pass for URL
            # registration.  Workers discard scanners; we re-collect ref_maps here
            # for deduplication.  This is an additional O(N) read but preserves the
            # credential-scanner-as-firewall guarantee (no URLs from compromised files).
            secure_scanners_b: list[ReferenceScanner] = []
            for md_file in md_files:
                _report_b, secure_scanner_b = _scan_single_file(md_file, config, None)
                if secure_scanner_b is not None:
                    secure_scanners_b.append(secure_scanner_b)
            _resolved_repo_root = find_repo_root(fallback_to_cwd=True, search_from=docs_root)
            validator_b = LinkValidator(config, _resolved_repo_root)
            for scanner in secure_scanners_b:
                validator_b.register_from_map(scanner.ref_map, scanner.file_path)
            for r in reports:
                if not r.security_findings and r.file_path.is_file():
                    try:
                        text = r.file_path.read_text(encoding="utf-8")
                        for link in PolyglotExtractor().extract_all_links(text):
                            if not link.suppressed:
                                parsed = urlsplit(link.url)
                                if parsed.scheme in ("http", "https"):
                                    validator_b.register(link.url, r.file_path, link.line_no)
                    except OSError:
                        pass

            return reports, validator_b.validate()

        # Sequential path — zero overhead, full O(N) link-validation support.
        reports_seq: list[IntegrityReport] = []
        secure_scanners_seq: list[ReferenceScanner] = []

        for md_file in md_files:
            report, secure_scanner = _scan_single_file(md_file, config, rule_engine)
            reports_seq.append(report)
            if validate_links and secure_scanner is not None:
                secure_scanners_seq.append(secure_scanner)
            if progress and task_id is not None:
                progress.advance(task_id)

        _run_vsm_and_urp_pass(
            reports_seq,
            md_files,
            docs_root,
            config,
            rule_engine,
            repo_root=repo_root,
            locale_roots=locale_roots,
            content_roots=content_roots,
            static_assets=static_assets,
        )

        elapsed_seq = time.monotonic() - _t0

        if verbose:
            _emit_telemetry(
                mode="Sequential",
                workers=1,
                n_files=len(md_files),
                elapsed=elapsed_seq,
            )

        if not validate_links:
            # Remap locale file paths to their logical display paths.
            if _locale_path_remap:
                for _r in reports_seq:
                    if _r.file_path in _locale_path_remap:
                        _r.file_path = _locale_path_remap[_r.file_path]
                    for _sf in _r.security_findings:
                        if _sf.file_path in _locale_path_remap:
                            _sf.file_path = _locale_path_remap[_sf.file_path]
            return reports_seq, []

        # Phase B — global URL deduplication and async HTTP validation.
        # Uses the already-populated ref_maps from Phase A — no second file read.
        _resolved_repo_root = find_repo_root(fallback_to_cwd=True, search_from=docs_root)
        validator_seq = LinkValidator(config, _resolved_repo_root)
        for scanner in secure_scanners_seq:
            validator_seq.register_from_map(scanner.ref_map, scanner.file_path)
        for r in reports_seq:
            if not r.security_findings and r.file_path.is_file():
                try:
                    text = r.file_path.read_text(encoding="utf-8")
                    for link in PolyglotExtractor().extract_all_links(text):
                        if not link.suppressed:
                            parsed = urlsplit(link.url)
                            if parsed.scheme in ("http", "https"):
                                validator_seq.register(link.url, r.file_path, link.line_no)
                except OSError:
                    pass

        # Remap locale file paths to their logical display paths.
        if _locale_path_remap:
            for _r in reports_seq:
                if _r.file_path in _locale_path_remap:
                    _r.file_path = _locale_path_remap[_r.file_path]
                for _sf in _r.security_findings:
                    if _sf.file_path in _locale_path_remap:
                        _sf.file_path = _locale_path_remap[_sf.file_path]
        if progress and task_validate_id is not None:
            n_external = sum(
                1
                for s in secure_scanners_seq
                for url, _ in s.ref_map.definitions.values()
                if url.startswith("http")
            )
            progress.update(
                task_validate_id,
                description=f"[blue]Validating links[/blue] [dim]({n_external} external URLs)...[/dim]",
                total=1,
            )
            progress.start_task(task_validate_id)
        link_errors = validator_seq.validate()
        if progress and task_validate_id is not None:
            progress.advance(task_validate_id)
        return reports_seq, link_errors
    finally:
        if progress:
            progress.stop()


# ─── Adaptive parallel worker ─────────────────────────────────────────────────

#: Files below this threshold are scanned sequentially (zero process-spawn
#: overhead).  Above it, scan_docs_references() switches to a
#: ProcessPoolExecutor automatically.  Exposed as a module constant so tests
#: can override it without patching private internals.
ADAPTIVE_PARALLEL_THRESHOLD: int = 50

#: Maximum wall-clock seconds a single worker may spend analysing one file.
#: If a worker exceeds this limit it is abandoned and a Z902 timeout finding
#: is emitted for the file instead of a normal IntegrityReport.  The purpose
#: is to guard against I/O hangs, network stalls, and worker process crashes
#: that would otherwise deadlock the entire parallel pipeline.  (ZRT-002 fix)
_WORKER_TIMEOUT_S: int = 30


def _make_timeout_report(md_file: Path) -> IntegrityReport:
    """Produce a minimal :class:`IntegrityReport` for a worker that timed out.

    Called by the parallel coordinator when ``future.result(timeout=...)``
    raises :class:`concurrent.futures.TimeoutError`.  The returned report
    carries a single ``Z902`` rule finding so the CLI can surface the
    timeout in the standard findings UI without crashing the scan.

    A Z902 finding indicates a systemic stall (I/O hang, network timeout,
    worker process crash) rather than a regex issue — all CustomRule patterns
    are DFA-safe since ZRT-007 replaced the NFA engine with Google RE2.

    Args:
        md_file: Absolute path of the file whose worker timed out.

    Returns:
        A :class:`IntegrityReport` with ``score=0`` and one ``Z902`` finding.
    """
    from zenzic.core.rules import RuleFinding  # deferred: avoid circular at module level
    from zenzic.models.references import IntegrityReport

    timeout_finding = RuleFinding(
        file_path=md_file,
        line_no=0,
        rule_id="Z902",
        message=(
            f"Analysis of '{md_file.name}' timed out after {_WORKER_TIMEOUT_S}s. "
            "Worker stalled — possible I/O hang, network timeout, or process crash. "
            "Custom rule patterns are DFA-safe (ZRT-007); this is a systemic stall."
        ),
        severity="error",
    )
    return IntegrityReport(
        file_path=md_file,
        score=0,
        findings=[],
        security_findings=[],
        rule_findings=[timeout_finding],
    )


def _make_error_report(md_file: Path, exc: BaseException) -> IntegrityReport:
    """Produce a minimal :class:`IntegrityReport` for a worker that raised.

    Args:
        md_file: Absolute path of the file whose worker raised an exception.
        exc: The exception caught from ``future.result()``.

    Returns:
        A :class:`IntegrityReport` with ``score=0`` and one ``RULE-ENGINE-ERROR`` finding.
    """
    from zenzic.core.rules import RuleFinding
    from zenzic.models.references import IntegrityReport

    error_finding = RuleFinding(
        file_path=md_file,
        line_no=0,
        rule_id="Z901",
        message=(
            f"Worker for '{md_file.name}' raised an unexpected exception: "
            f"{type(exc).__name__}: {exc}"
        ),
        severity="error",
    )
    return IntegrityReport(
        file_path=md_file,
        score=0,
        findings=[],
        security_findings=[],
        rule_findings=[error_finding],
    )


def _worker(args: tuple[Path, ZenzicConfig, AdaptiveRuleEngine | None]) -> IntegrityReport:
    """Top-level worker function for ``ProcessPoolExecutor``.

    Must be a module-level function (not a lambda or nested function) so that
    ``pickle`` can serialise it for inter-process transport.

    **Immutability contract:** ``config`` and ``rule_engine`` are serialised by
    ``pickle`` when dispatched to a worker process.  Each worker receives an
    independent copy — there is no shared state between processes.  Workers
    must never mutate ``config``; :func:`_scan_single_file` and all functions
    it calls are pure and honour this contract.

    Args:
        args: ``(md_file, config, rule_engine)`` tuple.

    Returns:
        The :class:`IntegrityReport` for *md_file*.  The ``ReferenceScanner``
        is discarded — workers do not participate in Phase B URL registration.
    """
    md_file, config, rule_engine = args
    report, _scanner = _scan_single_file(md_file, config, rule_engine)
    return report
