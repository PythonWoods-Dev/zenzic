# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""MkDocs build hook: correct mkdocs-rss-plugin's hardcoded feed-discovery links.

mkdocs-rss-plugin's `feeds_filenames` config option renames the actual output
feed files, but the plugin unconditionally injects
`<link rel="alternate" type="application/rss+xml">` discovery tags into every
page's `<head>` using its own hardcoded default filenames
(`feed_rss_created.xml`, `feed_rss_updated.xml`), regardless of that config —
a known upstream limitation (confirmed against the plugin's real behavior,
not assumed). Left unpatched, every page ships a broken feed-discovery link
pointing at a file that was never written to the built site, silently
breaking any browser extension or feed reader that follows standard
`<link rel="alternate">` auto-discovery instead of a hand-typed URL.

Runs as `on_post_build` — a single sweep over every file already written to
`site_dir` — rather than `on_post_page`, since Material's 404 page (and
other non-page artifacts such as the search index) is generated outside the
normal per-page render pipeline and would otherwise be missed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

_REPLACEMENTS = {
    "feed_rss_created.xml": "rss.xml",
    "feed_rss_updated.xml": "rss-updated.xml",
}
_TEXT_SUFFIXES = frozenset({".html", ".json", ".xml"})


def on_post_build(*, config: MkDocsConfig) -> None:
    site_dir = Path(config["site_dir"])
    for path in site_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        patched = text
        for stale_name, real_name in _REPLACEMENTS.items():
            patched = patched.replace(stale_name, real_name)
        if patched != text:
            path.write_text(patched, encoding="utf-8")
