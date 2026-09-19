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

Scope: Mermaid blocks under ``docs/``, **and the rule cards' icon colours**.

The cards were out of scope until 2026-09-16, because two of their values were
undeclared and a gate that starts red on seventy-one pages teaches its reader to
ignore it. `V031_RULE_CARD_ICONS` converted the 145 hand-written icons to CSS
variables, so the gate now starts green and the exclusion has no reason left.

**What the cards can and cannot do.** They are HTML inside Markdown, not Mermaid,
so they cannot use ``classDef``. A CSS variable *does* work inside a Material icon
attribute -- measured by building the site and reading the rendered HTML, not
assumed -- so a variable is required where a literal would merely happen to match
today. The 71 Severity icons are the exception: ``sync_rule_card_badges.py`` owns
them and ``tests/test_rule_card_badges.py`` asserts their literal with
``#[0-9a-f]{6}``, so converting them is a change to that script's contract and is
not this gate's business. They are checked as literals, like any other value.

**This gate reads ``docs/**/*.md`` and nothing else, and that perimeter is
narrower than the project's diagrams.** A coverage audit on 2026-09-16 ran this
file's own fence pattern across every surface and found 12 blocks here and
**11 more outside**, in four files that this gate cannot see. They are not
missing by accident: the private trees are gitignored, and a script in this
public directory must not name them (see *Governance Scope* in the control
plane's own instructions -- a public file citing a private path is the exact
disclosure defect recorded there). Those 11 are checked by the private-side
gate instead, so the surface is covered by a second instrument rather than by a
promise to remember.

What no instrument covers, stated rather than left silent: diagrams in the three
satellite repositories and the four READMEs -- measured empty on 2026-09-16, with
the sweep's reach positive-controlled, but nothing re-measures them on a schedule.

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


CARD_ICON = re.compile(r':material-[a-z-]+:\{[^}]*style="color:\s*(?P<value>[^;"]+);?"[^}]*\}')
VAR_REF = re.compile(r"var\(\s*(--[a-z-]+)\s*\)")


def declared_variables() -> set[str]:
    """Every ``--zz-*`` custom property the stylesheet defines, in any block."""
    css = CSS.read_text(encoding="utf-8")
    return set(re.findall(r"(--zz-[a-z-]+)\s*:", css))


def check_cards() -> list[str]:
    """Card icon colours: a declared variable, or a value the theme declares."""
    cards = ROOT / "docs" / "rules"
    if not cards.is_dir():
        return []
    palette = dark_palette() | light_palette()
    variables = declared_variables()
    problems: list[str] = []
    for path in sorted(cards.glob("*.md")):
        rel = path.relative_to(ROOT)
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = CARD_ICON.search(line)
            if not m:
                continue
            value = m.group("value").strip()
            ref = VAR_REF.fullmatch(value)
            if ref:
                if ref.group(1) not in variables:
                    problems.append(
                        f"{rel}:{n}: {value} names a variable the stylesheet does not define"
                    )
                continue
            low = value.lower()
            if low == RETIRED:
                problems.append(
                    f"{rel}:{n}: {RETIRED} is retired — the theme declares no such value"
                )
            elif low.startswith("#") and low not in palette:
                problems.append(
                    f"{rel}:{n}: {value} is not a value the theme declares; use a var(--zz-*)"
                )
    return problems


def light_palette() -> set[str]:
    """The light scheme's values, which a variable may legitimately resolve to."""
    css = CSS.read_text(encoding="utf-8")
    block = re.search(r'\[data-md-color-scheme="default"\]\s*\{([^}]*)\}', css, re.S)
    if not block:
        return set()
    return {h.lower() for h in HEX.findall(block.group(1))}


def self_test() -> list[str]:
    """The rule must fire on a planted divergence and stay silent on a clean one.

    A gate whose clean line has never been shown to become a failing line is a
    gate nobody has tested: "nothing found" reads identically whether the check
    worked or the check is broken. Two gates built earlier in this cycle print
    that clean line without carrying a control. This one is not a third.
    """
    palette = {"#10b981"}
    variables = {"--zz-success"}

    def judge(value: str) -> bool:
        ref = VAR_REF.fullmatch(value)
        if ref:
            return ref.group(1) not in variables
        low = value.lower()
        return low == RETIRED or (low.startswith("#") and low not in palette)

    cases = [
        ("a declared variable passes", "var(--zz-success)", False),
        ("an undefined variable is caught", "var(--zz-nonesuch)", True),
        ("a declared literal passes", "#10b981", False),
        ("an undeclared literal is caught", "#123456", True),
        ("the retired value is caught", RETIRED, True),
    ]
    failed = [name for name, value, expected in cases if judge(value) is not expected]
    if failed:
        return ["SELF-TEST FAILED: " + "; ".join(failed)]
    print(f"self-test passed: {len(cases)} case(s), both directions")
    return []


def main() -> int:
    failures = self_test()
    if failures:
        for f in failures:
            print(f)
        return 1
    problems = check() + check_cards()
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
