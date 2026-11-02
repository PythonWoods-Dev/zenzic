# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every self-hosted font carries its upstream copyright and the OFL in its own name table.

The ten `docs/assets/fonts/*.woff2` files served by the documentation site are
Roboto and Roboto Mono subsets. The copies first committed (fc10edb) came from
an unrecorded source and had name ID 13 (the licence description) stripped: the
file said who held it (name ID 0) but not under which licence, so the OFL's
condition that each copy carry the licence was met only by documents next to
the file, never by the file a browser downloads.

They are now produced by `scripts/regenerate_fonts.py` from the pinned upstream
releases, keeping name IDs 0, 13 and 14 as upstream wrote them. This test reads
each file's name table and fails when any of the three is missing or differs,
and when the set of files is not the ten the stylesheet loads (a zero-file
directory would otherwise pass every assertion).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.ttLib import TTFont


# fontTools and brotli (WOFF2) come from the test group's `fonttools[woff]`: imported, not
# skipped, so an environment without them fails here rather than passing silently.

FONTS = Path(__file__).resolve().parent.parent / "docs" / "assets" / "fonts"

ROBOTO = "Copyright 2011 The Roboto Project Authors (https://github.com/googlefonts/roboto-classic)"
ROBOTO_MONO = (
    "Copyright 2015 The Roboto Mono Project Authors (https://github.com/googlefonts/robotomono)"
)
OFL_DESCRIPTION = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: https://openfontlicense.org"
)
OFL_URL = "https://openfontlicense.org"

EXPECTED = {
    **{
        f"roboto-{w}-{s}.woff2": (ROBOTO, "Version 3.015")
        for w in (300, 400, 700)
        for s in ("normal", "italic")
    },
    **{
        f"roboto-mono-{w}-{s}.woff2": (ROBOTO_MONO, "Version 3.001")
        for w in (400, 700)
        for s in ("normal", "italic")
    },
}


def _name(font: TTFont, name_id: int) -> str | None:
    record = font["name"].getName(name_id, 3, 1, 0x409)
    return None if record is None else str(record)


def test_the_font_directory_holds_exactly_the_ten_loaded_files() -> None:
    assert sorted(p.name for p in FONTS.glob("*.woff2")) == sorted(EXPECTED)


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_a_font_names_its_upstream_holder_and_the_ofl(filename: str) -> None:
    copyright_line, version = EXPECTED[filename]
    font = TTFont(str(FONTS / filename))
    found = {nid: _name(font, nid) for nid in (0, 5, 13, 14)}
    assert found[0] == copyright_line, f"name ID 0 (copyright) of {filename}"
    assert found[13] == OFL_DESCRIPTION, f"name ID 13 (licence description) of {filename}"
    assert found[14] == OFL_URL, f"name ID 14 (licence URL) of {filename}"
    assert found[5] is not None and found[5].startswith(version), f"name ID 5 of {filename}"
