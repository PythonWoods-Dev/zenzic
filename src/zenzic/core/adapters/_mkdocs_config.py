# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Shared MkDocs config discovery and permissive YAML loading utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


class _PermissiveYamlLoader(yaml.SafeLoader):
    """SafeLoader that tolerates unknown tags used by MkDocs plugins."""


def _construct_unknown_tag(
    loader: _PermissiveYamlLoader,
    tag_suffix: str,
    node: ScalarNode | SequenceNode | MappingNode,
) -> Any:
    """Best-effort constructor for unknown YAML tags."""
    if isinstance(node, ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


def _construct_env_tag(
    loader: _PermissiveYamlLoader,
    node: ScalarNode | SequenceNode | MappingNode,
) -> Any:
    """Resolve MkDocs !ENV tags with fallback semantics."""
    if isinstance(node, ScalarNode):
        key = loader.construct_scalar(node)
        return os.getenv(key)

    if isinstance(node, SequenceNode):
        values = loader.construct_sequence(node)
        if not values:
            return None
        if len(values) == 1:
            return os.getenv(str(values[0]))

        *keys, default = values
        for key in keys:
            if not isinstance(key, str):
                continue
            val = os.getenv(key)
            if val is not None:
                return val
        return default

    return loader.construct_mapping(node)


def _construct_relative_tag(
    loader: _PermissiveYamlLoader,
    node: ScalarNode | SequenceNode | MappingNode,
) -> Any:
    """Preserve !relative payload as plain data for static analysis."""
    if isinstance(node, ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


def _construct_python_tag(
    loader: _PermissiveYamlLoader,
    tag_suffix: str,
    node: ScalarNode | SequenceNode | MappingNode,
) -> Any:
    """Preserve !!python/* payload as plain data without execution."""
    if isinstance(node, ScalarNode):
        value = loader.construct_scalar(node)
        return value if value is not None else tag_suffix
    if isinstance(node, SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_PermissiveYamlLoader.add_constructor("!ENV", _construct_env_tag)
_PermissiveYamlLoader.add_constructor("!relative", _construct_relative_tag)
_PermissiveYamlLoader.add_multi_constructor("!", _construct_unknown_tag)  # type: ignore[no-untyped-call]
_PermissiveYamlLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/",
    _construct_python_tag,
)  # type: ignore[no-untyped-call]


#: The filenames MkDocs itself accepts for its configuration, in the order it
#: looks for them.
#:
#: Declared once because the answer was split across eight sites: ``discover_engine``
#: probed both, this function probed only ``mkdocs.yml``, and the consequence was
#: reachable. On a project using ``mkdocs.yaml``, discovery returned ``"mkdocs"``,
#: ``MkDocsAdapter`` was built, and its configuration load returned ``{}`` — **no
#: `docs_dir`, no `nav`, no `markdown_extensions`, no `site_dir`** — so every
#: nav-contract, orphan and container-vocabulary finding was computed against an
#: empty configuration that the detection step had already proved was not empty.
MKDOCS_CONFIG_NAMES: Final[tuple[str, ...]] = ("mkdocs.yml", "mkdocs.yaml")


def find_mkdocs_config_file(repo_root: Path) -> Path | None:
    """Return the MkDocs config path, or ``None`` if absent.

    Both names, and ``is_file()`` rather than ``exists()``: a directory called
    ``mkdocs.yml`` is not a configuration file, and the probe in
    ``discover_engine`` has always said so while this one did not.
    """
    for name in MKDOCS_CONFIG_NAMES:
        candidate = repo_root / name
        if candidate.is_file():
            return candidate
    return None


def load_mkdocs_config_file(config_file: Path) -> dict[str, Any]:
    """Load and parse a specific MkDocs config file path."""
    if not config_file.is_file():
        return {}
    try:
        with config_file.open(encoding="utf-8") as f:
            return yaml.load(f, Loader=_PermissiveYamlLoader) or {}  # noqa: S506
    except (OSError, yaml.YAMLError):
        return {}


def load_mkdocs_config(repo_root: Path) -> dict[str, Any]:
    """Load and parse ``mkdocs.yml``, returning ``{}`` on failure."""
    config_file = find_mkdocs_config_file(repo_root)
    if config_file is None:
        return {}
    return load_mkdocs_config_file(config_file)
