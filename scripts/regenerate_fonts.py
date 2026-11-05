#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the self-hosted `docs/assets/fonts/*.woff2` from the pinned upstream releases.

Run it with its own pinned fontTools, which is not a runtime dependency:

    uvx --from 'fonttools[woff]==4.68.0' python -I scripts/regenerate_fonts.py

WHY THIS EXISTS
---------------
The ten WOFF2 files first committed (fc10edb) were Roboto 3.015 and Roboto Mono
3.001 subsets of unrecorded origin, with name ID 13 (the licence description)
stripped. This script makes the files reproducible from a source anyone can
check: it downloads each upstream file, refuses it unless its SHA-256 equals the
pinned value, checks that the original's own name table carries the copyright
(name ID 0) and the OFL (name IDs 13 and 14) before subsetting, and keeps those
records in the subset.

WHAT IT REPRODUCES, MEASURED FROM THE PREVIOUS FILES
----------------------------------------------------
`UNICODES` and `LAYOUT_FEATURES` are the values read from the previous files with
fontTools on 2026-11-02 (the union of each family's cmap; the GSUB/GPOS feature
tags). The subsetter keeps a code point only where the source has it, so one set
yields both families' previous cmaps exactly: U+0000 and U+0002 exist only in
Roboto, U+2215 only in Roboto Mono. Roboto Mono's previous files had no layout
feature, and keep none.

What it does NOT reproduce: the `unicode-range` in `fonts.css` is Google Fonts'
"latin" range, wider than these subsets. The browser draws a code point in that
range that the file lacks with the next font in the stack; this was already so
with the previous files. Hinting is kept as upstream ships it (the previous Roboto
Mono files were unhinted; these are hinted, as the release's TTFs are). The
previous files had a `STAT` table, which these upstream static TTFs do not carry:
it names the axes of a variable font and plays no part in a browser's rendering
of a static face chosen by `@font-face`.

The script is deterministic: `head.modified` is kept from the source, so two runs
write identical bytes.
"""

from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "fonts"

OFL_DESCRIPTION = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: https://openfontlicense.org"
)
OFL_URL = "https://openfontlicense.org"

#: Copyright, licence and URL (0, 13, 14), the family and style names a browser and an OS
#: font menu read (1-4, 6, 16, 17) and the version (5).
NAME_IDS = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]


def _ranges(*items: int | tuple[int, int]) -> frozenset[int]:
    points: set[int] = set()
    for item in items:
        low, high = item if isinstance(item, tuple) else (item, item)
        points.update(range(low, high + 1))
    return frozenset(points)


UNICODES = _ranges(
    0x0000, 0x0002, 0x000D, (0x0020, 0x007E), (0x00A0, 0x00FF), 0x0131, (0x0152, 0x0153),
    0x02BC, 0x02C6, 0x02DA, 0x02DC, (0x0300, 0x0301), 0x0303, 0x0309, 0x0323, 0x2002,
    0x2009, 0x200B, (0x2013, 0x2014), (0x2018, 0x201A), (0x201C, 0x201E), 0x2022, 0x2026,
    (0x2032, 0x2033), (0x2039, 0x203A), 0x2044, 0x20AC, 0x2122, 0x2212, 0x2215, 0xFEFF,
    0xFFFD,
)  # fmt: skip

ROBOTO_FEATURES = [
    "ccmp", "dnom", "frac", "liga", "lnum", "locl", "numr", "pnum", "tnum",
    "kern", "mark", "mkmk",
]  # fmt: skip


@dataclass(frozen=True)
class Family:
    copyright: str
    version: str
    features: list[str]
    #: output file name -> source: a member of the pinned archive, or a pinned URL.
    files: dict[str, tuple[str, str | None]]


ROBOTO_ARCHIVE = (
    "https://github.com/googlefonts/roboto-classic/releases/download/v3.015/Roboto_v3.015.zip",
    "bee3e9334ea86dd63e184598f31fb16750881c2da1a6f097a66e0f66a95b3d54",
)
MONO_BASE = (
    "https://raw.githubusercontent.com/googlefonts/robotomono/"
    "111eb14e367888c9374da4da0b018e72cf8ac46d/fonts/ttf/"  # tag v3.001
)

FAMILIES = (
    Family(
        copyright=(
            "Copyright 2011 The Roboto Project Authors "
            "(https://github.com/googlefonts/roboto-classic)"
        ),
        version="Version 3.015",
        features=ROBOTO_FEATURES,
        files={
            f"roboto-{out}.woff2": (f"web/static/Roboto-{src}.ttf", None)
            for out, src in {
                "300-normal": "Light",
                "300-italic": "LightItalic",
                "400-normal": "Regular",
                "400-italic": "Italic",
                "700-normal": "Bold",
                "700-italic": "BoldItalic",
            }.items()
        },
    ),
    Family(
        copyright=(
            "Copyright 2015 The Roboto Mono Project Authors "
            "(https://github.com/googlefonts/robotomono)"
        ),
        version="Version 3.001",
        features=[],
        files={
            "roboto-mono-400-normal.woff2": (
                MONO_BASE + "RobotoMono-Regular.ttf",
                "af0bff7599c3df3831755c16e39b3c496df74b8c8d8a1161b14dc8461be17cb4",
            ),
            "roboto-mono-400-italic.woff2": (
                MONO_BASE + "RobotoMono-Italic.ttf",
                "4549325cd2d10938d37d63eba2aaca7c2e16e48322dc767576eab45e512b6ad2",
            ),
            "roboto-mono-700-normal.woff2": (
                MONO_BASE + "RobotoMono-Bold.ttf",
                "3ecf35e5e87accc7578b605d1f5f0bc30d88b195d6807bec8a0c57f6aa95c4db",
            ),
            "roboto-mono-700-italic.woff2": (
                MONO_BASE + "RobotoMono-BoldItalic.ttf",
                "a0f16567447311eaf42a35f6c50eb64b911694b42f1b01038e3b7e92c20f131d",
            ),
        },
    ),
)


def fetch(url: str, sha256: str) -> bytes:
    """The bytes at *url*, or exit when their SHA-256 is not the pinned one."""
    if not url.startswith("https://"):
        raise SystemExit(f"refusing a non-https source: {url}")
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 -- https only
        data: bytes = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SystemExit(f"{url}: sha256 {digest}, pinned {sha256}")
    return data


def _name(font: TTFont, name_id: int) -> str | None:
    record = font["name"].getName(name_id, 3, 1, 0x409)
    return None if record is None else str(record)


def check_original(font: TTFont, family: Family, label: str) -> None:
    """The original release file names its holder and the OFL, before any subsetting."""
    found = {nid: _name(font, nid) for nid in (0, 5, 13, 14)}
    problems = [
        f"name ID {nid} is {found[nid]!r}, expected {want!r}"
        for nid, want in ((0, family.copyright), (13, OFL_DESCRIPTION), (14, OFL_URL))
        if found[nid] != want
    ]
    if not (found[5] or "").startswith(family.version):
        problems.append(f"name ID 5 is {found[5]!r}, expected {family.version}…")
    if problems:
        raise SystemExit(f"{label}: " + "; ".join(problems))


def make_subset(source: bytes, family: Family) -> bytes:
    font = TTFont(io.BytesIO(source), recalcTimestamp=False)
    options = subset.Options()
    options.layout_features = list(family.features)
    options.name_IDs = list(NAME_IDS)
    options.name_languages = [0x0409]
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(UNICODES))
    subsetter.subset(font)
    font.flavor = "woff2"  # `Options.flavor` is read only by fontTools' command line
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def main() -> int:
    archive_url, archive_sha = ROBOTO_ARCHIVE
    archive = zipfile.ZipFile(io.BytesIO(fetch(archive_url, archive_sha)))
    for family in FAMILIES:
        for out_name, (where, sha) in family.files.items():
            if sha is None:
                source, label = archive.read(where), f"{archive_url}!{where}"
            else:
                source, label = fetch(where, sha), where
            check_original(TTFont(io.BytesIO(source)), family, label)
            data = make_subset(source, family)
            (OUT / out_name).write_bytes(data)
            print(f"{out_name}: {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
