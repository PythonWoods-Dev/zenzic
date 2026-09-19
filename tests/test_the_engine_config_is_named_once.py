# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Which file is this project's MkDocs configuration, answered once.

Eight sites answered it and they disagreed. `discover_engine` probed
`mkdocs.yml` **and** `mkdocs.yaml`; `find_mkdocs_config_file` probed only the
first. The consequence was reachable, not theoretical: on a project using
`mkdocs.yaml`, detection returned `"mkdocs"`, `MkDocsAdapter` was built, and its
configuration load returned `{}` — no `docs_dir`, no `nav`, no
`markdown_extensions`, no `site_dir`. Every nav-contract, orphan and
container-vocabulary finding was then computed against an empty configuration
that the detection step had already proved was not empty.

`MKDOCS_CONFIG_NAMES` is the declaration now, and these pin that the sites read
it rather than keeping their own copy.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from zenzic.core.adapters._mkdocs_config import MKDOCS_CONFIG_NAMES, find_mkdocs_config_file


_SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"


@pytest.fixture
def mkdocs_yaml_project(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yaml").write_text(
        "site_name: Probe\nnav:\n  - Home: index.md\n", encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    return tmp_path


def test_the_adapter_is_not_built_on_an_empty_configuration(mkdocs_yaml_project: Path) -> None:
    """The defect, stated as the user meets it."""
    from zenzic.core.adapters import get_adapter
    from zenzic.models.config import ZenzicConfig

    config, _ = ZenzicConfig.load(mkdocs_yaml_project)
    docs_root = mkdocs_yaml_project / config.docs_dir
    adapter = get_adapter(config.build_context, docs_root, mkdocs_yaml_project)

    assert type(adapter).__name__ == "MkDocsAdapter"
    assert adapter.has_engine_config() is True
    assert len(adapter.get_nav_paths()) == 1, (
        "the adapter was built because detection found mkdocs.yaml, and then read "
        "an empty configuration — the nav it was built to honour is missing"
    )


def test_both_names_resolve_and_a_directory_does_not(tmp_path: Path) -> None:
    """`is_file()`, not `exists()`: a directory named `mkdocs.yml` is not a
    configuration file, and the probe in `discover_engine` always said so while
    this one did not."""
    for name in MKDOCS_CONFIG_NAMES:
        root = tmp_path / name.replace(".", "_")
        root.mkdir()
        (root / name).write_text("site_name: x\n", encoding="utf-8")
        assert find_mkdocs_config_file(root) == root / name

    as_directory = tmp_path / "dir"
    as_directory.mkdir()
    (as_directory / "mkdocs.yml").mkdir()
    assert find_mkdocs_config_file(as_directory) is None


def test_no_site_keeps_its_own_copy_of_the_names() -> None:
    """A literal `"mkdocs.yaml"` outside the declaration is a second answer.

    `"mkdocs.yml"` alone is allowed where it is prose — a substitution hint, an
    error message — so the check keys on the *pair* appearing as literals in one
    expression, which is what a private copy of the set looks like.
    """
    offenders: list[str] = []
    for py in sorted(_SRC.rglob("*.py")):
        if py.name == "_mkdocs_config.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Tuple | ast.Set | ast.List):
                continue
            values = {
                e.value
                for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
            if {"mkdocs.yml", "mkdocs.yaml"} <= values:
                rel = py.relative_to(_SRC.parent.parent).as_posix()
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "a second copy of the MkDocs configuration filenames:\n  "
        + "\n  ".join(offenders)
        + "\nRead MKDOCS_CONFIG_NAMES instead."
    )


def test_the_detector_would_find_a_copy() -> None:
    """A zero-result sweep is not evidence until the instrument has been shown
    to find something."""
    module = ast.parse('NAMES = ("mkdocs.yml", "mkdocs.yaml")\n')
    tuples = [n for n in ast.walk(module) if isinstance(n, ast.Tuple)]
    values = {e.value for e in tuples[0].elts if isinstance(e, ast.Constant)}

    assert {"mkdocs.yml", "mkdocs.yaml"} <= values
