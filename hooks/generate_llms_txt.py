# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""MkDocs build hook: emit `/llms.txt` and `/llms-ctx-full.txt` from the built nav.

`llms.txt` is a 2024 proposal by Jeremy Howard (Answer.AI) for a Markdown file at
a site's root that lists its documentation as links, so a tool assembling context
does not have to scrape rendered HTML. It is a proposal, not a ratified standard,
and it prescribes no processing behaviour.

Both files are **generated at build time and never committed**. That is the whole
design: an artifact derived from the nav on every build cannot fall out of step
with the nav, so there is nothing to keep in sync and no staleness to police.

Naming follows the original proposal: the full-content variant is
``llms-ctx-full.txt``. The widely circulated ``llms-full.txt`` appears nowhere in
the spec, which defines ``llms-ctx.txt`` / ``llms-ctx-full.txt`` as the outputs a
processing tool produces from ``llms.txt``.

The nav comes from MkDocs' own ``Navigation`` object rather than
``BaseAdapter.get_nav_paths()``. The adapter method returns ``frozenset[str]`` —
unordered and title-less — while this format needs both order and section titles,
and MkDocs' object is also the ground truth for what the build actually produced
rather than a second reading of the same config file.

Content is restricted to structural facts: the site name, the packaging
description, and the real titles and URLs of pages that are in the nav. It makes
no claim about how any consumer will treat the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.nav import Navigation

#: Captured in ``on_nav`` because ``on_post_build`` receives only the config.
_nav: Navigation | None = None

#: Factual one-line description, taken from the package metadata rather than
#: written here, so this file cannot become a second place marketing copy lives.
_DESCRIPTION = "Deterministic Document Integrity Engine for Markdown/MDX graphs."

_INDEX_NAME = "llms.txt"
_FULL_NAME = "llms-ctx-full.txt"


def on_nav(nav: Navigation, /, *_args: Any, **_kwargs: Any) -> Navigation:
    """Capture the built navigation; MkDocs calls this before ``on_post_build``."""
    global _nav
    _nav = nav
    return nav


def _walk(items: Any, trail: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str, Any]]:
    """Flatten the nav into ``(section_trail, page_title, page)`` in document order.

    Carrying the full trail rather than a depth lets each group be titled by the
    path that reaches it. That matters here: this nav has a *Reference* and a
    *How-to* section under both User and Developer Documentation, so a title
    taken from the nearest section alone would produce two indistinguishable
    ``## Reference`` headings.
    """
    out: list[tuple[tuple[str, ...], str, Any]] = []
    for item in items:
        if getattr(item, "is_section", False):
            out.extend(_walk(item.children, (*trail, item.title or "")))
        elif getattr(item, "is_page", False):
            out.append((trail, item.title or item.file.src_uri, item))
    return out


def _abs_url(config: MkDocsConfig, page: Any) -> str:
    """Canonical absolute URL for *page*, falling back to a site-root path."""
    canonical = getattr(page, "canonical_url", None)
    if canonical:
        return str(canonical)
    site_url = (config.get("site_url") or "").rstrip("/")
    return f"{site_url}/{page.url}" if site_url else f"/{page.url}"


def _render_index(config: MkDocsConfig, entries: list[tuple[tuple[str, ...], str, Any]]) -> str:
    """The `llms.txt` link index: H1, blockquote summary, H2 sections of links.

    Pages are grouped by section trail before rendering, not as they stream past.
    A nav that returns to a parent section after a nested one — this one does,
    under *Developer Documentation — How-to* — would otherwise emit that heading
    twice and split its pages across two identical H2s.

    Every link sits under an H2, including pages the nav lists before any section
    (the homepage), which would otherwise dangle above the first heading and
    break the format's one structural rule.
    """
    site_name = config.get("site_name") or "Documentation"

    groups: dict[str, list[str]] = {}
    for trail, title, page in entries:
        heading = " — ".join(part for part in trail if part) or site_name
        groups.setdefault(heading, []).append(f"- [{title}]({_abs_url(config, page)})")

    lines: list[str] = [f"# {site_name}", "", f"> {_DESCRIPTION}", ""]
    for heading, links in groups.items():
        lines.extend([f"## {heading}", "", *links, ""])
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_full(config: MkDocsConfig, entries: list[tuple[tuple[str, ...], str, Any]]) -> str:
    """The full-context variant: every nav page's Markdown source, in nav order."""
    site_name = config.get("site_name") or "Documentation"
    parts: list[str] = [f"# {site_name}", "", f"> {_DESCRIPTION}", ""]
    for _trail, title, page in entries:
        source = getattr(page.file, "abs_src_path", None)
        if not source or not Path(source).is_file():
            continue
        body = Path(source).read_text(encoding="utf-8")
        parts.extend(["---", "", f"# {title}", "", f"<{_abs_url(config, page)}>", "", body, ""])
    return "\n".join(parts).rstrip("\n") + "\n"


def on_post_build(*, config: MkDocsConfig) -> None:
    if _nav is None:  # pragma: no cover - MkDocs always calls on_nav first
        return
    entries = _walk(_nav.items)
    site_dir = Path(config["site_dir"])
    (site_dir / _INDEX_NAME).write_text(_render_index(config, entries), encoding="utf-8")
    (site_dir / _FULL_NAME).write_text(_render_full(config, entries), encoding="utf-8")
