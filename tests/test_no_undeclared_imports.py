# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The CLI entry point must not import a package that is not declared.

`import click` was added to main.py for the flag-placement hint. click is a
transitive dependency of Typer, so it was present on the development machine
and every test passed. It is not declared in pyproject.toml, so in an
environment that resolved without it `zenzic --version` died with
ModuleNotFoundError before printing anything -- which the VS Code extension
reads as "Version Error" and refuses to start the language server, so the user
sees no diagnostics at all.

Nothing caught it: the import is valid, the tests pass, and the failure only
appears where the transitive dependency happens to be absent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]

# Modules the interpreter always provides, plus the package itself.
STDLIB_OK = {"zenzic"}


def _declared() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = set()
    for spec in data["project"].get("dependencies", []):
        names.add(spec.split(">=")[0].split("==")[0].split("[")[0].split("~")[0].strip().lower())
    return names


def _module_level_imports(path: Path) -> set[str]:
    """Top-level imports only: a function-local import is a deliberate deferral."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_cli_entry_point_imports_only_declared_packages() -> None:
    import sys

    declared = _declared()
    imported = _module_level_imports(ROOT / "src" / "zenzic" / "main.py")
    third_party = {m for m in imported if m not in STDLIB_OK and m not in sys.stdlib_module_names}
    undeclared = sorted(third_party - declared)
    assert not undeclared, (
        f"main.py imports {undeclared} at module level, and pyproject.toml does not "
        f"declare them. `zenzic --version` dies before printing anything wherever the "
        f"transitive dependency is absent."
    )


def test_the_check_can_actually_find_something() -> None:
    """Positive control: a fabricated undeclared import must be detected."""
    import sys

    declared = _declared()
    fabricated = {"definitely_not_a_declared_package"}
    third_party = {m for m in fabricated if m not in sys.stdlib_module_names}
    assert sorted(third_party - declared) == ["definitely_not_a_declared_package"]
