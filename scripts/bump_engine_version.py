#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Bump a declared engine version, in every file that carries one.

`CONTRIBUTING.md` names `just version`, which bumps *Zenzic's* version. Nothing
named what a contributor does when MkDocs 2 ships — and the answer is spread
over three files that must agree:

* `docs/reference/compatibility.md` — the tested version, the verification
  method and the date it was last verified. This is the user-facing claim.
* `pyproject.toml` — the dependency pin, for engines that are pip dependencies.
* `uv.lock` — what that pin actually resolves to today.

The third is what makes the first checkable. For a pip-dependency engine this
script refuses a version the lock does not carry, because a "tested version"
nobody tested is the claim this table exists to prevent. For an engine that is
not a dependency (Zensical is parsed as data, never installed) there is nothing
to check against, and the script says so rather than pretending.

Usage:
    python scripts/bump_engine_version.py --list
    python scripts/bump_engine_version.py MkDocs 1.6.2
    python scripts/bump_engine_version.py --self-test
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
MATRIX = REPO / "docs" / "reference" / "compatibility.md"
LOCK = REPO / "uv.lock"

#: Engine label in the matrix -> the distribution name it is locked under, or
#: ``None`` when the engine is not a dependency of this project at all.
#:
#: Read from the matrix rather than duplicated as a list: the row is the
#: declaration, and a second list of engine names is the divergence this
#: codebase keeps paying for. Only the *mapping to a distribution* lives here,
#: because the matrix does not carry it.
_DISTRIBUTION = {
    "MkDocs": "mkdocs",
    "Material for MkDocs": "mkdocs-material",
    "Zensical": None,
    "Standalone": None,
    "Prebuilt (route manifest)": None,
    # The two generators `prebuilt` serves. Neither is a dependency and neither
    # has a version Zenzic reads: `prebuilt` consumes a manifest the user
    # generates, so what the matrix tracks is the artefact each claim was
    # measured against, not a release number. Bumping one is a matter of
    # re-measuring and moving the date.
    "↳ Astro / Starlight": None,
    "↳ Docusaurus": None,
}

_ROW = re.compile(r"^\|\s*(?P<engine>[^|]+?)\s*\|\s*(?P<version>[^|]*?)\s*\|(?P<rest>.*)\|\s*$")


def _rows(text: str) -> list[tuple[int, str, str, str]]:
    """Return ``(line index, engine, version cell, rest)`` for every matrix row.

    Bounded to the ``## Matrix`` section. The page carries a second four-column
    table further down — the MkDocs settings key table — and an unbounded parse
    reads `docs_dir` and `nav` as engines. The self-test found that before this
    script ever ran for real, which is what the self-test is for.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Matrix")
    except StopIteration:  # pragma: no cover - the page must carry the section
        raise SystemExit(f"{MATRIX} has no '## Matrix' section to read") from None
    end = next(
        (i for i, ln in enumerate(lines[start + 1 :], start + 1) if ln.startswith("## ")),
        len(lines),
    )

    out = []
    for i in range(start, end):
        m = _ROW.match(lines[i])
        if not m:
            continue
        engine = m["engine"]
        if engine in {"Engine", ":---"} or engine.startswith(":-"):
            continue
        out.append((i, engine, m["version"], m["rest"]))
    return out


def _locked_version(lock_text: str, distribution: str) -> str | None:
    """Return the version `uv.lock` resolves *distribution* to, if present."""
    pattern = re.compile(
        r'^\[\[package\]\]\nname = "' + re.escape(distribution) + r'"\nversion = "([^"]+)"',
        re.MULTILINE,
    )
    m = pattern.search(lock_text)
    return m.group(1) if m else None


def _bump_cell(cell: str, new_version: str) -> str:
    """Replace the backticked version at the head of a matrix version cell.

    The rest of the cell — a pin, a `(pre-1.0)` note — is carried through
    untouched, because it says something the version does not.
    """
    return re.sub(r"`[^`]+`", f"`{new_version}`", cell, count=1)


def bump(engine: str, new_version: str, *, today: str) -> tuple[str, list[str]]:
    """Return the rewritten matrix and the notes to print. Raises on refusal."""
    text = MATRIX.read_text(encoding="utf-8")
    rows = _rows(text)
    known = [r[1] for r in rows]
    if engine not in known:
        raise SystemExit(f"unknown engine {engine!r}. The matrix carries: {', '.join(known)}")

    notes: list[str] = []
    distribution = _DISTRIBUTION.get(engine)
    if distribution:
        locked = _locked_version(LOCK.read_text(encoding="utf-8"), distribution)
        if locked is None:
            raise SystemExit(
                f"{engine} is declared a dependency ({distribution}) and uv.lock does not "
                "carry it. Either the lock is stale or the mapping in this script is."
            )
        if locked != new_version:
            raise SystemExit(
                f"refusing: uv.lock resolves {distribution} to {locked}, not {new_version}.\n"
                f"  A tested version nobody tested is what this table exists to prevent.\n"
                f"  Change the pin in pyproject.toml, run `uv lock`, then bump to {locked}."
            )
        notes.append(f"uv.lock confirms {distribution} {locked}")
    else:
        notes.append(
            f"{engine} is not a dependency of this project, so there is nothing to check "
            "the version against — the date records a manual review, not a lock"
        )

    return _rewrite_rows(text, engine, new_version, today=today)[0], notes


def _rewrite_rows(text: str, engine: str, new_version: str, *, today: str) -> tuple[str, bool]:
    """Return the matrix with *engine*'s row rewritten, and whether it was found.

    Kept apart from :func:`bump` so the self-test can drive it without a lock, a
    real file, or today's date -- the first version of this rewrite put the date
    in the verification-method column, and nothing would have caught it.
    """
    rows = _rows(text)
    lines = text.splitlines(keepends=True)
    for index, name, version_cell, rest in rows:
        if name != engine:
            continue
        new_cell = _bump_cell(version_cell, new_version)
        # `rest` is everything after the version cell: " method | date ". Split
        # once from the right, so the date is replaced and the method -- which
        # can itself contain pipes in inline code -- is carried through whole.
        method, _old_date = rest.rsplit("|", 1)
        ending = "\n" if lines[index].endswith("\n") else ""
        lines[index] = f"| {name} | {new_cell} |{method}| {today} |{ending}"
        return "".join(lines), True
    return text, False


def _self_test() -> int:
    """The recipe is a claim about the matrix; this is the claim checked.

    Collected rather than asserted, matching the other scripts here: a self-test
    that stops at the first problem reports one of them, and the point of
    running it in `just verify` is to be told all of them at once.
    """
    problems: list[str] = []
    sample = (
        "| Engine | Tested version | Verification method | Last verified |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| MkDocs | `1.6.1` (pinned `>=1.5.0,<2`) | some method | 2026-08-29 |\n"
        "| Standalone | — | Engine-agnostic | — |\n"
    )
    if [r[1] for r in _rows("## Matrix\n" + sample)] != ["MkDocs", "Standalone"]:
        problems.append("the matrix parser does not read a plain two-row table")
    # The bound holds: a second table after the section is not read. The page
    # carries one -- the MkDocs settings keys -- and an unbounded parse reads
    # `docs_dir` and `nav` as engines.
    bounded = _rows("## Matrix\n" + sample + "\n## Settings\n| Key | `nav` | x | y |\n")
    if [r[1] for r in bounded] != ["MkDocs", "Standalone"]:
        problems.append("the parser reads past the '## Matrix' section")
    if _bump_cell("`1.6.1` (pinned `>=1.5.0,<2`)", "1.6.2") != "`1.6.2` (pinned `>=1.5.0,<2`)":
        problems.append("bumping the version cell does not preserve the pin beside it")

    # The rewrite puts the date in the date column, which the first version of
    # this script did not: it replaced the verification method instead.
    rebuilt, _found = _rewrite_rows("## Matrix\n" + sample, "MkDocs", "1.6.2", today="2026-01-01")
    row = next((ln for ln in rebuilt.splitlines() if ln.startswith("| MkDocs")), "")
    if row != "| MkDocs | `1.6.2` (pinned `>=1.5.0,<2`) | some method | 2026-01-01 |":
        problems.append(f"the rewrite put a value in the wrong column: {row!r}")

    lock = '[[package]]\nname = "mkdocs"\nversion = "1.6.1"\nsource = { registry = "x" }\n'
    if _locked_version(lock, "mkdocs") != "1.6.1":
        problems.append("the lock reader does not find a package it should")
    if _locked_version(lock, "absent") is not None:
        problems.append("the lock reader invents a package that is not there")

    # And the real matrix parses, which a sample cannot prove.
    real = _rows(MATRIX.read_text(encoding="utf-8"))
    if len(real) < 3:
        problems.append(f"the real matrix parsed {len(real)} rows")
    unmapped = {r[1] for r in real} - set(_DISTRIBUTION)
    if unmapped:
        problems.append(
            f"the matrix carries an engine this script has no mapping for: {sorted(unmapped)} "
            "-- a row added without saying how its version is verified"
        )

    if problems:
        print("FAILED:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"self-test passed: {len(real)} matrix row(s), both directions")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", nargs="?", help="engine label exactly as the matrix spells it")
    parser.add_argument("version", nargs="?", help="the new tested version")
    parser.add_argument("--list", action="store_true", help="show the matrix as it stands")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if args.list or not (args.engine and args.version):
        for _, engine, version, _rest in _rows(MATRIX.read_text(encoding="utf-8")):
            dist = _DISTRIBUTION.get(engine)
            where = f"locked as {dist}" if dist else "not a dependency"
            print(f"  {engine:22} {version:34} ({where})")
        if not (args.engine and args.version):
            print("\nUsage: just bump-engine <engine> <version>")
        return 0

    today = _dt.date.today().isoformat()
    new_text, notes = bump(args.engine, args.version, today=today)
    MATRIX.write_text(new_text, encoding="utf-8")
    for note in notes:
        print(f"  {note}")
    print(f"✓ {args.engine} → {args.version}, last verified {today}")
    print("  Review the verification method: a new version may have changed how it is tested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
