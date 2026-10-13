# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""TEAM BLUE — VSM edge-case stress tests.

Tests unusual structures: special characters, .mdx/.md mixing,
files outside docs/, nested paths, collision detection edge cases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zenzic.core.adapters._mkdocs import MkDocsAdapter
from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.models.config import BuildContext
from zenzic.models.vsm import Route, _detect_collisions


def _mkdocs(docs_root: Path, config: dict[str, Any] | None = None) -> MkDocsAdapter:
    return MkDocsAdapter(BuildContext(), docs_root, config or {})


class TestCollisionEdgeCases:
    """Edge cases in _detect_collisions."""

    def test_empty_routes(self) -> None:
        _detect_collisions([])

    def test_single_route_no_collision(self) -> None:
        r = Route(url="/a/", source="a.md", status="REACHABLE")
        _detect_collisions([r])
        assert r.status == "REACHABLE"

    def test_collision_preserves_source(self) -> None:
        """After collision, source paths are preserved."""
        r1 = Route(url="/x/", source="x.md", status="REACHABLE")
        r2 = Route(url="/x/", source="y.md", status="REACHABLE")
        _detect_collisions([r1, r2])
        assert r1.source == "x.md"
        assert r2.source == "y.md"

    def test_four_way_collision(self) -> None:
        routes = [Route(url="/z/", source=f"{i}.md", status="REACHABLE") for i in range(4)]
        _detect_collisions(routes)
        assert all(r.status == "CONFLICT" for r in routes)


class TestMkDocsNestedNav:
    """MkDocs nav can have deeply nested structures."""

    def test_deeply_nested_nav_page_reachable(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        config = {"nav": [{"Section A": [{"Subsection": [{"Deep Page": "a/b/c/deep.md"}]}]}]}
        adapter = _mkdocs(docs, config)
        nav_paths = adapter.get_nav_paths()
        assert "a/b/c/deep.md" in nav_paths
        assert adapter.get_route_info(Path("a/b/c/deep.md")).status == "REACHABLE"

    def test_page_not_in_nested_nav_is_orphan(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        config = {"nav": [{"Home": "index.md"}]}
        adapter = _mkdocs(docs, config)
        assert adapter.get_route_info(Path("unlisted.md")).status == "ORPHAN_BUT_EXISTING"


class TestStandaloneEdgeCases:
    """StandaloneAdapter treats everything as reachable."""

    def test_deeply_nested(self) -> None:
        adapter = StandaloneAdapter()
        assert adapter.get_route_info(Path("a/b/c/d.md")).canonical_url == "/a/b/c/d/"

    def test_special_chars(self) -> None:
        adapter = StandaloneAdapter()
        url = adapter.get_route_info(Path("my-file (1).md")).canonical_url
        assert "/my-file (1)/" == url
