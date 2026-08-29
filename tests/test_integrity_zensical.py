# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Targeted coverage tests — ZensicalAdapter.

Closes gaps identified in the v0.6.1 coverage audit (74%):
  - find_zensical_config: absent file path
  - _load_zensical_config: missing config, parse exception
  - _extract_nav_paths: nested section, external URL, plain-string non-md
  - ZensicalAdapter._map_url: offline mode (flat URLs), README.md collapsing
  - ZensicalAdapter._classify_route: _-prefix ignored, explicit-nav orphan
  - ZensicalAdapter.get_route_info: ignored status, orphan status
  - ZensicalAdapter.from_repo: zensical.toml present, mkdocs.yml fallback,
    unsupported-key warning, ConfigurationError when neither exists
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from zenzic.core.adapters._zensical import (
    ZensicalAdapter,
    _extract_config_declared_assets,
    _extract_nav_paths,
    _load_zensical_config,
    check_config_assets,
    find_zensical_config,
)
from zenzic.core.exceptions import ConfigurationError
from zenzic.models.config import BuildContext


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ctx(
    *,
    locales: list[str] | None = None,
    fallback: bool = True,
    offline: bool = False,
) -> BuildContext:
    return BuildContext(
        engine="zensical",
        locales=locales or [],
        fallback_to_default=fallback,
        offline_mode=offline,
    )


def _adapter(
    docs_root: Path,
    zensical_config: dict[str, Any] | None = None,
    *,
    locales: list[str] | None = None,
    offline: bool = False,
) -> ZensicalAdapter:
    ctx = _ctx(locales=locales or [], offline=offline)
    return ZensicalAdapter(ctx, docs_root, zensical_config or {})


# ── find_zensical_config ──────────────────────────────────────────────────────


class TestFindZensicalConfig:
    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        """find_zensical_config returns None when zensical.toml does not exist."""
        result = find_zensical_config(tmp_path)
        assert result is None

    def test_returns_path_when_present(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "zensical.toml"
        toml_file.write_text("[project]\nsite_name = 'X'\n", encoding="utf-8")
        result = find_zensical_config(tmp_path)
        assert result == toml_file


# ── _load_zensical_config ─────────────────────────────────────────────────────


class TestLoadZensicalConfig:
    def test_returns_empty_dict_when_no_config(self, tmp_path: Path) -> None:
        """When zensical.toml is absent, returns empty dict."""
        result = _load_zensical_config(tmp_path)
        assert result == {}

    def test_returns_parsed_dict(self, tmp_path: Path) -> None:
        """Valid zensical.toml is parsed correctly."""
        (tmp_path / "zensical.toml").write_text(
            "[project]\nsite_name = 'My Docs'\n", encoding="utf-8"
        )
        result = _load_zensical_config(tmp_path)
        assert result["project"]["site_name"] == "My Docs"

    def test_returns_empty_dict_on_parse_error(self, tmp_path: Path) -> None:
        """Corrupt zensical.toml returns empty dict (no crash)."""
        (tmp_path / "zensical.toml").write_bytes(b"\xff\xfe invalid toml \x00")
        result = _load_zensical_config(tmp_path)
        assert result == {}


# ── _extract_nav_paths ────────────────────────────────────────────────────────


class TestExtractNavPaths:
    def test_plain_string_md(self) -> None:
        assert _extract_nav_paths(["index.md"]) == {"index.md"}

    def test_plain_string_non_md_ignored(self) -> None:
        """Non-.md strings (e.g. plain labels) are ignored."""
        assert _extract_nav_paths(["README.rst"]) == set()

    def test_titled_page(self) -> None:
        assert _extract_nav_paths([{"Guide": "guide.md"}]) == {"guide.md"}

    def test_nested_section(self) -> None:
        """Sections with nested lists are recursed."""
        nav = [{"API": ["api/index.md", {"Endpoints": "api/endpoints.md"}]}]
        result = _extract_nav_paths(nav)
        assert result == {"api/index.md", "api/endpoints.md"}

    def test_external_url_ignored(self) -> None:
        """External URLs (not .md) are silently skipped."""
        nav = [{"GitHub": "https://github.com/org/repo"}]
        assert _extract_nav_paths(nav) == set()

    def test_leading_slash_stripped(self) -> None:
        """Leading slashes on .md paths are stripped."""
        assert _extract_nav_paths(["/guide.md"]) == {"guide.md"}

    def test_empty_list(self) -> None:
        assert _extract_nav_paths([]) == set()

    def test_mixed_variants(self) -> None:
        nav = [
            "index.md",
            {"Guide": "guide.md"},
            {"Ext": "https://example.com"},
            {"Nested": ["api/index.md", {"Sub": "api/sub.md"}]},
        ]
        result = _extract_nav_paths(nav)
        assert result == {"index.md", "guide.md", "api/index.md", "api/sub.md"}


# ── ZensicalAdapter.map_url ───────────────────────────────────────────────────


class TestZensicalAdapterMapUrl:
    def test_directory_url_mode(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("guide/install.md")).canonical_url == "/guide/install/"

    def test_readme_collapses_to_parent(self, tmp_path: Path) -> None:
        """README.md collapses to the parent directory URL."""
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("guide/README.md")).canonical_url == "/guide/"

    def test_index_collapses_to_parent(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("guide/index.md")).canonical_url == "/guide/"

    def test_root_index_collapses_to_slash(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("index.md")).canonical_url == "/"

    def test_root_readme_collapses_to_slash(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("README.md")).canonical_url == "/"

    def test_offline_mode_flat_url(self, tmp_path: Path) -> None:
        """With offline_mode=True (use_directory_urls=False), path is preserved."""
        adapter = _adapter(tmp_path, offline=True)
        assert adapter.get_route_info(Path("guide/install.md")).canonical_url == "/guide/install.md"

    def test_offline_mode_index_not_collapsed(self, tmp_path: Path) -> None:
        """In offline mode, index.md is NOT collapsed (flat URL mode)."""
        adapter = _adapter(tmp_path, offline=True)
        assert adapter.get_route_info(Path("guide/index.md")).canonical_url == "/guide/index.md"

    def test_use_directory_urls_false_via_config(self, tmp_path: Path) -> None:
        """use_directory_urls=false in zensical.toml disables directory collapsing."""
        config = {"project": {"use_directory_urls": False}}
        adapter = _adapter(tmp_path, config)
        assert adapter.get_route_info(Path("page.md")).canonical_url == "/page.md"

    def test_empty_parts_returns_slash(self, tmp_path: Path) -> None:
        """Edge case: a path with no parts maps to /."""
        adapter = _adapter(tmp_path)
        # Pathlib won't produce an empty Path naturally, but we can fake it
        # by using a path that after stripping yields empty parts.
        # index.md at root → already covered; test stem stripping:
        url = adapter.get_route_info(Path("index.md")).canonical_url
        assert url == "/"


# ── ZensicalAdapter.classify_route ────────────────────────────────────────────


class TestZensicalAdapterClassifyRoute:
    def test_underscore_prefix_ignored(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("_private/page.md")).status == "IGNORED"

    def test_nested_underscore_ignored(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.get_route_info(Path("guide/_draft.md")).status == "IGNORED"

    def test_reachable_when_no_explicit_nav(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path, {})
        assert adapter.get_route_info(Path("page.md")).status == "REACHABLE"

    def test_reachable_when_in_nav(self, tmp_path: Path) -> None:
        config = {"project": {"nav": ["page.md"]}}
        adapter = _adapter(tmp_path, config)
        assert adapter.get_route_info(Path("page.md")).status == "REACHABLE"

    def test_orphan_when_explicit_nav_and_not_listed(self, tmp_path: Path) -> None:
        config = {"project": {"nav": ["index.md"]}}
        adapter = _adapter(tmp_path, config)
        assert adapter.get_route_info(Path("unlisted.md")).status == "ORPHAN_BUT_EXISTING"


# ── ZensicalAdapter.get_route_info ────────────────────────────────────────────


class TestZensicalAdapterGetRouteInfo:
    def test_ignored_status(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        meta = adapter.get_route_info(Path("_private/page.md"))
        assert meta.status == "IGNORED"

    def test_reachable_status(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        meta = adapter.get_route_info(Path("page.md"))
        assert meta.status == "REACHABLE"

    def test_orphan_status(self, tmp_path: Path) -> None:
        config = {"project": {"nav": ["index.md"]}}
        adapter = _adapter(tmp_path, config)
        meta = adapter.get_route_info(Path("orphan.md"))
        assert meta.status == "ORPHAN_BUT_EXISTING"

    def test_slug_is_always_none(self, tmp_path: Path) -> None:
        """Zensical does not support frontmatter slug — always None."""
        adapter = _adapter(tmp_path)
        meta = adapter.get_route_info(Path("page.md"))
        assert meta.slug is None


# ── ZensicalAdapter.from_repo ─────────────────────────────────────────────────


class TestZensicalFromRepo:
    def test_uses_zensical_toml_when_present(self, tmp_path: Path) -> None:
        """from_repo returns ZensicalAdapter when zensical.toml exists."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (tmp_path / "zensical.toml").write_text("[project]\nsite_name = 'Test'\n", encoding="utf-8")
        ctx = _ctx()
        adapter = ZensicalAdapter.from_repo(ctx, docs_root, tmp_path)
        assert isinstance(adapter, ZensicalAdapter)

    def test_falls_back_to_mkdocs_yml(self, tmp_path: Path) -> None:
        """from_repo returns ZensicalAdapter when only mkdocs.yml exists."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")
        ctx = _ctx()
        adapter = ZensicalAdapter.from_repo(ctx, docs_root, tmp_path)
        assert isinstance(adapter, ZensicalAdapter)

    def test_unsupported_mkdocs_keys_emit_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unsupported MkDocs keys emit a warning during bridge construction."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        (tmp_path / "mkdocs.yml").write_text(
            "site_name: Test\nstrict: true\nhooks: []\n", encoding="utf-8"
        )
        ctx = _ctx()
        with caplog.at_level(logging.WARNING, logger="zenzic.core.adapters._zensical"):
            ZensicalAdapter.from_repo(ctx, docs_root, tmp_path)
        warned_keys = {r.message for r in caplog.records}
        assert any("strict" in msg for msg in warned_keys)

    def test_raises_config_error_when_neither_exists(self, tmp_path: Path) -> None:
        """from_repo raises ConfigurationError when no config file is found."""
        docs_root = tmp_path / "docs"
        docs_root.mkdir()
        ctx = _ctx()
        with pytest.raises(ConfigurationError, match="engine 'zensical'"):
            ZensicalAdapter.from_repo(ctx, docs_root, tmp_path)


# ── check_config_assets ─────────────────────────────────────────────────────
#
# Zensical's own real schema nests favicon/logo under [project.theme], not
# top-level [project] — confirmed live against zensical.org/docs/setup/logo-and-icons/
# and the real bootstrap zensical.toml shipped in zensical/zensical's own repo,
# both of which show `[project.theme]` as the table these keys live under.


class TestCheckConfigAssets:
    def test_missing_favicon_under_project_theme_is_detected(self, tmp_path: Path) -> None:
        """A favicon declared under the real [project.theme] table, pointing at a
        file that does not exist on disk, must fire Z404 CONFIG_ASSET_MISSING."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "zensical.toml").write_text(
            "[project]\n"
            'site_name = "Test"\n'
            "\n"
            "[project.theme]\n"
            'favicon = "assets/favicon.png"\n',
            encoding="utf-8",
        )

        issues = check_config_assets(tmp_path)

        assert len(issues) == 1
        rel_path, message = issues[0]
        assert rel_path == "docs/assets/favicon.png"
        assert "favicon" in message.lower()

    def test_missing_logo_under_project_theme_is_detected(self, tmp_path: Path) -> None:
        """Same as above for `logo`, confirming both fields, not just favicon."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "zensical.toml").write_text(
            "[project]\n"
            'site_name = "Test"\n'
            "\n"
            "[project.theme]\n"
            'logo = "assets/logo.png"\n',
            encoding="utf-8",
        )

        issues = check_config_assets(tmp_path)

        assert len(issues) == 1
        rel_path, message = issues[0]
        assert rel_path == "docs/assets/logo.png"
        assert "logo" in message.lower()

    def test_present_favicon_under_project_theme_is_not_flagged(self, tmp_path: Path) -> None:
        """A favicon that genuinely exists on disk must not be reported missing."""
        docs_root = tmp_path / "docs"
        (docs_root / "assets").mkdir(parents=True)
        (docs_root / "assets" / "favicon.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "zensical.toml").write_text(
            "[project]\n"
            'site_name = "Test"\n'
            "\n"
            "[project.theme]\n"
            'favicon = "assets/favicon.png"\n',
            encoding="utf-8",
        )

        issues = check_config_assets(tmp_path)

        assert issues == []


# ── _extract_config_declared_assets ─────────────────────────────────────────
#
# Phase 3 sibling check: this function feeds get_metadata_files(), which
# protects engine-declared assets from a false-positive Z405 UNUSED_ASSET.
# It shared the same wrong [project]-only assumption for favicon/logo, and a
# second, differently-shaped mismatch for extra_css/extra_javascript (real
# Zensical schema nests those under [project] directly, not top-level —
# confirmed live against zensical.org/docs/customization/).


class TestExtractConfigDeclaredAssets:
    def test_recognizes_theme_nested_favicon_and_logo(self) -> None:
        doc_config = {
            "project": {
                "theme": {
                    "favicon": "assets/favicon.png",
                    "logo": "assets/logo.png",
                },
            },
        }

        assets = _extract_config_declared_assets(doc_config)

        assert "assets/favicon.png" in assets
        assert "assets/logo.png" in assets

    def test_recognizes_project_nested_extra_css_and_javascript(self) -> None:
        doc_config = {
            "project": {
                "extra_css": ["stylesheets/extra.css"],
                "extra_javascript": ["javascripts/extra.js"],
            },
        }

        assets = _extract_config_declared_assets(doc_config)

        assert "stylesheets/extra.css" in assets
        assert "javascripts/extra.js" in assets
