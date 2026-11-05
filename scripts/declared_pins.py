#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every declared pin in this repository, and the command that moves it.

`just bump-engine` moves one of them. Five others exist, each with its own
mechanism, and until this file nothing enumerated them: "which files carry a
pin" was answered from memory, and a pin whose bump command nobody remembers is
a pin that goes stale.

The self-test is the point. For each entry it checks three things:

* the **file** exists — a pin recorded against a path that moved is a pointer
  to nothing;
* the **value** is still readable there — a pin that changed shape silently
  stops being tracked, and the listing would print a stale number forever;
* the **command** exists — a recipe named here that is not in the justfile is a
  mechanism nobody can invoke, which is the same as one that was never built.

Usage:
    python scripts/declared_pins.py            # the listing
    python scripts/declared_pins.py --self-test
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ECOSYSTEM = REPO.parent


@dataclass(frozen=True)
class Pin:
    what: str
    file: Path
    #: Finds the current value. Returns None when the shape has moved.
    read: object
    #: How to change it. A `just` recipe of this repository, or a documented command.
    command: str
    #: True when `command` names a recipe in *this* repository's justfile.
    is_local_recipe: bool = True


def _first_group(path: Path, pattern: str) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(pattern, text, re.MULTILINE)
    return m.group(1) if m else None


def _corpus_pins(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    corpora = data.get("corpora") or []
    if not corpora:
        return None
    return ", ".join(
        f"{c['repository'].rsplit('/', 1)[-1].removesuffix('.git')}@{str(c['commit'])[:8]}"
        for c in corpora
        if "repository" in c and "commit" in c
    )


PINS: tuple[Pin, ...] = (
    Pin(
        what="Zenzic's own version",
        file=REPO / ".bumpversion.toml",
        read=lambda p: _first_group(p, r'^current_version\s*=\s*"([^"]+)"'),
        command="just release <part>",
    ),
    Pin(
        what="Documentation engine versions",
        file=REPO / "docs" / "reference" / "compatibility.md",
        read=lambda p: _first_group(p, r"^\|\s*MkDocs\s*\|\s*`([^`]+)`"),
        command='just bump-engine "<engine>" <version>',
    ),
    Pin(
        what="External corpus commits",
        file=REPO / "scripts" / "external-corpus-pin.json",
        read=_corpus_pins,
        command="python scripts/external_corpus_check.py --update",
        is_local_recipe=False,
    ),
    Pin(
        what="pre-commit hook revisions",
        file=REPO / ".pre-commit-config.yaml",
        read=lambda p: _first_group(p, r"^\s*rev:\s*([0-9a-f]{40})"),
        command="uvx pre-commit autoupdate --freeze",
        is_local_recipe=False,
    ),
    Pin(
        what="Python dependency resolution",
        file=REPO / "uv.lock",
        read=lambda p: _first_group(p, r'^version = "([^"]+)"'),
        command="uv lock",
        is_local_recipe=False,
    ),
    Pin(
        what="Minimum Core version (VS Code extension)",
        file=ECOSYSTEM / "zenzic-vscode" / "src" / "coreVersion.ts",
        read=lambda p: _first_group(p, r"MIN_CORE_VERSION\s*=\s*'([^']+)'"),
        command="just pin-core <version>   (in zenzic-vscode)",
        is_local_recipe=False,
    ),
)


def _listing() -> int:
    width = max(len(p.what) for p in PINS)
    for pin in PINS:
        value = pin.read(pin.file) if pin.file.exists() else None
        shown = value if value is not None else "(unreadable)"
        rel = pin.file.relative_to(ECOSYSTEM).as_posix()
        print(f"  {pin.what:<{width}}  {shown}")
        print(f"  {'':<{width}}  {rel}")
        print(f"  {'':<{width}}  → {pin.command}\n")
    return 0


def _justfile_recipes() -> set[str]:
    out = subprocess.run(  # noqa: S603
        ["just", "--summary"],  # noqa: S607
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return set(out.stdout.split()) if out.returncode == 0 else set()


def _self_test() -> int:
    problems: list[str] = []
    for pin in PINS:
        if not pin.file.exists():
            problems.append(f"{pin.what}: {pin.file} does not exist")
            continue
        if pin.read(pin.file) is None:
            problems.append(
                f"{pin.what}: the value is no longer readable in "
                f"{pin.file.name} — the pin changed shape and this listing "
                "would print nothing while claiming to track it"
            )
    recipes = _justfile_recipes()
    if recipes:
        for pin in PINS:
            if not pin.is_local_recipe:
                continue
            name = pin.command.split()[1]
            if name not in recipes:
                problems.append(
                    f"{pin.what}: names `just {name}`, which is not a recipe in this "
                    "justfile — a mechanism nobody can invoke was not built"
                )
    else:
        print("  note: `just --summary` unavailable; recipe existence unchecked")

    if problems:
        print("FAILED:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"self-test passed: {len(PINS)} declared pin(s), each readable with a live command")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv else _listing())
