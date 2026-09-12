#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tripwire for docs/_redirects. Detects structural drift, whatever caused it.

Commit 36c5f70 silently gained 18 blank lines through this file's comment
header while removing 19 rules. The mechanism was identified — `#` comments read
as Markdown H1s, so a markdownlint `--fix` pass applies MD022 and double-spaces
the header — but the vector never was: no git hook, no `core.hooksPath`, no git
filter or gitattribute, no editor format-on-save, no husky/lint-staged, no
direnv, no file watcher, no CI step, and no mkdocs hook can reach this file, and
none of the five gate commands alters it when re-run. Eleven prior commits
touched the file and all held at 8 blank lines, which rules out any *standing*
automation and marks the event as one-shot.

This check therefore does not try to prevent the rewrite. It detects it, on the
commit where it happens, regardless of what did it. Deliberately a tripwire and
not a formatter: it never edits the file.

    python3 scripts/check_redirects_structure.py

Exit 0 if the file is structurally intact, 1 with a specific diagnosis otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path


REDIRECTS = Path(__file__).resolve().parent.parent / "docs" / "_redirects"

# The file's comment header is the only place blank lines belong. This count has
# been stable across every commit in the file's history except the one anomaly
# above. If a deliberate edit changes it, update this number in the same commit —
# that is the point: the change becomes visible and intentional.
EXPECTED_BLANK_LINES = 8


def main() -> int:
    if not REDIRECTS.is_file():
        print(f"error: {REDIRECTS} not found", file=sys.stderr)
        return 1

    lines = REDIRECTS.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    problems: list[str] = []

    blanks = sum(1 for line in lines if not line.strip())
    if blanks != EXPECTED_BLANK_LINES:
        problems.append(
            f"blank-line count is {blanks}, expected {EXPECTED_BLANK_LINES}. "
            "If this change is deliberate, update EXPECTED_BLANK_LINES in this "
            "script in the same commit. If it is not, something rewrote the file "
            "— a doubled comment header is the known signature of a markdownlint "
            "--fix pass treating '#' comments as Markdown headings."
        )

    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) != 3:
            problems.append(f"line {number}: expected 3 fields, found {len(fields)}: {line!r}")
            continue
        source, destination, status = fields
        if not source.startswith("/"):
            problems.append(f"line {number}: source must start with '/': {source!r}")
        if not (destination.startswith("/") or destination.startswith("http")):
            problems.append(
                f"line {number}: destination must start with '/' or 'http': {destination!r}"
            )
        if status != "301":
            problems.append(f"line {number}: status must be '301', found {status!r}")

    if problems:
        print(f"docs/_redirects: {len(problems)} structural problem(s)", file=sys.stderr)
        for problem in problems[:20]:
            print(f"  - {problem}", file=sys.stderr)
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more", file=sys.stderr)
        return 1

    rules = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))
    print(f"docs/_redirects OK — {rules} rules, {blanks} blank lines, all well-formed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
