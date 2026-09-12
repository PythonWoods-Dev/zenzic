# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PrebuiltVSMAdapter (ADR-080 Bridge Architecture ingestion).

No prior coverage existed for this adapter at all — these cover the
.zenzic-vsm.json presence/absence branches, the malformed-JSON error path,
and every get_route_info() lookup branch (found-with-full-data,
found-with-partial-data fallback, not-found-with-config, not-found-without-config).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zenzic.core.adapters._prebuilt import PrebuiltVSMAdapter
from zenzic.core.exceptions import ZenzicConfigError
from zenzic.models.config import BuildContext


def test_no_vsm_file_means_no_engine_config(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()

    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)

    assert adapter.has_engine_config() is False
    assert adapter._routes == {}


def test_valid_vsm_file_is_loaded_and_marks_engine_config_present(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    routes = {"guide/install.md": {"url": "/guide/install/", "status": "REACHABLE"}}
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(routes), encoding="utf-8")

    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)

    assert adapter.has_engine_config() is True
    assert adapter._routes == routes


def test_malformed_vsm_file_raises_zenzic_config_error(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (tmp_path / ".zenzic-vsm.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ZenzicConfigError, match=r"Failed to parse"):
        PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)


def test_repo_root_defaults_to_docs_root_parent(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    routes = {"a.md": {"url": "/a/"}}
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(routes), encoding="utf-8")

    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=None)

    assert adapter.has_engine_config() is True


def test_from_repo_classmethod_delegates_to_constructor(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()

    adapter = PrebuiltVSMAdapter.from_repo(BuildContext(), docs_root, tmp_path)

    assert isinstance(adapter, PrebuiltVSMAdapter)
    assert adapter.has_engine_config() is False


def test_get_route_info_uses_full_data_when_present(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    routes = {
        "guide/install.md": {
            "url": "/guide/install/",
            "status": "REACHABLE",
            "slug": "install-guide",
        }
    }
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(routes), encoding="utf-8")
    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)

    info = adapter.get_route_info(Path("guide/install.md"))

    assert info.canonical_url == "/guide/install/"
    assert info.status == "REACHABLE"
    assert info.slug == "install-guide"


def test_get_route_info_falls_back_to_map_url_and_defaults_when_data_partial(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    routes: dict[str, dict[str, str]] = {"guide/install.md": {}}
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(routes), encoding="utf-8")
    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)

    info = adapter.get_route_info(Path("guide/install.md"))

    assert info.canonical_url == "/guide/install/"
    assert info.status == "REACHABLE"
    assert info.slug is None


def test_get_route_info_unlisted_path_is_ignored_when_vsm_config_present(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    routes = {"guide/install.md": {"url": "/guide/install/"}}
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(routes), encoding="utf-8")
    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)

    info = adapter.get_route_info(Path("guide/uninstall.md"))

    assert info.status == "IGNORED"
    assert info.canonical_url == "/guide/uninstall/"


def test_get_route_info_unlisted_path_is_reachable_without_vsm_config(
    tmp_path: Path,
) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    adapter = PrebuiltVSMAdapter(BuildContext(), docs_root, repo_root=tmp_path)

    info = adapter.get_route_info(Path("guide/install.md"))

    assert info.status == "REACHABLE"
    assert info.canonical_url == "/guide/install/"
