# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the permissive MkDocs YAML loader and config discovery
helpers in zenzic.core.adapters._mkdocs_config.

Covers the !ENV / !relative / unknown-tag / !!python constructor branches
(scalar, sequence, mapping) and the file-discovery/error-tolerance paths,
none of which had direct coverage before.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from zenzic.core.adapters._mkdocs_config import (
    _PermissiveYamlLoader,
    find_mkdocs_config_file,
    load_mkdocs_config,
    load_mkdocs_config_file,
)


def _load(yaml_text: str) -> object:
    return yaml.load(yaml_text, Loader=_PermissiveYamlLoader)  # noqa: S506


# ── !ENV tag ────────────────────────────────────────────────────────────────


def test_env_tag_scalar_reads_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv("ZENZIC_TEST_VAR", "hello")
    assert _load("key: !ENV ZENZIC_TEST_VAR") == {"key": "hello"}


def test_env_tag_empty_sequence_returns_none() -> None:
    assert _load("key: !ENV []") == {"key": None}


def test_env_tag_single_item_sequence_reads_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv("ZENZIC_TEST_VAR", "world")
    assert _load("key: !ENV [ZENZIC_TEST_VAR]") == {"key": "world"}


def test_env_tag_multi_key_sequence_uses_first_set_variable(monkeypatch) -> None:
    monkeypatch.delenv("ZENZIC_TEST_FIRST", raising=False)
    monkeypatch.setenv("ZENZIC_TEST_SECOND", "found")
    result = _load("key: !ENV [ZENZIC_TEST_FIRST, ZENZIC_TEST_SECOND, fallback]")
    assert result == {"key": "found"}


def test_env_tag_multi_key_sequence_falls_back_to_default_when_none_set(monkeypatch) -> None:
    monkeypatch.delenv("ZENZIC_TEST_FIRST", raising=False)
    monkeypatch.delenv("ZENZIC_TEST_SECOND", raising=False)
    result = _load("key: !ENV [ZENZIC_TEST_FIRST, ZENZIC_TEST_SECOND, fallback]")
    assert result == {"key": "fallback"}


def test_env_tag_multi_key_sequence_skips_non_string_keys(monkeypatch) -> None:
    monkeypatch.setenv("ZENZIC_TEST_SECOND", "found")
    result = _load("key: !ENV [1, ZENZIC_TEST_SECOND, fallback]")
    assert result == {"key": "found"}


def test_env_tag_mapping_form_is_preserved_as_dict() -> None:
    result = _load("key: !ENV {a: 1, b: 2}")
    assert result == {"key": {"a": 1, "b": 2}}


# ── unknown tags (best-effort passthrough) ──────────────────────────────────


def test_unknown_scalar_tag_is_preserved() -> None:
    assert _load("key: !SomePlugin value") == {"key": "value"}


def test_unknown_sequence_tag_is_preserved() -> None:
    assert _load("key: !SomePlugin [a, b]") == {"key": ["a", "b"]}


def test_unknown_mapping_tag_is_preserved() -> None:
    assert _load("key: !SomePlugin {a: 1}") == {"key": {"a": 1}}


# ── !relative tag ────────────────────────────────────────────────────────────


def test_relative_tag_scalar_is_preserved() -> None:
    assert _load("key: !relative path/to/file") == {"key": "path/to/file"}


def test_relative_tag_sequence_is_preserved() -> None:
    assert _load("key: !relative [a, b]") == {"key": ["a", "b"]}


def test_relative_tag_mapping_is_preserved() -> None:
    assert _load("key: !relative {a: 1}") == {"key": {"a": 1}}


# ── !!python/* tags (must never execute, only preserve as data) ────────────


def test_python_tag_scalar_with_value_is_preserved() -> None:
    assert _load("key: !!python/name:builtins.dict foo") == {"key": "foo"}


def test_python_tag_scalar_with_no_trailing_value_is_empty_string() -> None:
    result = _load("key: !!python/name:builtins.dict")
    assert result == {"key": ""}


def test_python_tag_sequence_is_preserved() -> None:
    result = _load("key: !!python/tuple [a, b]")
    assert result == {"key": ["a", "b"]}


def test_python_tag_mapping_is_preserved() -> None:
    result = _load("key: !!python/object:foo.Bar {a: 1}")
    assert result == {"key": {"a": 1}}


# ── file discovery / load helpers ───────────────────────────────────────────


def test_find_mkdocs_config_file_returns_none_when_absent(tmp_path: Path) -> None:
    assert find_mkdocs_config_file(tmp_path) is None


def test_find_mkdocs_config_file_returns_path_when_present(tmp_path: Path) -> None:
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")
    assert find_mkdocs_config_file(tmp_path) == tmp_path / "mkdocs.yml"


def test_load_mkdocs_config_file_returns_empty_dict_when_not_a_file(tmp_path: Path) -> None:
    assert load_mkdocs_config_file(tmp_path / "missing.yml") == {}


def test_load_mkdocs_config_file_returns_empty_dict_on_malformed_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "mkdocs.yml"
    bad.write_text("site_name: [unclosed", encoding="utf-8")
    assert load_mkdocs_config_file(bad) == {}


def test_load_mkdocs_config_file_parses_valid_yaml(tmp_path: Path) -> None:
    good = tmp_path / "mkdocs.yml"
    good.write_text("site_name: Test\n", encoding="utf-8")
    assert load_mkdocs_config_file(good) == {"site_name": "Test"}


def test_load_mkdocs_config_returns_empty_dict_when_no_config_file(tmp_path: Path) -> None:
    assert load_mkdocs_config(tmp_path) == {}


def test_load_mkdocs_config_loads_from_repo_root(tmp_path: Path) -> None:
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")
    assert load_mkdocs_config(tmp_path) == {"site_name": "Test"}
