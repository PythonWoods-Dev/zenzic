# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``scripts/check_third_party_declarations.py`` finds a planted case and passes the real tree.

The positive controls are the three shapes that shipped before 9da4e36: a
minified bundle whose banner names another licence under a PythonWoods sidecar,
a font covered by a PythonWoods directory glob, and a schema whose ``$id`` is
another organisation's, also under a PythonWoods sidecar. Run against the tree
of 9da4e36^ the script reports exactly the twelve files that commit corrected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_third_party_declarations import (  # noqa: E402
    declared_own,
    problems_in,
    self_test,
)


# REUSE-IgnoreStart -- the planted declarations below are fixtures, not this file's.
OWN = "SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>\n\nSPDX-License-Identifier: Apache-2.0\n"


def _project(root: Path, toml: str = "") -> Path:
    (root / "LICENSES").mkdir()
    (root / "LICENSES" / "Apache-2.0.txt").write_text("Apache\n", encoding="utf-8")
    (root / "LICENSES" / "MIT.txt").write_text("MIT\n", encoding="utf-8")
    (root / "LICENSES" / "OFL-1.1.txt").write_text("OFL\n", encoding="utf-8")
    (root / "REUSE.toml").write_text("version = 1\n" + toml, encoding="utf-8")
    return root


def _flagged(root: Path) -> set[str]:
    return {p.split(":", 1)[0] for p in problems_in(root)}


def test_the_instrument_passes_its_own_self_test() -> None:
    assert self_test() == []


def test_the_repository_declares_no_third_party_file_as_its_own() -> None:
    assert problems_in(ROOT) == []


def test_a_banner_under_a_project_sidecar_is_found(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "bundle.min.css").write_text(
        "/*! somecss v4.3.1 | MIT License | x */\n.a{}", encoding="utf-8"
    )
    (root / "bundle.min.css.license").write_text(OWN, encoding="utf-8")
    assert _flagged(root) == {"bundle.min.css"}


def test_a_font_under_a_project_glob_is_found(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        '[[annotations]]\npath = "fonts/**"\nprecedence = "aggregate"\n'
        'SPDX-FileCopyrightText = "2026 PythonWoods <dev@pythonwoods.dev>"\n'
        'SPDX-License-Identifier = "Apache-2.0"\n',
    )
    (root / "fonts").mkdir()
    (root / "fonts" / "face.woff2").write_bytes(b"wOF2\0\0\0\0")
    assert _flagged(root) == {"fonts/face.woff2"}


def test_a_font_under_its_real_holder_is_not_found(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        '[[annotations]]\npath = "fonts/**"\nprecedence = "override"\n'
        'SPDX-FileCopyrightText = "2011 The Face Project Authors"\n'
        'SPDX-License-Identifier = "OFL-1.1"\n',
    )
    (root / "fonts").mkdir()
    (root / "fonts" / "face.woff2").write_bytes(b"wOF2\0\0\0\0")
    assert _flagged(root) == set()


def test_a_foreign_schema_id_is_found_and_the_project_s_own_is_not(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "theirs.json").write_text(
        '{"$id": "https://example.org/schema.json"}\n', encoding="utf-8"
    )
    (root / "ours.json").write_text(
        '{"$id": "https://zenzic.dev/schemas/x.json"}\n', encoding="utf-8"
    )
    for name in ("theirs.json", "ours.json"):
        (root / f"{name}.license").write_text(OWN, encoding="utf-8")
    assert _flagged(root) == {"theirs.json"}


def test_a_plain_copyright_line_under_the_project_licence_is_found(tmp_path: Path) -> None:
    # reuse takes the holder from the content and the licence from the glob, so
    # the file is declared under Apache-2.0 with no SPDX holder at all.
    root = _project(
        tmp_path,
        '[[annotations]]\npath = "vendor/**"\n'
        'SPDX-FileCopyrightText = "2026 PythonWoods <dev@pythonwoods.dev>"\n'
        'SPDX-License-Identifier = "Apache-2.0"\n',
    )
    (root / "vendor").mkdir()
    (root / "vendor" / "lib.js").write_text(
        "// Copyright (c) 2019 Jane Doe\nx()\n", encoding="utf-8"
    )
    assert _flagged(root) == {"vendor/lib.js"}


def test_prose_about_copyright_is_not_a_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "theme.css").write_text(
        "/* SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> */\n"
        "/* SPDX-License-Identifier: Apache-2.0 */\n/* Copyright notices live in NOTICE. */\n",
        encoding="utf-8",
    )
    assert _flagged(root) == set()


@pytest.mark.parametrize(
    ("holders", "licences", "own"),
    [
        (["PythonWoods <dev@pythonwoods.dev>"], {"Apache-2.0"}, True),
        (
            ["Tailwind Labs, Inc.", "PythonWoods <dev@pythonwoods.dev>"],
            {"MIT AND Apache-2.0"},
            False,
        ),
        ([], {"Apache-2.0"}, True),
        ([], {"MIT"}, False),
        ([], set(), False),
    ],
)
def test_declared_own(holders: list[str], licences: set[str], own: bool) -> None:
    assert declared_own(holders, licences) is own


def test_a_banner_quoted_in_prose_is_not_a_marker(tmp_path: Path) -> None:
    # The licensing page and this check's own docstring quote both forms.
    root = _project(tmp_path)
    (root / "page.md").write_text(
        "<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->\n"
        "<!-- SPDX-License-Identifier: Apache-2.0 -->\n"
        "A bundle keeps a `/*! x v1 | MIT License */` banner, and a script an `@license` tag.\n",
        encoding="utf-8",
    )
    assert _flagged(root) == set()


# REUSE-IgnoreEnd
