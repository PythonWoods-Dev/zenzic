# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for smart build engine auto-discovery."""

from pathlib import Path

from zenzic.core.adapters._factory import discover_engine


def test_discover_engine_pure_mkdocs(tmp_path: Path) -> None:
    mkdocs_file = tmp_path / "mkdocs.yml"
    mkdocs_file.write_text(
        "site_name: My MkDocs Site\ntheme:\n  name: material\nnav:\n  - Home: index.md\n",
        encoding="utf-8",
    )
    assert discover_engine(tmp_path) == "mkdocs"


def test_discover_engine_inline_zensical_theme(tmp_path: Path) -> None:
    mkdocs_file = tmp_path / "mkdocs.yml"
    mkdocs_file.write_text(
        "site_name: My Zensical Site\ntheme: zensical\nnav:\n  - Home: index.md\n",
        encoding="utf-8",
    )
    assert discover_engine(tmp_path) == "zensical"


def test_discover_engine_multiline_zensical_theme(tmp_path: Path) -> None:
    mkdocs_file = tmp_path / "mkdocs.yml"
    mkdocs_file.write_text(
        "site_name: My Zensical Site\n"
        "theme:\n"
        "  name: zensical\n"
        "  palette:\n"
        "    primary: indigo\n"
        "nav:\n"
        "  - Home: index.md\n",
        encoding="utf-8",
    )
    assert discover_engine(tmp_path) == "zensical"


def test_discover_engine_zensical_quoted_theme(tmp_path: Path) -> None:
    mkdocs_file = tmp_path / "mkdocs.yaml"
    mkdocs_file.write_text(
        'site_name: My Zensical Site\ntheme:\n  name: "zensical"\n',
        encoding="utf-8",
    )
    assert discover_engine(tmp_path) == "zensical"


def test_discover_engine_false_positive_guard(tmp_path: Path) -> None:
    """Ensure mention of 'zensical' in comments or nav does NOT trigger zensical engine."""
    mkdocs_file = tmp_path / "mkdocs.yml"
    mkdocs_file.write_text(
        "# Note: We are migrating away from zensical to mkdocs-material\n"
        "site_name: My MkDocs Site\n"
        "theme:\n"
        "  name: material\n"
        "nav:\n"
        "  - Zensical Guide: docs/zensical_guide.md\n"
        "plugins:\n"
        "  - search\n",
        encoding="utf-8",
    )
    assert discover_engine(tmp_path) == "mkdocs"


def test_discover_engine_zensical_toml(tmp_path: Path) -> None:
    zensical_file = tmp_path / "zensical.toml"
    zensical_file.write_text(
        '[project]\nsite_name = "Zensical Native"\n',
        encoding="utf-8",
    )
    assert discover_engine(tmp_path) == "zensical"


def test_discover_engine_prebuilt_vsm(tmp_path: Path) -> None:
    vsm_file = tmp_path / ".zenzic-vsm.json"
    vsm_file.write_text("{}", encoding="utf-8")
    assert discover_engine(tmp_path) == "prebuilt"


def test_discover_engine_standalone_fallback(tmp_path: Path) -> None:
    assert discover_engine(tmp_path) == "standalone"
