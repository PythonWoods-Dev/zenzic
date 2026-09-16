#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every Mermaid node takes its colour from a declared class, and every class value is the theme's.

WHAT THIS CAN VERIFY
--------------------
1. No diagram carries an inline ``style N fill:#...`` line. Colour comes from a
   ``classDef``, so one edit changes every diagram rather than thirty-eight lines.
2. Every ``classDef`` value exists in ``docs/assets/css/extra.css``'s dark block.
   Declared against derived: if the theme moves, this reports a divergence instead
   of letting the diagrams drift silently, which is exactly what happened here.
3. ``#ef4444`` appears nowhere in a diagram. It is named explicitly because it is
   the value this conversion removed: 8 diagram nodes carried it, the CSS never
   declared it, and repetition had made it look like a convention.

WHAT THIS CANNOT VERIFY, stated so the gate's name does not imply more
----------------------------------------------------------------------
**Whether a depicted flow is still the flow.** A diagram whose arrows describe a
pipeline that changed passes this check completely. It cannot know whether a step
is missing because it was removed from the product or because nobody updated the
picture, and it cannot tell a deliberate simplification from an omission.
It checks colour and declaration, not truth.

Scope: Mermaid blocks under ``docs/``. Rule cards carry their own icon colours and
are NOT in scope -- three of their values are undeclared today, and a gate that
starts red on seventy-one pages teaches its reader to ignore it.

Exit codes: 0 = conformant, 1 = divergence.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CSS = DOCS / "assets" / "css" / "extra.css"
RETIRED = "#ef4444"

FENCE = re.compile(r"^\s*```+\s*mermaid\s*$", re.I)
CLOSE = re.compile(r"^\s*```+\s*$")
STYLE = re.compile(r"^\s*style\s+\S+\s+.*fill:", re.I)
CLASSDEF = re.compile(r"^\s*classDef\s+(\w+)\s+(.*)$")
HEX = re.compile(r"#[0-9a-fA-F]{3,6}")


def dark_palette() -> set[str]:
    """Colours the dark scheme declares, which the diagrams must draw from."""
    css = CSS.read_text(encoding="utf-8")
    block = re.search(r'\[data-md-color-scheme="slate"\]\{(.*?)\}', css, re.S)
    if not block:
        return set()
    return {h.lower() for h in HEX.findall(block.group(1))}


def check() -> list[str]:
    palette = dark_palette()
    if not palette:
        return ["extra.css: the dark scheme block was not found, so nothing could be compared"]
    problems: list[str] = []
    for path in sorted(DOCS.rglob("*.md")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        i = 0
        while i < len(lines):
            if not FENCE.match(lines[i]):
                i += 1
                continue
            start, j = i + 1, i + 1
            while j < len(lines) and not CLOSE.match(lines[j]):
                j += 1
            rel = path.relative_to(ROOT)
            for offset, line in enumerate(lines[start:j], start=start + 1):
                if STYLE.match(line):
                    problems.append(f"{rel}:{offset}: inline style; use a declared class")
                if RETIRED in line.lower():
                    problems.append(
                        f"{rel}:{offset}: {RETIRED} is retired — the theme declares no such value"
                    )
                m = CLASSDEF.match(line)
                if m:
                    for hexv in HEX.findall(m.group(2)):
                        low = hexv.lower()
                        if low in {"#fff", "#ffffff"}:
                            continue
                        if low not in palette:
                            problems.append(
                                f"{rel}:{offset}: classDef {m.group(1)} uses {hexv}, "
                                f"which the dark scheme does not declare"
                            )
            i = j + 1
    return problems


def main() -> int:
    problems = check()
    if problems:
        print(f"diagram palette: {len(problems)} divergence(s)")
        for p in problems:
            print(f"  {p}")
        return 1
    print(
        "diagram palette: every node takes its colour from a declared class, "
        "and every class value is the theme's"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
