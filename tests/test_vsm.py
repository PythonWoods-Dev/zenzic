# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Virtual Site Map (VSM) — models/vsm.py and adapter integration.

Test philosophy (The Zenzic Way):
- Pure functions are tested with in-memory inputs only.
- I/O tests use tmp_path to create real but ephemeral filesystem trees.
- Every test asserts a single, named invariant.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from _helpers import make_mgr

from zenzic.core.adapters._mkdocs import MkDocsAdapter
from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.core.adapters._zensical import ZensicalAdapter
from zenzic.core.validator import validate_links
from zenzic.models.config import BuildContext, ZenzicConfig
from zenzic.models.vsm import Route, _detect_collisions, build_vsm


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_docs(root: Path, files: dict[str, str]) -> None:
    """Create stub .md files with given content under root/docs/."""
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    for rel, content in files.items():
        p = docs / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _write_mkdocs(root: Path, config: dict) -> None:  # type: ignore[type-arg]
    with (root / "mkdocs.yml").open("w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def _write_zenzic_toml(root: Path, engine: str = "mkdocs") -> None:
    (root / ".zenzic.toml").write_text(f'[build_context]\nengine = "{engine}"\n', encoding="utf-8")


# ─── Route dataclass ──────────────────────────────────────────────────────────


class TestRoute:
    def test_is_reachable_true(self) -> None:
        r = Route(url="/page/", source="page.md", status="REACHABLE")
        assert r.is_reachable is True

    def test_is_reachable_false_for_orphan(self) -> None:
        r = Route(url="/page/", source="page.md", status="ORPHAN_BUT_EXISTING")
        assert r.is_reachable is False

    def test_is_conflict_true(self) -> None:
        r = Route(url="/dir/", source="dir/index.md", status="CONFLICT")
        assert r.is_conflict is True

    def test_anchors_default_empty(self) -> None:
        r = Route(url="/page/", source="page.md", status="REACHABLE")
        assert r.anchors == set()

    def test_aliases_default_empty(self) -> None:
        r = Route(url="/page/", source="page.md", status="REACHABLE")
        assert r.aliases == set()


# ─── _detect_collisions (pure) ────────────────────────────────────────────────


class TestDetectCollisions:
    def test_no_collision_leaves_status_unchanged(self) -> None:
        routes = [
            Route(url="/a/", source="a.md", status="REACHABLE"),
            Route(url="/b/", source="b.md", status="REACHABLE"),
        ]
        _detect_collisions(routes)
        assert all(r.status == "REACHABLE" for r in routes)

    def test_two_files_same_url_both_marked_conflict(self) -> None:
        routes = [
            Route(url="/dir/", source="dir/index.md", status="REACHABLE"),
            Route(url="/dir/", source="dir/README.md", status="REACHABLE"),
        ]
        _detect_collisions(routes)
        assert all(r.status == "CONFLICT" for r in routes)

    def test_double_index_conflict(self) -> None:
        """index.md + README.md in same dir → same URL → CONFLICT (Double Index)."""
        routes = [
            Route(url="/guide/", source="guide/index.md", status="REACHABLE"),
            Route(url="/guide/", source="guide/README.md", status="REACHABLE"),
        ]
        _detect_collisions(routes)
        assert routes[0].status == "CONFLICT"
        assert routes[1].status == "CONFLICT"

    def test_first_route_also_marked_when_collision_found_later(self) -> None:
        """The first route must be retroactively marked CONFLICT."""
        r1 = Route(url="/x/", source="x.md", status="REACHABLE")
        r2 = Route(url="/x/", source="x2.md", status="ORPHAN_BUT_EXISTING")
        _detect_collisions([r1, r2])
        assert r1.status == "CONFLICT"

    def test_three_way_collision(self) -> None:
        routes = [
            Route(url="/same/", source="a.md", status="REACHABLE"),
            Route(url="/same/", source="b.md", status="REACHABLE"),
            Route(url="/same/", source="c.md", status="REACHABLE"),
        ]
        _detect_collisions(routes)
        assert all(r.status == "CONFLICT" for r in routes)


# ─── MkDocsAdapter.map_url ────────────────────────────────────────────────────


class TestMkDocsAdapterMapUrl:
    def _make_adapter(self, config: dict | None = None) -> MkDocsAdapter:  # type: ignore[type-arg]
        ctx = BuildContext()
        return MkDocsAdapter(ctx, Path("/docs"), config or {})

    def test_page_md_maps_to_slash_page_slash(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("page.md")).canonical_url == "/page/"

    def test_index_md_maps_to_slash(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("index.md")).canonical_url == "/"

    def test_nested_index_md(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("guide/index.md")).canonical_url == "/guide/"

    def test_readme_md_same_as_index(self) -> None:
        """README.md must produce the same URL as index.md → collision risk."""
        a = self._make_adapter()
        assert a.get_route_info(Path("guide/README.md")).canonical_url == "/guide/"

    def test_nested_page(self) -> None:
        a = self._make_adapter()
        assert (
            a.get_route_info(Path("guide/installation.md")).canonical_url == "/guide/installation/"
        )

    def test_no_directory_urls(self) -> None:
        a = self._make_adapter({"use_directory_urls": False})
        assert a.get_route_info(Path("page.md")).canonical_url == "/page.html"

    def test_no_directory_urls_index(self) -> None:
        # With use_directory_urls=false, guide/index.md → parts=["guide"] → /guide.html
        a = self._make_adapter({"use_directory_urls": False})
        assert a.get_route_info(Path("guide/index.md")).canonical_url == "/guide.html"

    def test_jpg_asset_preserves_exact_path(self) -> None:
        """Static assets must not receive use_directory_urls transformation (Z101 fix)."""
        a = self._make_adapter()
        assert a.get_route_info(Path("blog/posts/hero.jpg")).canonical_url == "/blog/posts/hero.jpg"

    def test_png_asset_preserves_exact_path(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("assets/logo.png")).canonical_url == "/assets/logo.png"

    def test_css_asset_preserves_exact_path(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("assets/style.css")).canonical_url == "/assets/style.css"

    def test_asset_exact_path_even_when_use_directory_urls_true(self) -> None:
        """use_directory_urls=True must not affect non-Markdown asset routing."""
        a = self._make_adapter({"use_directory_urls": True})
        assert (
            a.get_route_info(Path("blog/posts/photo.jpg")).canonical_url == "/blog/posts/photo.jpg"
        )

    def test_asset_exact_path_even_when_use_directory_urls_false(self) -> None:
        """use_directory_urls=False must not affect non-Markdown asset routing."""
        a = self._make_adapter({"use_directory_urls": False})
        assert (
            a.get_route_info(Path("blog/posts/photo.jpg")).canonical_url == "/blog/posts/photo.jpg"
        )


# ─── MkDocsAdapter.classify_route ────────────────────────────────────────────


class TestMkDocsAdapterClassifyRoute:
    def _make_adapter(self, nav_paths: frozenset[str]) -> MkDocsAdapter:
        nav_list = [{"page": p} for p in nav_paths]
        ctx = BuildContext()
        return MkDocsAdapter(ctx, Path("/docs"), {"nav": nav_list})

    def test_file_in_nav_is_reachable(self) -> None:
        a = self._make_adapter(frozenset({"index.md"}))
        assert a.get_route_info(Path("index.md")).status == "REACHABLE"

    def test_file_not_in_nav_is_orphan(self) -> None:
        a = self._make_adapter(frozenset({"index.md"}))
        assert a.get_route_info(Path("draft.md")).status == "ORPHAN_BUT_EXISTING"

    def test_readme_not_in_nav_is_ignored(self) -> None:
        a = self._make_adapter(frozenset({"index.md"}))
        assert a.get_route_info(Path("README.md")).status == "IGNORED"

    def test_readme_in_nav_is_reachable(self) -> None:
        a = self._make_adapter(frozenset({"README.md"}))
        assert a.get_route_info(Path("README.md")).status == "REACHABLE"


# ─── Ghost Route: reconfigure_material locale entry points ───────────────────
# Dev 4 (QA) mandated test suite.
# Invariant: when reconfigure_material: true, the locale index page (e.g.
# it/index.md) is a synthetic route auto-generated by mkdocs-material and
# must be REACHABLE even though it is absent from nav.
# Regression: when reconfigure_material: false (or absent), the same file
# must revert to ORPHAN_BUT_EXISTING.


_GHOST_ROUTE_CONFIG_ON = {
    "plugins": [
        {
            "i18n": {
                "docs_structure": "folder",
                "reconfigure_material": True,
                "languages": [
                    {"locale": "en", "default": True, "build": True},
                    {"locale": "it", "build": True},
                ],
            }
        }
    ],
    "nav": [{"Home": "index.md"}],
}

_GHOST_ROUTE_CONFIG_OFF = {
    "plugins": [
        {
            "i18n": {
                "docs_structure": "folder",
                "reconfigure_material": False,
                "languages": [
                    {"locale": "en", "default": True, "build": True},
                    {"locale": "it", "build": True},
                ],
            }
        }
    ],
    "nav": [{"Home": "index.md"}],
}

_NAV_PATHS = frozenset({"index.md"})


class TestGhostRouteReconfigureMaterial:
    """Dev 4 mandated Ghost Route integration tests."""

    def _make_adapter(self, config: dict) -> MkDocsAdapter:  # type: ignore[type-arg]
        ctx = BuildContext()
        return MkDocsAdapter(ctx, Path("/docs"), config)

    # ── Positive path (reconfigure_material: true) ──────────────────────────

    def test_locale_index_is_reachable_when_reconfigure_material_true(self) -> None:
        """it/index.md → REACHABLE when reconfigure_material: true."""
        a = self._make_adapter(_GHOST_ROUTE_CONFIG_ON)
        assert a.get_route_info(Path("it/index.md")).status == "REACHABLE"

    def test_locale_readme_is_ignored_not_a_ghost_route(self) -> None:
        """it/README.md → IGNORED: the README.md rule (rule 1) fires before the
        ghost-route rule.  Material does not synthesise README entry points."""
        a = self._make_adapter(_GHOST_ROUTE_CONFIG_ON)
        assert a.get_route_info(Path("it/README.md")).status == "IGNORED"

    # ── Regression path (reconfigure_material: false) ────────────────────────
    # NOTE: we use it/extra.md (no default-locale equivalent in nav) rather than
    # it/index.md so that is_shadow_of_nav_page() does not kick in and mask the
    # reconfigure_material regression.  The shadow logic is correct and intentional
    # — it/index.md IS reachable via the shadow of index.md regardless of the flag.

    def test_non_shadow_locale_page_is_orphan_when_reconfigure_material_false(self) -> None:
        """it/extra.md has no default-locale equivalent in nav → ORPHAN_BUT_EXISTING
        when reconfigure_material: false (ghost-route rule inactive)."""
        a = self._make_adapter(_GHOST_ROUTE_CONFIG_OFF)
        assert a.get_route_info(Path("it/extra.md")).status == "ORPHAN_BUT_EXISTING"

    def test_non_shadow_locale_page_is_orphan_when_reconfigure_material_absent(self) -> None:
        """it/extra.md → ORPHAN_BUT_EXISTING when reconfigure_material key is absent."""
        config_no_key = {
            "plugins": [
                {
                    "i18n": {
                        "docs_structure": "folder",
                        "languages": [
                            {"locale": "en", "default": True, "build": True},
                            {"locale": "it", "build": True},
                        ],
                    }
                }
            ],
            "nav": [{"Home": "index.md"}],
        }
        a = self._make_adapter(config_no_key)
        assert a.get_route_info(Path("it/extra.md")).status == "ORPHAN_BUT_EXISTING"

    # ── Boundary: explicit nav entry must NOT be overridden ──────────────────

    def test_locale_index_in_nav_stays_reachable_regardless_of_flag(self) -> None:
        """If it/index.md is explicitly in nav, classify_route must return REACHABLE
        via the standard nav path — the reconfigure_material branch is never reached."""
        a = self._make_adapter(_GHOST_ROUTE_CONFIG_ON)
        assert a.get_route_info(Path("it/index.md")).status == "REACHABLE"

    # ── Boundary: deeper locale pages are NOT ghost routes ───────────────────

    def test_nested_locale_page_is_not_a_ghost_route(self) -> None:
        """it/guide/index.md is not a top-level entry point → ORPHAN_BUT_EXISTING
        even when reconfigure_material: true (shadow logic handles it via
        is_shadow_of_nav_page, not the ghost-route rule)."""
        a = self._make_adapter(_GHOST_ROUTE_CONFIG_ON)
        # guide/index.md is not in nav → shadow check also returns False → ORPHAN
        assert a.get_route_info(Path("it/guide/index.md")).status == "ORPHAN_BUT_EXISTING"

    # ── End-to-end VSM integration (filesystem) ──────────────────────────────

    def test_ghost_route_reachable_in_vsm(self, tmp_path: Path) -> None:
        """Full VSM build: it/index.md must appear as REACHABLE in the VSM
        when reconfigure_material: true, even though it is absent from nav."""
        _make_docs(tmp_path, {"index.md": "# Home", "it/index.md": "# Home IT"})
        docs_root = (tmp_path / "docs").resolve()
        adapter = MkDocsAdapter(BuildContext(), docs_root, _GHOST_ROUTE_CONFIG_ON)
        md_contents = {
            (docs_root / "index.md").resolve(): "# Home",
            (docs_root / "it" / "index.md").resolve(): "# Home IT",
        }
        vsm = build_vsm(adapter, docs_root, md_contents)
        assert "/it/" in vsm, "Ghost route /it/ missing from VSM"
        assert vsm["/it/"].status == "REACHABLE"

    def test_non_index_ghost_route_orphan_in_vsm_when_flag_off(self, tmp_path: Path) -> None:
        """Regression: with reconfigure_material: false, it/extra.md (no default-locale
        equivalent in nav) must be ORPHAN_BUT_EXISTING in the VSM.
        it/index.md is intentionally not used here because is_shadow_of_nav_page
        correctly marks it REACHABLE regardless of the flag — that is the right
        behaviour for shadow pages."""
        _make_docs(tmp_path, {"index.md": "# Home", "it/extra.md": "# Extra IT"})
        docs_root = (tmp_path / "docs").resolve()
        adapter = MkDocsAdapter(BuildContext(), docs_root, _GHOST_ROUTE_CONFIG_OFF)
        md_contents = {
            (docs_root / "index.md").resolve(): "# Home",
            (docs_root / "it" / "extra.md").resolve(): "# Extra IT",
        }
        vsm = build_vsm(adapter, docs_root, md_contents)
        assert "/it/extra/" in vsm, "/it/extra/ missing from VSM"
        assert vsm["/it/extra/"].status == "ORPHAN_BUT_EXISTING"


# ─── ZensicalAdapter.map_url + classify_route ─────────────────────────────────


class TestZensicalAdapterMapUrl:
    def _make_adapter(self) -> ZensicalAdapter:
        return ZensicalAdapter(BuildContext(), Path("/docs"), {})

    def test_page_md(self) -> None:
        assert self._make_adapter().get_route_info(Path("page.md")).canonical_url == "/page/"

    def test_index_md(self) -> None:
        assert self._make_adapter().get_route_info(Path("index.md")).canonical_url == "/"

    def test_readme_md_treated_as_index(self) -> None:
        assert (
            self._make_adapter().get_route_info(Path("guide/README.md")).canonical_url == "/guide/"
        )

    def test_nested_page(self) -> None:
        assert (
            self._make_adapter().get_route_info(Path("guide/install.md")).canonical_url
            == "/guide/install/"
        )

    def test_all_files_reachable(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("any/page.md")).status == "REACHABLE"

    def test_underscore_prefix_is_ignored(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("_private/notes.md")).status == "IGNORED"

    def test_underscore_in_nested_segment_is_ignored(self) -> None:
        a = self._make_adapter()
        assert a.get_route_info(Path("section/_draft.md")).status == "IGNORED"


# ─── build_vsm (I/O boundary) ─────────────────────────────────────────────────


class TestBuildVsm:
    def _adapter_and_contents(
        self,
        tmp_path: Path,
        files: dict[str, str],
        nav: list | None = None,  # type: ignore[type-arg]
    ) -> tuple[MkDocsAdapter, Path, dict[Path, str]]:
        _make_docs(tmp_path, files)
        docs_root = (tmp_path / "docs").resolve()
        cfg: dict = {"nav": nav} if nav is not None else {}  # type: ignore[type-arg]
        adapter = MkDocsAdapter(BuildContext(), docs_root, cfg)
        md_contents = {(docs_root / rel).resolve(): content for rel, content in files.items()}
        return adapter, docs_root, md_contents

    def test_single_reachable_page(self, tmp_path: Path) -> None:
        adapter, docs_root, md_contents = self._adapter_and_contents(
            tmp_path,
            {"index.md": "# Home"},
            nav=[{"Home": "index.md"}],
        )
        vsm = build_vsm(adapter, docs_root, md_contents)
        assert "/" in vsm
        assert vsm["/"].status == "REACHABLE"

    def test_orphan_page_present(self, tmp_path: Path) -> None:
        adapter, docs_root, md_contents = self._adapter_and_contents(
            tmp_path,
            {"index.md": "# Home", "draft.md": "# Draft"},
            nav=[{"Home": "index.md"}],
        )
        vsm = build_vsm(adapter, docs_root, md_contents)
        assert "/draft/" in vsm
        assert vsm["/draft/"].status == "ORPHAN_BUT_EXISTING"

    def test_ignored_readme_excluded_from_vsm(self, tmp_path: Path) -> None:
        """README.md not in nav → IGNORED → excluded from returned VSM."""
        adapter, docs_root, md_contents = self._adapter_and_contents(
            tmp_path,
            {"index.md": "# Home", "README.md": "# Readme"},
            nav=[{"Home": "index.md"}],
        )
        vsm = build_vsm(adapter, docs_root, md_contents)
        # README maps to "/" same as index.md, but is IGNORED → excluded
        # index.md wins the "/" URL as REACHABLE
        assert "/" in vsm

    def test_double_index_conflict(self, tmp_path: Path) -> None:
        """index.md + README.md in same dir both map to /dir/ → CONFLICT."""
        adapter, docs_root, md_contents = self._adapter_and_contents(
            tmp_path,
            {
                "guide/index.md": "# Guide",
                "guide/README.md": "# Guide Readme",
                "index.md": "# Home",
            },
            nav=[{"Home": "index.md"}, {"Guide": "guide/index.md"}],
        )
        vsm = build_vsm(adapter, docs_root, md_contents)
        # Both map to /guide/ → CONFLICT; CONFLICT routes ARE included in VSM
        assert "/guide/" in vsm
        assert vsm["/guide/"].status == "CONFLICT"

    def test_anchors_propagated(self, tmp_path: Path) -> None:
        adapter, docs_root, md_contents = self._adapter_and_contents(
            tmp_path,
            {"index.md": "# Quick Start\n\n## Installation"},
            nav=[{"Home": "index.md"}],
        )
        from zenzic.core.validator import anchors_in_file

        anchors_cache = {p: anchors_in_file(c) for p, c in md_contents.items()}
        vsm = build_vsm(adapter, docs_root, md_contents, anchors_cache=anchors_cache)
        assert "quick-start" in vsm["/"].anchors
        assert "installation" in vsm["/"].anchors

    def test_zensical_all_reachable(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, {"index.md": "# Home", "draft.md": "# Draft"})
        docs_root = (tmp_path / "docs").resolve()
        adapter = ZensicalAdapter(BuildContext(), docs_root, {})
        md_contents = {
            (docs_root / "index.md").resolve(): "# Home",
            (docs_root / "draft.md").resolve(): "# Draft",
        }
        vsm = build_vsm(adapter, docs_root, md_contents)
        assert vsm["/"].status == "REACHABLE"
        assert vsm["/draft/"].status == "REACHABLE"

    def test_standalone_all_reachable(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, {"index.md": "# Home", "page.md": "# Page"})
        docs_root = (tmp_path / "docs").resolve()
        adapter = StandaloneAdapter()
        md_contents = {
            (docs_root / "index.md").resolve(): "# Home",
            (docs_root / "page.md").resolve(): "# Page",
        }
        vsm = build_vsm(adapter, docs_root, md_contents)
        assert vsm["/"].status == "REACHABLE"
        assert vsm["/page/"].status == "REACHABLE"


# ─── Dev 4 Mandato: "Zenzic rc4 vs Pulsante Get Started" ────────────────────
# This test fulfils the QA/Inquisitor directive: validate_links must emit
# UNREACHABLE_LINK when a link points to a file that exists on disk but is
# not listed in the MkDocs nav.  It models the real-world scenario where a
# "Get Started" button links to a page that was accidentally removed from nav.


class TestUnreachableLinkDetection:
    def _build_repo(
        self,
        tmp_path: Path,
        nav_files: list[str],
        link_from: str,
        link_to: str,
        link_content: str,
    ) -> Path:
        """Build a minimal docs repo and return the repo root."""
        all_files = {f: f"# {f}\n" for f in nav_files}
        all_files[link_from] = f"# Source\n\n[Get Started]({link_content})\n"
        _make_docs(tmp_path, all_files)
        _write_zenzic_toml(tmp_path, engine="mkdocs")
        nav_entries = [{f.split("/")[-1]: f} for f in nav_files]
        _write_mkdocs(tmp_path, {"site_name": "Test", "docs_dir": "docs", "nav": nav_entries})
        return tmp_path

    def test_link_to_nav_page_is_ok(self, tmp_path: Path) -> None:
        """Button pointing to a REACHABLE page → no errors."""
        repo = self._build_repo(
            tmp_path,
            nav_files=["index.md", "guide/index.md"],
            link_from="index.md",
            link_to="guide/index.md",
            link_content="guide/index.md",
        )
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        errors = validate_links(docs_root, mgr, repo_root=repo, config=config)
        assert not any("UNREACHABLE_LINK" in e for e in errors)

    def test_link_to_orphan_page_emits_unreachable_link(self, tmp_path: Path) -> None:
        """Button pointing to a page that exists on disk but is NOT in nav
        must produce an UNREACHABLE_LINK error.  This is the 'Get Started'
        scenario from the rc4 brief."""
        # guide/index.md exists on disk but is NOT listed in nav
        _make_docs(
            tmp_path,
            {
                "index.md": "[Get Started](guide/index.md)\n",
                "guide/index.md": "# Guide\n",
            },
        )
        _write_zenzic_toml(tmp_path, engine="mkdocs")
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "docs_dir": "docs",
                "nav": [{"Home": "index.md"}],  # guide/index.md intentionally absent
            },
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert any("UNREACHABLE_LINK" in e for e in errors), (
            f"Expected UNREACHABLE_LINK in errors but got: {errors}"
        )

    def test_standalone_adapter_never_emits_unreachable_link(self, tmp_path: Path) -> None:
        """Without mkdocs.yml (StandaloneAdapter), no UNREACHABLE_LINK is emitted
        because every file is implicitly reachable."""
        _make_docs(
            tmp_path,
            {
                "index.md": "[link](draft.md)\n",
                "draft.md": "# Draft\n",
            },
        )
        _write_zenzic_toml(tmp_path, engine="mkdocs")
        # No mkdocs.yml → StandaloneAdapter
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert not any("UNREACHABLE_LINK" in e for e in errors)

    def test_zensical_never_emits_unreachable_link(self, tmp_path: Path) -> None:
        """Zensical is filesystem-driven — all files are reachable by design."""
        _make_docs(
            tmp_path,
            {
                "index.md": "[link](draft.md)\n",
                "draft.md": "# Draft\n",
            },
        )
        _write_zenzic_toml(tmp_path, engine="zensical")
        (tmp_path / "zensical.toml").write_text(
            '[site]\nname = "Test"\n[nav]\nnav = []\n', encoding="utf-8"
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert not any("UNREACHABLE_LINK" in e for e in errors)

    def test_conflict_route_not_emitting_unreachable_link(self, tmp_path: Path) -> None:
        """A CONFLICT route is a build error, not an unreachable link per se.
        The engine should not double-report it as UNREACHABLE_LINK."""
        _make_docs(
            tmp_path,
            {
                "index.md": "[link](guide/index.md)\n",
                "guide/index.md": "# Guide\n",
                "guide/README.md": "# Guide Readme\n",
            },
        )
        _write_zenzic_toml(tmp_path, engine="mkdocs")
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "docs_dir": "docs",
                "nav": [{"Home": "index.md"}, {"Guide": "guide/index.md"}],
            },
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        # Should not contain UNREACHABLE_LINK for the CONFLICT route
        unreachable = [e for e in errors if "UNREACHABLE_LINK" in e]
        assert not unreachable, f"Unexpected UNREACHABLE_LINK for CONFLICT route: {unreachable}"
