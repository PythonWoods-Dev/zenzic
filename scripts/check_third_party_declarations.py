#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A file declared as PythonWoods' own does not carry another holder's marks.

`reuse lint` asks whether every file *has* a copyright and licence declaration.
It does not ask whether the declaration is *true*. Three groups of third-party
files were declared "2026 PythonWoods", Apache-2.0, and `reuse lint` passed on
every one of them for months:

1. **The Roboto and Roboto Mono fonts** (`docs/assets/fonts/*.woff2`, added in
   fc10edb, 2026-07-02), covered by a `docs/assets/fonts/**` block added to
   `REUSE.toml` in the same commit with the project's own values, while the
   `NOTICE` written in that commit already listed them as third-party.
2. **The compiled Tailwind bundle** (`docs/assets/css/zenzic-tailwind.min.css`),
   whose first line is `/*! tailwindcss v4.3.1 | MIT License | ... */`: a
   PythonWoods header was prepended above that banner on import (6573beb,
   2026-06-22), then moved to a `.license` sidecar (6507e5e, 2026-07-04).
3. **The OASIS SARIF 2.1.0 schema** (`tests/fixtures/sarif-2.1.0-schema.json`,
   d5cf7c7, 2026-06-28), whose `$id` points at the OASIS repository, given a
   sidecar with the project's two default lines.

Corrected in 9da4e36. In each case the file itself said whose it was, and no
gate read the file.

WHAT THIS CAN VERIFY
--------------------
For every file `reuse` covers, the declaration is resolved with `reuse`'s own
API (`Project.reuse_info_of`), so `REUSE.toml` precedence, `.license` sidecars
and inline headers are read the way `reuse lint` reads them. A file whose
declared holders (the `SPDX-FileCopyrightText` values from `REUSE.toml`, a
sidecar, or an inline SPDX header) are all PythonWoods is "declared own". A
declared-own file is reported when its content carries a third-party marker:

1. **A preserved licence banner** -- a `/*! ... */` comment naming a licence,
   or an `@license` tag in a comment, each at the start of a line: the form
   minifiers keep precisely because it is someone else's notice. Quoted
   mid-sentence, as prose and this docstring quote them, they are not markers.
2. **A plain copyright line of another holder** -- `Copyright (c) 2020 Foo`,
   `Copyright © ...`, `Copyright 2011 The ... Authors` -- that does not name
   PythonWoods. `SPDX-FileCopyrightText` lines are declarations, not markers.
3. **A font file** (`.woff`, `.woff2`, `.ttf`, `.otf`). With fontTools (and
   brotli, for WOFF2) importable, the name table's copyright (name ID 0) is
   read and the file is reported only when it does not name PythonWoods.
   Neither is a dependency of this repository, so in the ordinary environment
   **every** font declared as PythonWoods' own is reported: this project draws
   no typefaces, and a font it ships is somebody else's until shown otherwise.
4. **A JSON document whose `$id` is another organisation's URL.** A schema's
   `$id` names its publisher; this project's own schemas use `zenzic.dev`.
   `$schema` is not read: on a schema it names the JSON Schema meta-schema, on
   a data file the format the file conforms to -- neither says who wrote it.

Run with `--self-test` to check the instrument: it plants each marker in a
throwaway REUSE project and asserts it is found, and that a third-party file
declared under its real holder is not.

WHAT THIS CANNOT VERIFY, stated so the gate's name does not imply more
----------------------------------------------------------------------
**A copied file with no marker in it.** A snippet pasted without its banner, a
font with its name table stripped, a schema without an `$id`: the content says
nothing, and nothing here can say it for the content.

**That a third-party declaration is correct.** A file declared under another
holder is outside this check by construction. Whether "OFL-1.1" is the right
licence for a font is a fact about the upstream project, verified at the
source, not here.

**Markers deeper than the first 16 KiB of a text file.** Banners, headers and
`$id` sit at the top; scanning whole files would turn every document that
*discusses* a licence into a finding. A bundle that concatenates a second
library after the first 16 KiB is not seen.

**Files that list other holders by purpose.** `NOTICE`, `LICENSE` and
`LICENSES/` exist to quote other projects' notices, and `CHANGELOG.md` records
what was corrected; they are exempted below by name, each with its reason.
"""

from __future__ import annotations

import re
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from reuse.project import Project


ROOT = Path(__file__).resolve().parent.parent

#: The project's own holder, as every SPDX header in the repository writes it.
OWN_HOLDER = "PythonWoods"
#: The project's own licence, as `REUSE.toml` and the SPDX headers declare it.
OWN_LICENCE = "Apache-2.0"
#: Hosts the project's own schemas use in `$id`.
OWN_HOSTS = ("zenzic.dev", "pythonwoods.dev")

#: Files whose purpose is to quote other holders' notices. Exempted by name,
#: never by pattern, so a new file is checked until someone argues otherwise.
EXEMPT = {
    "NOTICE": "lists the bundled and depended-on projects' copyright notices by purpose",
    "LICENSE": "the Apache-2.0 text, which names its own licensor",
    "CHANGELOG.md": "records the corrections of earlier third-party declarations",
}
#: `LICENSES/` holds licence texts, which name their authors by design.
EXEMPT_DIRS = ("LICENSES/",)

FONT_SUFFIXES = (".woff", ".woff2", ".ttf", ".otf")
HEAD_BYTES = 16 * 1024

# Both are anchored to the start of a line (after a comment opener for the tag),
# where a preserved banner and a JSDoc tag sit, so that prose and Markdown which
# *quote* one mid-sentence are not markers.
BANNER = re.compile(
    r"^[^\S\n]*/\*!.{0,200}?\blicen[cs]e\b", re.IGNORECASE | re.MULTILINE | re.DOTALL
)
LICENSE_TAG = re.compile(r"^[^\S\n]*(?:/\*\*?|\*|//)[^\S\n]*@license\b", re.MULTILINE)
# A copyright line needs a (c)/© or a year after the word, so that prose such
# as "copyright notices" or "Copyright holder" is not a marker.
COPYRIGHT = re.compile(
    r"^(?P<line>[^\S\n]*(?:[#*/;<!-]+[^\S\n]*)?"
    r"Copyright[^\S\n]+(?:\(c\)|©)?[^\S\n]*(?:\d{4}|\(c\)|©).*)$",
    re.IGNORECASE | re.MULTILINE,
)
JSON_ID = re.compile(r'"\$id"\s*:\s*"(?P<url>[^"]+)"')


def declaration(project: Project, path: Path) -> tuple[list[str], set[str]]:
    """The SPDX-declared holders of *path*, and every licence expression declared for it.

    Plain `Copyright ...` lines that `reuse` also reads from a file's content are
    left out of the holders on purpose: they are what this check looks *for*, not
    the declaration it compares them against.
    """
    from reuse.copyright import CopyrightPrefix

    spdx = {
        CopyrightPrefix.SPDX,
        CopyrightPrefix.SPDX_C,
        CopyrightPrefix.SPDX_SYMBOL,
        CopyrightPrefix.SPDX_STRING,
        CopyrightPrefix.SPDX_STRING_C,
        CopyrightPrefix.SPDX_STRING_SYMBOL,
    }
    holders: list[str] = []
    licences: set[str] = set()
    for info in project.reuse_info_of(path):
        holders.extend(n.name for n in info.copyright_notices if n.prefix in spdx)
        licences.update(str(e) for e in info.spdx_expressions)
    return holders, licences


def declared_own(holders: list[str], licences: set[str]) -> bool:
    """True when the declaration names PythonWoods alone, or gives the project's licence alone.

    The second arm is the file with no SPDX holder whose licence comes from a
    `REUSE.toml` glob: `reuse` takes its holder from a plain `Copyright (c)`
    line in the content and its licence from the glob, so a vendored file is
    declared under the project's licence and `reuse lint` is satisfied.
    """
    if any(OWN_HOLDER not in h for h in holders):
        return False
    return bool(holders) or licences == {OWN_LICENCE}


def _font_copyright(path: Path) -> str | None:
    """Name ID 0 of a font, or None when fontTools cannot read it here."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    try:
        name = TTFont(str(path))["name"]
    except Exception:  # noqa: BLE001 -- unreadable means unverified, reported below
        return None
    return str(name.getDebugName(0) or "")


def markers(path: Path) -> list[str]:
    """Every third-party marker in *path*'s content, as a short description."""
    if path.suffix.lower() in FONT_SUFFIXES:
        notice = _font_copyright(path)
        if notice is None:
            return ["a font file (its name table cannot be read here: fontTools is not installed)"]
        if OWN_HOLDER in notice:
            return []
        return [f"font name table copyright: {notice!r}"]

    head = path.read_bytes()[:HEAD_BYTES]
    if b"\0" in head:
        return []
    text = head.decode("utf-8", errors="replace")
    found: list[str] = []
    if match := BANNER.search(text):
        found.append(f"licence banner: {match.group(0)[:80]!r}")
    if LICENSE_TAG.search(text):
        found.append("an @license tag")
    for match in COPYRIGHT.finditer(text):
        line = match.group("line").strip()
        if "SPDX-" in line or OWN_HOLDER in line:
            continue
        found.append(f"copyright line: {line[:80]!r}")
    if path.suffix.lower() == ".json":
        for match in JSON_ID.finditer(text):
            url = match.group("url")
            if url.startswith(("http://", "https://")) and not any(h in url for h in OWN_HOSTS):
                found.append(f"JSON $id of another publisher: {url}")
    return found


def _exempt(rel: str) -> bool:
    return rel in EXEMPT or rel.startswith(EXEMPT_DIRS)


def problems_in(root: Path, files: Iterable[Path] | None = None) -> list[str]:
    from reuse.project import Project

    project = Project.from_directory(root)
    out: list[str] = []
    for path in sorted(files if files is not None else project.all_files()):
        rel = path.relative_to(root).as_posix()
        if _exempt(rel):
            continue
        holders, licences = declaration(project, path)
        if not declared_own(holders, licences):
            continue
        for marker in markers(path):
            out.append(f"{rel}: declared {OWN_HOLDER}' own, but carries {marker}")
    return out


# REUSE-IgnoreStart -- the planted declarations below are fixtures, not this file's.
_HEADER = "SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>\n\nSPDX-License-Identifier: Apache-2.0\n"


def self_test() -> list[str]:
    """Plant each marker in a REUSE project and assert the instrument sees it.

    A clean sweep means nothing until this passes: an instrument that matches
    nothing reports a clean repository in exactly the words of one that works.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "LICENSES").mkdir()
        (root / "LICENSES" / "Apache-2.0.txt").write_text("Apache\n", encoding="utf-8")
        (root / "LICENSES" / "MIT.txt").write_text("MIT\n", encoding="utf-8")
        (root / "REUSE.toml").write_text(
            "version = 1\n\n"
            '[[annotations]]\npath = ["assets/**", "schema.json"]\n'
            'SPDX-FileCopyrightText = "2026 PythonWoods <dev@pythonwoods.dev>"\n'
            'SPDX-License-Identifier = "Apache-2.0"\n\n'
            '[[annotations]]\npath = "assets/real.min.css"\nprecedence = "override"\n'
            'SPDX-FileCopyrightText = "Some Labs, Inc."\nSPDX-License-Identifier = "MIT"\n',
            encoding="utf-8",
        )
        (root / "assets").mkdir()
        cases: dict[str, tuple[bytes, bool, str]] = {
            "assets/bundle.min.css": (
                b"/*! somecss v1.0 | MIT License | x */\n.a{}",
                True,
                "banner",
            ),
            "assets/lib.js": (b"/**\n * @license Apache-2.0\n */\nx()", True, "@license"),
            "assets/vendored.txt": (b"Copyright (c) 2019 Jane Doe\n", True, "copyright line"),
            "assets/font.woff2": (b"wOF2\0\0\0\0", True, "font file"),
            "schema.json": (b'{"$id": "https://example.org/s.json"}\n', True, "foreign $id"),
            "assets/real.min.css": (
                b"/*! somecss v1.0 | MIT License */",
                False,
                "declared under its holder",
            ),
            "assets/own.css": (
                b"/* our theme. Copyright notices live in NOTICE. */",
                False,
                "prose",
            ),
        }
        for rel, (content, _, _) in cases.items():
            (root / rel).write_bytes(content)
        (root / "own.json").write_bytes(b'{"$id": "https://zenzic.dev/schemas/x.json"}\n')
        (root / "own.json.license").write_text(_HEADER, encoding="utf-8")
        (root / "sidecar.css").write_bytes(b"/*! other v2 | MIT License */")
        (root / "sidecar.css.license").write_text(_HEADER, encoding="utf-8")

        found = problems_in(root)
        failures = []
        for rel, (_, want, why) in cases.items():
            got = any(p.startswith(f"{rel}:") for p in found)
            if got != want:
                failures.append(
                    f"  self-test: {rel} expected {'a' if want else 'no'} finding -- {why}"
                )
        if any(p.startswith("own.json:") for p in found):
            failures.append(
                "  self-test: own.json reported -- an $id on zenzic.dev is the project's own"
            )
        if not any(p.startswith("sidecar.css:") for p in found):
            failures.append(
                "  self-test: sidecar.css not reported -- a .license sidecar declares too"
            )
    return failures


# REUSE-IgnoreEnd


def main() -> int:
    failures = self_test()
    if failures:
        print("third-party declarations: the instrument is wrong")
        print("\n".join(failures))
        return 1
    if "--self-test" in sys.argv:
        print(
            "third-party declarations: self-test passes, the instrument finds every planted marker"
        )
        return 0
    problems = problems_in(ROOT)
    if problems:
        print(
            f"third-party declarations: {len(problems)} file(s) declared as {OWN_HOLDER}' own carry another holder's marks"
        )
        for p in problems:
            print(f"  {p}")
        print("  fix: annotate the file under its real holder and licence (REUSE.toml, precedence")
        print(
            "  'override', or its .license sidecar), add the licence text to LICENSES/, and list it in NOTICE"
        )
        return 1
    print(
        f"third-party declarations: no file declared as {OWN_HOLDER}' own carries another holder's marks"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
