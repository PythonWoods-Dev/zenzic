# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The monorepo include matcher recognised one spelling out of the ones people write.

``mkdocs-monorepo-plugin``'s documented nav syntax puts the directive in the
*value* of a titled entry::

    nav:
      - Home: index.md
      - Sub: '!include ./sub/mkdocs.yml'

``_iter_monorepo_include_paths`` matched a bare string item (``- '!include ./sub'``)
and a dict whose *key* is ``!include``, and looked no further. The canonical form
above is a dict whose key is the section title, so it matched nothing and the
sub-project's ``docs_dir`` was never discovered.

That is a security reach gap, not a nav-rendering nicety: the discovered roots
feed ``iter_security_scan_sources``, so a live credential in an included
sub-project scanned clean — ``exit 0`` — while the identical repository written
with the bare-string spelling exited 2.

Includes are now collected from nav values as well as keys, and the walk
recurses into nested sections, since nav is a tree and an include can sit at any
depth of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.core.adapters._mkdocs import _iter_monorepo_include_paths
from zenzic.main import app


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _build(root: Path, nav_entry: str) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "sub" / "docs").mkdir(parents=True, exist_ok=True)
    (root / "mkdocs.yml").write_text(
        "site_name: Parent\nplugins:\n  - monorepo\nnav:\n  - Home: index.md\n" + nav_entry + "\n",
        encoding="utf-8",
    )
    (root / "docs" / "index.md").write_text(f"# Parent\n\n{_PROSE}\n", encoding="utf-8")
    (root / "sub" / "mkdocs.yml").write_text("site_name: Sub\n", encoding="utf-8")
    (root / "sub" / "docs" / "index.md").write_text(
        f'# Sub\n\n{_PROSE}\n\n    aws_key = "{_SECRET}"\n', encoding="utf-8"
    )


_NAV_SPELLINGS = [
    pytest.param("  - '!include ./sub'", id="bare-string"),
    pytest.param("  - Sub: '!include ./sub'", id="titled-directory"),
    pytest.param("  - Sub: '!include ./sub/mkdocs.yml'", id="titled-explicit-file"),
    pytest.param(
        "  - Section:\n    - Sub: '!include ./sub/mkdocs.yml'", id="nested-under-a-section"
    ),
]


@pytest.mark.parametrize("nav_entry", _NAV_SPELLINGS)
def test_a_credential_in_an_included_project_is_found(
    tmp_path: Path, nav_entry: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build(tmp_path, nav_entry)
    monkeypatch.chdir(tmp_path)
    code = CliRunner().invoke(app, ["check", "all", "--quiet"], catch_exceptions=False).exit_code
    assert code == 2, f"the credential in ./sub/docs was not reached with nav entry {nav_entry!r}"


class TestIncludeExtraction:
    """Unit level, so a failure names the spelling rather than an exit code."""

    @pytest.mark.parametrize(
        ("nav", "expected"),
        [
            ([{"Home": "index.md"}, "!include ./sub"], ["./sub"]),
            ([{"Sub": "!include ./sub"}], ["./sub"]),
            ([{"Sub": "!include ./sub/mkdocs.yml"}], ["./sub/mkdocs.yml"]),
            ([{"Section": [{"Sub": "!include ./sub"}]}], ["./sub"]),
            ([{"!include": "./sub"}], ["./sub"]),
        ],
    )
    def test_every_documented_spelling_yields_the_path(
        self, nav: list[object], expected: list[str]
    ) -> None:
        assert _iter_monorepo_include_paths({"nav": nav}) == expected

    @pytest.mark.parametrize(
        "nav",
        [
            [{"Home": "index.md"}],
            [{"Guide": "guide/index.md"}, "reference.md"],
            [{"Section": [{"Page": "a.md"}, {"Other": "b.md"}]}],
        ],
    )
    def test_ordinary_nav_yields_nothing(self, nav: list[object]) -> None:
        """A matcher that over-reaches would pull real pages in as configs."""
        assert _iter_monorepo_include_paths({"nav": nav}) == []
