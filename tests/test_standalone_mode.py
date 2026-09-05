# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Adapter Factory: StandaloneAdapter, engine routing, and
Zensical Native Enforcement.

Covers:
* StandaloneAdapter unit behaviour
* get_adapter engine routing (Multi-Engine Matrix)
* Zensical Identity Violation — ConfigurationError when zensical.toml is absent
* find_orphans integration for standalone and Zensical repos
* Legacy aliases and unknown engines fall back to StandaloneAdapter
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _helpers import make_mgr

from zenzic.core.adapter import (
    BaseAdapter,
    MkDocsAdapter,
    StandaloneAdapter,
    ZensicalAdapter,
    get_adapter,
)
from zenzic.core.adapters._factory import discover_engine
from zenzic.core.exceptions import ConfigurationError
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.scanner import find_orphans
from zenzic.models.config import BuildContext, ZenzicConfig


def _mkdocs(repo: Path, nav: list[str] | None = None) -> None:
    """Write a minimal mkdocs.yml into *repo*."""
    nav_lines = "\n".join(f"  - '{p}'" for p in nav or ["index.md"])
    (repo / "mkdocs.yml").write_text(f"site_name: Test\nnav:\n{nav_lines}\n")


def _zensical(repo: Path, nav: list[str] | None = None) -> None:
    """Write a minimal zensical.toml into *repo*."""
    nav_items = "\n".join(f'  "{p}",' for p in nav or ["index.md"])
    (repo / "zensical.toml").write_text(
        f'[project]\nsite_name = "Test"\ndocs_dir = "docs"\nnav = [\n{nav_items}\n]\n'
    )


def _run_find_orphans(
    repo_root: Path, config: ZenzicConfig, mgr: LayeredExclusionManager
) -> list[Path]:
    """Execute find_orphans via adapter."""
    docs_root = repo_root / config.docs_dir
    adapter = get_adapter(config.build_context, docs_root, repo_root)
    return find_orphans(docs_root, mgr, config=config, adapter=adapter)


def test_standalone_adapter_satisfies_base_adapter_protocol() -> None:
    assert isinstance(StandaloneAdapter(), BaseAdapter)


def test_standalone_is_locale_dir_always_false() -> None:
    a = StandaloneAdapter()
    for code in ("it", "fr", "en", ""):
        assert not a.is_locale_dir(code)


def test_standalone_resolve_asset_always_none(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    assert StandaloneAdapter().resolve_asset(docs / "it" / "logo.png", docs) is None


def test_standalone_is_shadow_of_nav_page_always_false() -> None:
    nav = frozenset({"index.md", "guide/start.md"})
    a = StandaloneAdapter()
    assert not a.is_shadow_of_nav_page(Path("it/index.md"), nav)
    assert not a.is_shadow_of_nav_page(Path("fr/guide/start.md"), nav)


def test_standalone_get_ignored_patterns_empty() -> None:
    assert StandaloneAdapter().get_ignored_patterns() == set()


def test_standalone_get_nav_paths_empty() -> None:
    assert StandaloneAdapter().get_nav_paths() == frozenset()


@pytest.mark.parametrize("filename", ["guide.it.md", "page.fr.md", "index.pt.md"])
def test_standalone_suffix_files_not_treated_as_translations(filename: str) -> None:
    locale = filename.rsplit(".", 2)[1]
    assert not StandaloneAdapter().is_locale_dir(locale)
    assert StandaloneAdapter().get_ignored_patterns() == set()


def test_get_adapter_no_config_no_locales_returns_standalone(tmp_path: Path) -> None:
    """Test C: no config files + no locales → StandaloneAdapter."""
    adapter = get_adapter(BuildContext(), tmp_path / "docs", tmp_path)
    assert isinstance(adapter, StandaloneAdapter)


def test_get_adapter_mkdocs_engine_with_config(tmp_path: Path) -> None:
    """Test A: engine='mkdocs' + mkdocs.yml → MkDocsAdapter."""
    _mkdocs(tmp_path)
    context = BuildContext(engine="mkdocs", locales=["it"])
    adapter = get_adapter(context, tmp_path / "docs", tmp_path)
    assert isinstance(adapter, MkDocsAdapter)
    assert not isinstance(adapter, ZensicalAdapter)


def test_get_adapter_zensical_engine_with_config(tmp_path: Path) -> None:
    """Test B: engine='zensical' + zensical.toml → ZensicalAdapter."""
    _zensical(tmp_path)
    context = BuildContext(engine="zensical", locales=["it"])
    adapter = get_adapter(context, tmp_path / "docs", tmp_path)
    assert isinstance(adapter, ZensicalAdapter)
    assert isinstance(adapter, BaseAdapter)


def test_get_adapter_locales_no_config_uses_engine(tmp_path: Path) -> None:
    """Explicit locales declared in .zenzic.toml → routes by engine without doc_config."""
    _mkdocs(tmp_path)
    assert isinstance(
        get_adapter(BuildContext(engine="mkdocs", locales=["it"]), tmp_path / "docs", tmp_path),
        MkDocsAdapter,
    )


def test_discover_engine_empty_dir_returns_standalone(tmp_path: Path) -> None:
    """No engine config files → 'standalone' (universal Privacy Gate)."""
    assert discover_engine(tmp_path) == "standalone"


def test_discover_engine_mkdocs_yml(tmp_path: Path) -> None:
    """mkdocs.yml present → 'mkdocs'."""
    _mkdocs(tmp_path)
    assert discover_engine(tmp_path) == "mkdocs"


def test_discover_engine_zensical_toml(tmp_path: Path) -> None:
    """zensical.toml present → 'zensical' (highest priority)."""
    _zensical(tmp_path)
    assert discover_engine(tmp_path) == "zensical"


def test_discover_engine_zensical_wins_over_mkdocs(tmp_path: Path) -> None:
    """Priority: zensical.toml beats mkdocs.yml when both present."""
    _zensical(tmp_path)
    _mkdocs(tmp_path)
    assert discover_engine(tmp_path) == "zensical"


def test_get_adapter_auto_no_config_returns_standalone(tmp_path: Path) -> None:
    """engine='auto' + no config files → StandaloneAdapter + mutates context.engine."""
    ctx = BuildContext()
    assert ctx.engine == "auto"
    adapter = get_adapter(ctx, tmp_path / "docs", tmp_path)
    assert isinstance(adapter, StandaloneAdapter)
    assert ctx.engine == "standalone"


def test_get_adapter_auto_mkdocs_yml_routes_to_mkdocs(tmp_path: Path) -> None:
    """engine='auto' + mkdocs.yml → MkDocsAdapter + context.engine mutated."""
    _mkdocs(tmp_path)
    (tmp_path / "docs").mkdir()
    ctx = BuildContext()
    adapter = get_adapter(ctx, tmp_path / "docs", tmp_path)
    assert isinstance(adapter, MkDocsAdapter)
    assert ctx.engine == "mkdocs"


def test_get_adapter_auto_mutates_engine_for_cache_reuse(tmp_path: Path) -> None:
    """After auto-detection, second call with a different context uses the cache."""
    _mkdocs(tmp_path)
    (tmp_path / "docs").mkdir()
    ctx1 = BuildContext()
    ctx2 = BuildContext()
    adapter1 = get_adapter(ctx1, tmp_path / "docs", tmp_path)
    adapter2 = get_adapter(ctx2, tmp_path / "docs", tmp_path)
    assert adapter1 is adapter2
    assert ctx1.engine == "mkdocs"
    assert ctx2.engine == "mkdocs"


def test_zensical_engine_without_zensical_toml_raises(tmp_path: Path) -> None:
    """Identity Violation: engine='zensical' + no configuration → ConfigurationError."""
    context = BuildContext(engine="zensical")
    with pytest.raises(ConfigurationError, match="no configuration file was found"):
        get_adapter(context, tmp_path / "docs", tmp_path)


def test_zensical_engine_mkdocs_yml_bridge_works(tmp_path: Path) -> None:
    """Bridge path: engine='zensical' + mkdocs.yml resolves to ZensicalAdapter."""
    _mkdocs(tmp_path)
    context = BuildContext(engine="zensical")
    adapter = get_adapter(context, tmp_path / "docs", tmp_path)
    assert adapter.has_engine_config() is True
    assert isinstance(adapter, ZensicalAdapter)


def test_zensical_engine_with_zensical_toml_does_not_raise(tmp_path: Path) -> None:
    """No error when both engine='zensical' and zensical.toml are present."""
    _zensical(tmp_path)
    adapter = get_adapter(BuildContext(engine="zensical"), tmp_path / "docs", tmp_path)
    assert isinstance(adapter, ZensicalAdapter)


def test_zensical_adapter_nav_paths_from_toml(tmp_path: Path) -> None:
    """ZensicalAdapter.get_nav_paths reads [project].nav from zensical.toml."""
    _zensical(tmp_path, nav=["index.md", "guide/start.md", "about.md"])
    adapter = get_adapter(BuildContext(engine="zensical"), tmp_path / "docs", tmp_path)
    assert isinstance(adapter, ZensicalAdapter)
    assert adapter.get_nav_paths() == frozenset({"index.md", "guide/start.md", "about.md"})


def test_find_orphans_no_config_returns_empty(tmp_path: Path) -> None:
    """Standalone repo (no mkdocs.yml, no zensical.toml) → no orphan check → []."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home")
    (docs / "orphan.md").write_text("# Orphan")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    assert _run_find_orphans(tmp_path, config, mgr) == []


def test_find_orphans_zensical_repo(tmp_path: Path) -> None:
    """Zensical repo with zensical.toml → orphan check uses TOML nav."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home")
    (docs / "orphan.md").write_text("# Unlisted")
    _zensical(tmp_path, nav=["index.md"])
    config = ZenzicConfig.model_validate(
        {"docs_dir": "docs", "build_context": {"engine": "zensical"}}
    )
    mgr = make_mgr(config, repo_root=tmp_path)
    orphans = _run_find_orphans(tmp_path, config, mgr)
    assert Path("orphan.md") in orphans
    assert Path("index.md") not in orphans


def test_find_orphans_standalone_suffix_file_appears_as_orphan(tmp_path: Path) -> None:
    """In standalone mode, guide.it.md is an ordinary page — not silently excluded."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: T\nnav:\n  - Home: index.md\n")
    (docs / "index.md").write_text("# Home")
    (docs / "guide.it.md").write_text("# Guide IT")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    orphans = _run_find_orphans(tmp_path, config, mgr)
    assert Path("guide.it.md") in orphans
