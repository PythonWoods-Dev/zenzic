# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Shared utilities for Zenzic adapters.

- **i18n path remapping** — locale prefix stripping for ``fallback_to_default``.
- **Frontmatter extraction** — engine-agnostic YAML frontmatter parser.
- **Eager Metadata Cache** — single-pass extraction of slug, draft/unlisted
  flags, and tags from all loaded files.

All functions are **pure** — no I/O, no disk access.  Third-party adapters
may use or ignore them as needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from zenzic.core import regex as re


def _iter_plugins(doc_config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return normalized plugin declarations from list or mapping syntax.

    MkDocs / compat config supports both:
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


def _extract_blog_dir(doc_config: dict[str, Any]) -> str | None:
    """Extract relative blog posts prefix from MkDocs / compat blog plugin config.

    Returns:
        The relative ``<blog_dir>/posts/`` prefix (e.g. ``"blog/posts"``) when
        the blog plugin is active; ``None`` when the plugin is absent.
    """
    for name, blog_cfg in _iter_plugins(doc_config):
        # Accept both short form ``blog`` and fully-qualified ``material/blog``.
        if name not in ("blog", "material/blog"):
            continue
        blog_dir = blog_cfg.get("blog_dir", "blog") if isinstance(blog_cfg, dict) else "blog"
        blog_dir = blog_dir.strip("/")
        return f"{blog_dir}/posts"
    return None


def dedupe_roots(roots: list[Path]) -> list[Path]:

    """Return roots de-duplicated by resolved absolute path, preserving order."""
    seen: set[str] = set()
    out: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        key = resolved.as_posix()
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def case_sensitive_exists(path: Path) -> bool:
    """Return ``True`` only when *path* exists with an exact case-sensitive match.

    On case-insensitive filesystems (Windows NTFS, macOS HFS+), ``Path.exists()``
    returns ``True`` even when the on-disk filename differs only in case from the
    requested name.  Web servers and browsers are case-sensitive, so
    ``Logo.png`` and ``logo.png`` are different resources; static analysis must
    reflect that.

    This function uses ``os.listdir(path.parent)`` — which always returns the
    actual stored filenames — to enforce case-sensitive semantics on every
    platform without any per-platform branching.

    Args:
        path: Absolute or relative path to check.

    Returns:
        ``True`` when a directory entry with *exactly* this name exists.
        ``False`` when the parent directory does not exist or an OS error occurs.
    """
    if not path.parent.is_dir():
        return False
    try:
        return path.name in os.listdir(path.parent)
    except OSError:
        return False


def remap_to_default_locale(
    abs_path: Path,
    docs_root: Path,
    locale_dirs: frozenset[str],
) -> Path | None:
    """Return the default-locale equivalent of a path inside a locale sub-tree.

    Strips the first path component when it is a known locale directory name,
    producing the canonical default-locale path.  Returns ``None`` when the
    path is not inside any known locale directory — the caller should not apply
    fallback logic in that case.

    This function is **pure** — no I/O, no disk access.  The caller decides
    what to do with the returned path (existence check, anchor lookup, etc.).

    Examples::

        remap_to_default_locale(
            Path("/docs/it/architecture.md"),
            Path("/docs"),
            frozenset({"it", "fr"}),
        )
        # → Path("/docs/architecture.md")

        remap_to_default_locale(
            Path("/docs/architecture.md"),
            Path("/docs"),
            frozenset({"it", "fr"}),
        )
        # → None  (not inside a locale directory)

    Args:
        abs_path: Absolute path to remap.  May be a ``.md`` file, an asset,
            or any path inside ``docs_root``.
        docs_root: Resolved absolute ``docs/`` root.
        locale_dirs: Frozenset of non-default locale directory names
            (e.g. ``frozenset({"it", "fr"})``).

    Returns:
        Absolute :class:`~pathlib.Path` of the default-locale equivalent, or
        ``None`` when *abs_path* is not inside a recognised locale directory.
    """
    try:
        rel = abs_path.relative_to(docs_root)
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] not in locale_dirs:
        return None
    return docs_root.joinpath(*rel.parts[1:])


# ── Frontmatter extraction (engine-agnostic) ────────────────────────────────

# Matches leading YAML frontmatter block: --- ... ---
_FRONTMATTER_RE = re.compile(r"\A\s*---\s*\n(.*?)\n---", re.DOTALL)

# Individual field patterns inside frontmatter.
_SLUG_RE = re.compile(r"^slug\s*:\s*['\"]?([^'\"#\n]+?)['\"]?\s*$", re.MULTILINE)
_DRAFT_RE = re.compile(r"^draft\s*:\s*(true|false)\s*$", re.MULTILINE | re.IGNORECASE)
_UNLISTED_RE = re.compile(r"^unlisted\s*:\s*(true|false)\s*$", re.MULTILINE | re.IGNORECASE)
_TAGS_RE = re.compile(r"^tags\s*:\s*\[([^\]]*)\]\s*$", re.MULTILINE)
_TAGS_FLOW_RE = re.compile(r"^-\s+(.+)$", re.MULTILINE)
# Block-style tags key: "tags:\n  - item" (used in extract_frontmatter_tags).
_TAGS_BLOCK_RE = re.compile(r"^tags\s*:\s*$", re.MULTILINE)


def extract_frontmatter_slug(content: str) -> str | None:
    """Extract ``slug`` from YAML frontmatter, or ``None`` if absent.

    Only looks in the leading ``---`` fenced block.  The slug value is
    returned as-is (may be absolute ``/custom`` or relative ``custom``).

    This function is **engine-agnostic** — it works identically for
    MkDocs, Docusaurus, Zensical, and Standalone.

    Args:
        content: Raw Markdown/MDX source text.

    Returns:
        The slug string, or ``None`` when no frontmatter slug is declared.
    """
    fm = _FRONTMATTER_RE.match(content)
    if fm is None:
        return None
    slug_match = _SLUG_RE.search(fm.group(1))
    if slug_match is None:
        return None
    return slug_match.group(1).strip()


def extract_frontmatter_draft(content: str) -> bool:
    """Return ``True`` when frontmatter declares ``draft: true``.

    Returns ``False`` when no frontmatter exists, when ``draft`` is absent,
    or when ``draft: false`` is declared.
    """
    fm = _FRONTMATTER_RE.match(content)
    if fm is None:
        return False
    m = _DRAFT_RE.search(fm.group(1))
    return m is not None and m.group(1).lower() == "true"


def extract_frontmatter_unlisted(content: str) -> bool:
    """Return ``True`` when frontmatter declares ``unlisted: true``.

    Returns ``False`` when no frontmatter exists, when ``unlisted`` is absent,
    or when ``unlisted: false`` is declared.
    """
    fm = _FRONTMATTER_RE.match(content)
    if fm is None:
        return False
    m = _UNLISTED_RE.search(fm.group(1))
    return m is not None and m.group(1).lower() == "true"


def extract_frontmatter_tags(content: str) -> list[str]:
    """Extract ``tags`` from YAML frontmatter as a list of strings.

    Supports both inline (``tags: [a, b]``) and flow (``tags:\\n- a\\n- b``)
    YAML syntax.  Returns an empty list when no tags are declared.
    """
    fm = _FRONTMATTER_RE.match(content)
    if fm is None:
        return []
    fm_text = fm.group(1)

    # Inline syntax: tags: [a, b, c]
    inline = _TAGS_RE.search(fm_text)
    if inline:
        raw = inline.group(1)
        return [t.strip().strip("'\"") for t in raw.split(",") if t.strip()]

    # Flow syntax: tags:\n- a\n- b
    tags_start = _TAGS_BLOCK_RE.search(fm_text)
    if tags_start:
        rest = fm_text[tags_start.end() :]
        return [m.group(1).strip() for m in _TAGS_FLOW_RE.finditer(rest)]

    return []


# ── Eager Metadata Cache ─────────────────────────────────────────────────────

from dataclasses import dataclass, field  # noqa: E402


@dataclass(slots=True)
class FileMetadata:
    """Metadata harvested from a single Markdown file's frontmatter.

    Populated in a single pass during Phase 1 (VSM construction).
    All fields default to safe no-op values.
    """

    slug: str | None = None
    draft: bool = False
    unlisted: bool = False
    tags: list[str] = field(default_factory=list)


def build_metadata_cache(
    md_contents: dict[Path, str],
    docs_root: Path,
    *,
    scan_credentials: bool = True,
) -> dict[str, FileMetadata]:
    """Build a metadata cache from all loaded Markdown files in one pass.

    Extracts ``slug``, ``draft``, ``unlisted``, and ``tags`` from each file's
    YAML frontmatter.  The returned dict is keyed by the POSIX relative path
    (e.g. ``"guide/install.mdx"``).

    This is the **Eager Metadata Harvesting** function: call it once during
    VSM construction to pre-compute all frontmatter metadata, then pass the
    result to adapter constructors or ``get_route_info()`` implementations.

    When ``scan_credentials`` is ``True`` (default), every frontmatter line is
    passed through :func:`~zenzic.core.credentials.safe_read_line` before parsing.
    If a secret is detected, :class:`~zenzic.core.credentials.CredentialViolation` is
    raised immediately — the VSM is never constructed.

    Args:
        md_contents: Pre-loaded mapping of absolute ``Path`` → raw content.
        docs_root: Resolved absolute ``docs/`` directory root.
        scan_credentials: When ``True``, run credential scan on frontmatter lines.

    Returns:
        Dict mapping POSIX relative path → :class:`FileMetadata`.

    Raises:
        :class:`~zenzic.core.credentials.CredentialViolation`: When a secret is found
            in frontmatter content (only when ``scan_credentials=True``).
    """
    cache: dict[str, FileMetadata] = {}
    for abs_path, content in md_contents.items():
        try:
            rel = abs_path.relative_to(docs_root)
        except ValueError:
            continue

        # Credential scanner check on frontmatter lines if enabled.
        if scan_credentials:
            fm_match = _FRONTMATTER_RE.match(content)
            if fm_match:
                from zenzic.core.credentials import safe_read_line

                fm_text = fm_match.group(1)
                # Find the line offset of frontmatter start.
                prefix = content[: fm_match.start()]
                start_line = prefix.count("\n") + 2  # +1 for 1-based, +1 for --- line
                for i, line in enumerate(fm_text.split("\n")):
                    safe_read_line(line, abs_path, start_line + i)

        cache[rel.as_posix()] = FileMetadata(
            slug=extract_frontmatter_slug(content),
            draft=extract_frontmatter_draft(content),
            unlisted=extract_frontmatter_unlisted(content),
            tags=extract_frontmatter_tags(content),
        )
    return cache
