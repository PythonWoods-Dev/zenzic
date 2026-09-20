#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A list item's continuation stays inside the item, instead of falling out of the list.

Python-Markdown needs **four** spaces to keep a paragraph inside a list item across
a blank line. Two spaces reads as correct and renders as three elements: the list
closes, the continuation becomes a top-level paragraph, and a second list opens.
The Markdown is valid, so `markdownlint` passes it -- which is how 99 instances
survived until 2026-09-20, the oldest traced to v0.15.1. Every one shipped a list
item that stops mid-sentence with its other half orphaned below; in the 19
ordered-list cases the break also restarted the numbering, so `implement-adapter`
rendered its eight adapter-contract invariants as seven lists each numbered "1.".

WHAT THIS CAN VERIFY
--------------------
1. No list item is followed by a blank line and a continuation indented 1-3 spaces.
   That shape is the defect, exactly; 4 spaces is correct and no blank line is
   correct.
2. Both forms of the fix stay fixed. A reflow that reintroduces the blank line
   turns this red on the next run rather than on the next reader.

WHAT THIS CANNOT VERIFY, stated so the gate's name does not imply more
----------------------------------------------------------------------
**Whether the continuation should have been a separate paragraph at all.** The two
repairs differ -- join the wrapped sentence, or indent the deliberate paragraph to
four -- and only the author knows which was meant. This check proves the rendering
matches the source's structure; it cannot prove the structure was the intent.

**Which threshold a given reader's platform applies.** Verified at the source on
2026-09-20: Python-Markdown ends the item below four spaces (`tab_length`), and so
does Redcarpet 3.5, which is what dev.to runs -- `parse_listitem` in
`ext/redcarpet/markdown.c` breaks on `in_empty && i < 4 && data[beg] != '\t'`.
CommonMark uses the marker's content column instead and accepts two. Hashnode's
parser could not be established: its cheatsheet 404s and no primary source names
it, so it is left unverified rather than assumed. The check is unaffected either
way -- four spaces renders inside the item under all three, so this gate asks for
the one indent that is correct everywhere and can produce no platform-specific
false positive.

**Anything outside `zenzic/docs/` and the syndication drafts.** This is deliberate and measured, not an
oversight of the ecosystem-wide rule. The defect is Python-Markdown's four-space
requirement; CommonMark uses the marker's content column instead, so `markdown-it`
renders the same two-space source *inside* the list. The satellite repositories
ship no MkDocs build -- their Markdown is read through GitHub's GFM -- and a sweep
of all three on 2026-09-20 found zero instances in their own files (the three hits
were vendored VS Code test fixtures under `.vscode-test/`). Pointing this gate at
them would report on a shape that is correct where it lives.

**Ordered lists nested past one level.** The content column of a `1.` marker inside
another list is not the flat 4 this assumes, so a deep nesting could be flagged
where it renders correctly. None exists in `docs/` today.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
# Derived from the canonical posts, so the real gate is `docs/` above. Scanned
# anyway because a hand-edit to a copy would not pass through the generator, and
# because four spaces is the one indent that renders correctly under every parser
# involved -- Python-Markdown, Redcarpet and CommonMark alike. Gitignored, so it
# is absent in CI; missing is not a failure.
SYNDICATION = ROOT / ".human" / "editorial-drafts" / "external-syndication"

ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.) \S")
CONTINUATION = re.compile(r"^ {1,3}\S")
NEW_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.) ")
FENCE = ("```", "~~~")


def orphaned_continuations(text: str) -> list[tuple[int, str]]:
    """Return (line number, item text) for every continuation that leaves its list."""
    lines = text.split("\n")
    found: list[tuple[int, str]] = []
    in_fence = False
    for i in range(len(lines) - 2):
        stripped = lines[i].strip()
        if stripped.startswith(FENCE):
            in_fence = not in_fence
        if in_fence:
            continue
        nxt = lines[i + 2]
        if (
            ITEM.match(lines[i])
            and not lines[i + 1].strip()
            and CONTINUATION.match(nxt)
            and not NEW_ITEM.match(nxt)
            and not nxt.strip().startswith(FENCE)
        ):
            found.append((i + 1, lines[i].strip()))
    return found


def self_test() -> list[str]:
    """Prove the instrument finds the defect and spares both correct forms (Rule 39)."""
    cases = [
        ("- **A** - half\n\n  rest.\n", 1, "two-space continuation is the defect"),
        ("- **A** - half\n\n    rest.\n", 0, "four spaces keeps it in the item"),
        ("- **A** - half\n  rest.\n", 0, "no blank line keeps it in the item"),
        ("- **A** - half\n\n- **B** - x\n", 0, "the next item is not a continuation"),
        ("1. step\n\n  rest.\n", 1, "ordered lists break the same way"),
        ("- a\n\n  ```py\n  x\n  ```\n", 0, "an indented fence is not this defect"),
        ("```\n- a\n\n  rest.\n```\n", 0, "inside a fence nothing is a list"),
        ("Plain paragraph.\n\n  indented.\n", 0, "no list, no finding"),
    ]
    failures = []
    for text, want, why in cases:
        got = len(orphaned_continuations(text))
        if got != want:
            failures.append(f"  self-test: expected {want}, got {got} -- {why}")
    return failures


def main() -> int:
    if "--self-test" in sys.argv:
        failures = self_test()
        if failures:
            print("list continuation: the instrument is wrong")
            print("\n".join(failures))
            return 1
        print("list continuation: self-test passes, the instrument finds the defect")
        return 0

    problems = []
    roots = [DOCS] + ([SYNDICATION] if SYNDICATION.is_dir() else [])
    for root in roots:
        for path in sorted(root.rglob("*.md")):
            for line_no, item in orphaned_continuations(path.read_text(encoding="utf-8")):
                rel = path.relative_to(ROOT)
                problems.append(f"{rel}:{line_no}  {item[:62]}")

    if problems:
        print(f"list continuation: {len(problems)} item(s) lose their continuation")
        for p in problems:
            print(f"  {p}")
        print("  fix: join the wrapped sentence, or indent the paragraph to 4 spaces")
        return 1
    print("list continuation: every continuation stays inside its list item")
    return 0


if __name__ == "__main__":
    sys.exit(main())
