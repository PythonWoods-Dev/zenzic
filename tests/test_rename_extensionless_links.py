# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Renaming a file must also update the extensionless links that point at it.

``RenameLinkMutation`` resolved each href and compared it against ``old_abs``,
which is a real file path and therefore carries a suffix.  An extensionless
href resolves to a suffix-less string, so the comparison could never match:
moving a page left every ``[text](../../target/page)`` link in the corpus
pointing at the old address, silently and with no finding -- and this project's
own documentation is written almost entirely in that spelling.

The replacement must also preserve the author's spelling.  Writing a suffixed,
tree-relative path in place of an extensionless one would be correct as a path
and wrong as a link: the generator rewrites suffixed links and emits
extensionless ones verbatim, so the two are resolved against different bases.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.ast import LinkNode
from zenzic.core.mutator import RenameLinkMutation


DOCS = Path("/docs")
SOURCE = DOCS / "a" / "b" / "leaf.md"  # served at /a/b/leaf/
OLD = str(DOCS / "target" / "page.md")
NEW = str(DOCS / "moved" / "page.md")


def _rename(url: str) -> tuple[bool, str]:
    node = LinkNode(url=url, children=[])
    m = RenameLinkMutation(SOURCE, str(DOCS), str(DOCS.parent), OLD, NEW)
    changed = m.apply(node)
    return changed, node.url


def test_suffixed_link_is_retargeted() -> None:
    """The control: this worked before and must keep working.

    Note the hop count differs from the extensionless cases by one, and that is
    the whole point: the generator rewrites this spelling, so it resolves against
    the source directory (``/docs/a/b``), while an extensionless href is emitted
    verbatim and resolves against the page URL (``/a/b/leaf/``).
    """
    changed, url = _rename("../../target/page.md")
    assert changed, "the .md control regressed"
    assert url.endswith("moved/page.md"), url


def test_extensionless_link_is_retargeted() -> None:
    """`../../../target/page` names the same file and must be updated too."""
    changed, url = _rename("../../../target/page")
    assert changed, "an extensionless href never matched the renamed file"


def test_extensionless_link_keeps_its_spelling() -> None:
    """The rewrite must stay extensionless, or it changes how it resolves."""
    _, url = _rename("../../../target/page")
    assert not url.endswith(".md"), f"spelling changed to a suffixed path: {url}"
    assert url.endswith("moved/page"), url


def test_extensionless_rewrite_resolves_at_url_depth() -> None:
    """From /a/b/leaf/, reaching /moved/page/ needs three hops, not two."""
    _, url = _rename("../../../target/page")
    assert url == "../../../moved/page", url


def test_an_unrelated_link_is_untouched() -> None:
    changed, url = _rename("../../../other/page")
    assert not changed
    assert url == "../../../other/page"
