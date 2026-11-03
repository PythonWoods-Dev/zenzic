#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Refuse a commit message that names a private folder, or a term of the local list.

    python3 scripts/check_commit_message_terms.py <commit-msg-file>
    python3 scripts/check_commit_message_terms.py --self-test

A commit message is public the moment it is pushed, and correcting it afterwards
means rewriting published history. The pre-push gates catch such a message among
the commits about to be pushed; this hook catches it when it is written, while a
reword costs nothing.

Exit 0 when the message is acceptable, 1 with each offending line otherwise.

What it refuses
---------------
* **A path inside a private folder**: `.claude/`, `.human/` or `.governance/`
  followed by a slash. The bare names stay allowed, because the product itself
  refuses to point into those folders and a message about that code may name
  them.
* **Every term of the local list**, one per line, matched case-insensitively.
  The list is the file `.commit-message-terms` at the repository's root, kept out
  of git (`.gitignore`), so the words it holds are never published by being
  listed. Blank lines and lines starting with `#` are ignored. No file, no terms:
  the folder rule alone applies.

Lines git itself strips (those starting with `#`) are not read.

What this does NOT check
------------------------
1. **Messages already committed.** It reads the message being written; the
   commits already in the history are the pre-push gates' business.
2. **A term split across lines or spelled differently.** It matches literal
   text, not meaning.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TERMS_FILE = REPO_ROOT / ".commit-message-terms"
PRIVATE_FOLDERS = (".claude", ".human", ".governance")
FOLDER_PATH = re.compile(r"(?<![\w.])(" + "|".join(re.escape(f) for f in PRIVATE_FOLDERS) + r")/")


def terms(file: Path = TERMS_FILE) -> list[str]:
    """The local terms, one per line; none when the file is missing."""
    if not file.is_file():
        return []
    lines = (line.strip() for line in file.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def problems(message: str, local_terms: list[str]) -> list[str]:
    """One line per offending line of [message], with what it names."""
    out: list[str] = []
    for n, line in enumerate(message.splitlines(), 1):
        if line.startswith("#"):
            continue
        folder = FOLDER_PATH.search(line)
        if folder:
            out.append(f"line {n}: names a path inside the private folder {folder.group(1)}/")
        lowered = line.lower()
        out += [
            f"line {n}: names a term of the local list ({term!r})"
            for term in local_terms
            if term.lower() in lowered
        ]
    return out


def self_test() -> list[str]:
    """Each rule must be shown to fire, and to stay quiet where it should."""
    failed: list[str] = []
    if not problems("docs: the rule in .claude/references/x.md", []):
        failed.append("a private folder's path passes")
    if problems("fix: DoctorConfig refuses .claude and .human as targets", []):
        failed.append("the bare folder names are refused")
    if not problems("docs: as the secret plan says", ["secret plan"]):
        failed.append("a term of the local list passes")
    if problems("# .claude/x is a comment git strips", []):
        failed.append("a comment line is read")
    return failed


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        failed = self_test()
        for f in failed:
            print(f"self-test FAILED: {f}", file=sys.stderr)
        print("self-test passed: 4 case(s)" if not failed else "", end="\n" if not failed else "")
        return 1 if failed else 0
    if len(argv) != 1:
        print(
            "usage: check_commit_message_terms.py <commit-msg-file> | --self-test", file=sys.stderr
        )
        return 2
    found = problems(Path(argv[0]).read_text(encoding="utf-8"), terms())
    if found:
        print(
            "The commit message names what stays private (it is public once pushed):",
            file=sys.stderr,
        )
        for line in found:
            print(f"  {line}", file=sys.stderr)
        print("Reword it; the message was saved in .git/COMMIT_EDITMSG.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
