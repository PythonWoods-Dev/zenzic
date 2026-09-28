#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Require a `!` in the commit subject when a new BREAKING entry is added.

`docs/developers/explanation/cli-contract-stability.md` lists four requirements
for shipping a breaking change, of which the first is a `!` in the commit
subject -- "what makes the change findable in history later". The requirements
were enforced by reading the page, which is how two of them were missed on
v0.31.0: `e18e855` and `8245436` are both `fix(security):`, not
`fix(security)!:`. Both are pushed, and this project does not rewrite published
history, so neither can be repaired. This check exists so the next one is caught
before it is written rather than recorded after it is.

    python3 scripts/check_breaking_change_marker.py <commit-msg-file>

Exit 0 when the subject is acceptable, 1 with a diagnosis otherwise.

The naive design is wrong, and the way it is wrong matters
-----------------------------------------------------------
Requiring `!` whenever the diff adds lines under `### Changed` or `### Removed`
false-positives on an ordinary reorganisation: moving an existing entry into
`### Changed` adds lines there without introducing any breaking change, and that
is an operation this project has actually performed. It would also fire on every
non-breaking behaviour change, since those sections are not reserved for
breaking ones.

What discriminates is the count of the marker the entries carry themselves.
Compare `BREAKING` occurrences in `HEAD:CHANGELOG.md` against the staged file and
require `!` only when the count **increases**. A move leaves it unchanged. A
genuinely new breaking entry cannot avoid raising it, because requirement 2 of
the same contract obliges the entry to carry the word.

Two limits, stated here rather than left to be discovered
---------------------------------------------------------
1. **It cannot repair a pushed commit.** This runs at `commit-msg`, before the
   commit object exists. Once a commit is pushed the only remedies are a
   force-push -- which this project does not do on a branch backing an open pull
   request -- or a record in the priority table. The two v0.31.0 commits above
   are in the second category permanently.
2. **It only runs if the hook is installed.** `pre-commit install` writes the
   `pre-commit` stage by default; the `commit-msg` stage needs
   `pre-commit install --hook-type commit-msg` and is silently absent otherwise.
   A check that is declared but not installed is not a control, and its absence
   looks exactly like a clean run. `just verify`'s git-hook check is what
   notices; this file cannot notice its own absence.

A third property, deliberate rather than a limit: `--no-verify` bypasses it, as
it bypasses every hook. The check is a guardrail against forgetting, not an
attempt to make the contract unbypassable by someone who has decided to.

And one thing it will not do quietly: if `git` cannot be located it says so on
stderr instead of returning a silent success. A check that could not measure must
not report the same thing as one that measured and found nothing.
"""

from __future__ import annotations

import re
import shutil
import subprocess  # noqa: S404 - repository tooling, not the Zero Subprocess Core
import sys
from pathlib import Path


CHANGELOG = "CHANGELOG.md"

#: Resolved once, so the subprocess calls below name a full path. A commit-msg
#: hook runs inside git, so this is present by construction; the None branch is
#: handled anyway, and handled *loudly*. Failing open in silence is the shape
#: this project keeps finding in its own gates -- a check that could not measure
#: reporting the same "fine" as one that measured and found nothing.
_GIT = shutil.which("git")

#: A CHANGELOG entry *marked* BREAKING, which is not the same as a line that
#: happens to contain the word. Requirement 2 puts the marker in the entry's bold
#: title -- `- **BREAKING - ...**`, `- **... - BREAKING**`,
#: `- **... (BREAKING for ...)**` -- so the pattern anchors to a list item and
#: stops at the closing `**`.
#:
#: Counting bare occurrences instead was wrong, and it was wrong in a way worth
#: recording: the commit that documented this very check tripped it, because the
#: CHANGELOG entry *describing* the marker says the word BREAKING twice in its
#: body. A check whose own documentation it blocks has miscounted, not caught
#: something. Case-sensitive, because "breaking change" in prose is not a marker.
_MARKER = re.compile(r"^[ \t]*[-*][ \t]+\*\*[^*]*BREAKING", re.M)

#: A Conventional Commits subject. The `!` sits after the optional scope and
#: before the colon: `fix(cli)!: ...`. Anything before the first newline is the
#: subject; comment lines that git appends are not part of it.
_SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:")


def _count_in_head() -> int:
    """BREAKING occurrences in the committed CHANGELOG, or 0 if there is none.

    A repository with no commit yet, or no CHANGELOG at HEAD, has nothing to
    compare against -- every entry in the staged file is new. Returning 0 makes
    the first commit of a CHANGELOG require the marker, which is correct.
    """
    if _GIT is None:
        return 0
    try:
        blob = subprocess.run(  # noqa: S603
            [_GIT, "show", f"HEAD:{CHANGELOG}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return 0
    if blob.returncode != 0:
        return 0
    return len(_MARKER.findall(blob.stdout))


def _count_staged() -> int | None:
    """BREAKING occurrences in the staged CHANGELOG, or None if it is not staged.

    Not staged means this commit does not touch the CHANGELOG, so it cannot be
    adding a breaking entry and there is nothing for this check to say.
    """
    if _GIT is None:
        print(
            "check_breaking_change_marker: git is not on PATH, so this commit was "
            "not checked for a breaking-change marker.",
            file=sys.stderr,
        )
        return None
    try:
        listing = subprocess.run(  # noqa: S603
            [_GIT, "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    if listing.returncode != 0 or CHANGELOG not in listing.stdout.split():
        return None
    blob = subprocess.run(  # noqa: S603
        [_GIT, "show", f":{CHANGELOG}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if blob.returncode != 0:
        return None
    return len(_MARKER.findall(blob.stdout))


def subject_of(message: str) -> str:
    """First non-comment, non-empty line of a commit message."""
    for line in message.splitlines():
        if line.startswith("#"):
            continue
        if line.strip():
            return line.strip()
    return ""


def has_marker(subject: str) -> bool:
    """True when the subject carries a Conventional Commits `!`."""
    m = _SUBJECT.match(subject)
    return bool(m and m.group("bang"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_breaking_change_marker.py <commit-msg-file>", file=sys.stderr)
        return 1

    staged = _count_staged()
    if staged is None:
        return 0

    before = _count_in_head()
    if staged <= before:
        # A move, a reword, or a removal. Not a new breaking change.
        return 0

    message = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    subject = subject_of(message)
    if has_marker(subject):
        return 0

    added = staged - before
    print(
        f"This commit adds {added} new BREAKING entr"
        f"{'y' if added == 1 else 'ies'} to {CHANGELOG}, but its subject has no `!`.\n"
        f"\n    {subject}\n\n"
        "cli-contract-stability.md requires a `!` after the type or scope --\n"
        "`fix(cli)!:`, `feat(check)!:` -- because that is what makes the change\n"
        "findable in history later. Two v0.31.0 commits shipped without it and\n"
        "cannot be repaired, because they are already pushed.\n"
        "\n"
        "Add the `!`, or -- if this is not a breaking change -- reword the\n"
        "CHANGELOG entry so it does not say BREAKING.",
        file=sys.stderr,
    )
    return 1


def self_test() -> int:
    """Prove the discriminator behaves, including where the naive design fails."""
    cases: list[tuple[str, bool]] = [
        ("fix(cli)!: drop the flag", True),
        ("feat!: new contract", True),
        ("fix(security)!: stop inheriting the mask", True),
        ("fix(cli): tell the user where an option belongs", False),
        ("fix(security): stop inheriting the mask", False),
        ("docs: reword", False),
        ("chore(deps): bump", False),
        ("", False),
        ("not a conventional subject at all", False),
        ("fix(cli) !: space before the bang", False),
    ]
    failures = 0
    for subject, expected in cases:
        if has_marker(subject) != expected:
            print(f"self-test: has_marker({subject!r}) != {expected}", file=sys.stderr)
            failures += 1

    # The marker pattern, against lines taken from this repository's real
    # CHANGELOG plus the false positive that caught this check on its own
    # documenting commit.
    marker_cases: list[tuple[str, int]] = [
        ("- **BREAKING - A File Could Downgrade a Finding**: body.", 1),
        ("- **`Z000` (`UNSUPPORTED_ENGINE`) Removed - BREAKING**:", 1),
        ("- **Z110 Code-Identity Collision (BREAKING for existing baselines)**:", 1),
        # The regression case: the word appears in the body, not the bold title.
        ("- **Mechanical Enforcement for the Marker**: refuses a new `BREAKING` entry.", 0),
        ("Some prose about a BREAKING change, not a list item at all.", 0),
        ("- an unbolded bullet mentioning BREAKING", 0),
        ("", 0),
    ]
    for text, expected in marker_cases:
        got = len(_MARKER.findall(text))
        if got != expected:
            print(f"self-test: marker count {got} != {expected} for {text!r}", file=sys.stderr)
            failures += 1

    msg = "# a comment git added\n\nfix(cli)!: real subject\n\nbody\n"
    if subject_of(msg) != "fix(cli)!: real subject":
        print(f"self-test: subject_of picked {subject_of(msg)!r}", file=sys.stderr)
        failures += 1

    if failures:
        return 1
    print(f"self-test passed: {len(cases) + len(marker_cases) + 1} case(s)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        raise SystemExit(self_test())
    raise SystemExit(main(sys.argv))
