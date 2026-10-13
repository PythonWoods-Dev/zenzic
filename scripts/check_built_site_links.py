#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Resolve every internal link in the BUILT site the way a browser does.

The engine resolves links against the source tree. A browser resolves them
against the served URL, and with ``use_directory_urls`` those differ by one
segment for every non-index page -- which is how 161 broken links across 66
pages passed ``zenzic check links`` for months. The engine defect is fixed, but
the two are still different questions, and only this one asks the reader's.

**Parse, do not pattern-match.** ``minify_html`` strips attribute quotes, so the
rendered anchor is ``<a href=../../../reference/checks>``. A regex requiring
quotes finds nothing and reports a clean sweep; that quirk has cost two sweeps
in this repository, this one and a dead-CSS pass.

**What it cannot reach**: MkDocs does not render ``.mdx`` -- it copies the file
into the site verbatim, so there is no HTML page to parse and no built-site
checker can cover those links even in principle. The engine is the only
instrument there, which is why its ``.mdx`` behaviour is tested directly
(``tests/test_directory_url_link_depth.py``). It also cannot judge external
URLs, anchors within a page, or anything a client resolves at runtime.
"""

from __future__ import annotations

import pathlib
import posixpath
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit


SITE = pathlib.Path(sys.argv[1])


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[tuple[str, str]] = []
        self._cur: str | None = None
        self._txt: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href") is not None:
            self._cur = d["href"]
            self._txt = []
        elif tag == "img" and d.get("src"):
            self.out.append((d["src"], "<img>"))

    def handle_data(self, data):
        if self._cur is not None:
            self._txt.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._cur is not None:
            self.out.append((self._cur, "".join(self._txt).strip()))
            self._cur = None


def url_of(page: pathlib.Path) -> str:
    rel = page.relative_to(SITE).as_posix()
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    if rel == "index.html":
        return "/"
    return "/" + rel


def exists(target: str) -> bool:
    t = unquote(target).lstrip("/")
    if t == "":
        return (SITE / "index.html").exists()
    p = SITE / t
    if p.is_file():
        return True
    if p.is_dir() and (p / "index.html").is_file():
        return True
    # a directory-style URL without the trailing slash
    if (SITE / (t + "/index.html")).is_file():
        return True
    if (SITE / (t + ".html")).is_file():
        return True
    return False


broken = []
total = 0
pages = 0
for page in sorted(SITE.rglob("*.html")):
    pages += 1
    parser = Links()
    try:
        parser.feed(page.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print(f"  parse error {page}: {e}", file=sys.stderr)
        continue
    base = url_of(page)
    for href, text in parser.out:
        sp = urlsplit(href)
        if sp.scheme or sp.netloc:
            continue  # external
        if not sp.path:
            continue  # pure #anchor
        total += 1
        resolved = posixpath.normpath(posixpath.join(base, sp.path))
        if sp.path.endswith("/") and not resolved.endswith("/"):
            resolved += "/"
        if not exists(resolved):
            broken.append((url_of(page), href, text, resolved))

print(f"built-site link gate: {pages} page(s), {total} internal link(s), {len(broken)} broken")
for src, href, text, res in broken:
    print(f"  {src}\n      href={href!r}  text={text!r}\n      -> {res}  (404)")
raise SystemExit(1 if broken else 0)
