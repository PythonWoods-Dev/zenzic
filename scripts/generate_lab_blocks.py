#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Generate the terminal blocks the family index pages include.

    python3 scripts/generate_lab_blocks.py            # write every block
    python3 scripts/generate_lab_blocks.py --check    # fail if any is stale

Each family index page under `docs/tutorials/examples/` names a `zenzic lab`
command and, until now, showed nothing of what it produces. These blocks are
that output, captured by running the command — never transcribed. Every
quote-drift correction in this cycle came from the transcribing shortcut.

**Why a text snippet and not the homepage's HTML partial.** The partial is not
reusable: 30 tags and 55 class attributes inside its terminal region alone, plus
hand-placed `terminal:begin`/`terminal:end` sentinels its parity check depends
on. Reproducing that programmatically means emitting Tailwind classes per line
type. And it would put a markup layer between the command and the check: the
existing extraction decodes three HTML entities and not `&lt;`/`&gt;`, while the
`z1xx` family's own output carries 11 lines containing `<` and `>` — the caret
rows echoing `<a href=…>`. The transformation would break exactly where this
content lives. A `.txt` snippet is compared to real output with nothing in
between.

**Why outside `docs/`.** A file under `docs/` is scanned as documentation and
copied into the built site. These are build inputs, not pages.

**The banner is stripped** because it carries the version string. Left in, every
release would make every block disagree with real output, and the parity test
would fail for a reason that has nothing to do with the content it guards.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SNIPPET_DIR = REPO_ROOT / "snippets"

#: Block file name -> the argv that produces it. This mapping is the single
#: registration point: the parity test imports it and asserts it matches the
#: files on disk IN BOTH DIRECTIONS, so a block with no entry fails the suite
#: rather than shipping unverified, and an entry with no block fails too.
BLOCKS: dict[str, tuple[str, ...]] = {
    "lab-z1xx.txt": ("lab", "z101"),
    "lab-z2xx.txt": ("lab", "z201"),
    "lab-z4xx.txt": ("lab", "z405"),
    "lab-z5xx.txt": ("lab", "z501"),
    "lab-z6xx.txt": ("lab", "z601"),
}

#: Families that get no block, each with its reason. Recorded here rather than
#: left as a silent absence: five blocks for seven families is a number someone
#: would otherwise have to re-derive.
#:
#: `z3xx-references` names no lab command at all.
#:
#: `z0xx-core` names one, and its output cannot be published. `zenzic lab z001`
#: demonstrates a config parse failure, and pydantic reports the offending file
#: by ABSOLUTE path -- so the block embedded the home directory of whatever
#: machine generated it. It passed locally and failed on CI for exactly that
#: reason, which is the correct outcome: the parity test compared a depicted
#: line against real output and the paths differed. Marking the line volatile
#: would have hidden the machine path in the published block rather than
#: removing it, and rewriting the path would put a line in the file that no
#: command printed -- the transcription this whole mechanism exists to avoid.
NO_COMMAND = ("z3xx-references", "z0xx-core")


def _zenzic() -> Path:
    return Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")


def capture(argv: tuple[str, ...]) -> str:
    """Real output of one command, banner removed, trailing blanks collapsed."""
    proc = subprocess.run(  # noqa: S603
        [str(_zenzic()), *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # Emoji forced on: the blocks depict what a developer sees in their own
        # terminal, and `zenzic.core.ui` swaps in ASCII whenever CI is set.
        env={**os.environ, "COLUMNS": "80", "NO_COLOR": "1", "CI": ""},
    )
    lines = proc.stdout.splitlines()
    # Drop the banner: everything up to and including its closing border.
    for i, line in enumerate(lines):
        if line.startswith("╰"):
            lines = lines[i + 1 :]
            break
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    # Trailing whitespace is stripped because the repository's pre-commit hook
    # strips it anyway, and a generator that writes what a hook then rewrites
    # produces a file that is stale the instant it is committed -- `--check`
    # would report drift forever, for a difference no reader can see. Rich pads
    # some lines to the console width, so this is not hypothetical: six of six
    # blocks were rewritten by the hook on their first commit.
    return "\n".join(line.rstrip() for line in lines) + "\n"


#: Lines whose content legitimately varies between runs. Throughput and elapsed
#: time are machine-dependent, so a byte-for-byte `--check` would fail on every
#: invocation -- which is how the first version of this script behaved, making
#: the check unusable rather than strict. The written block keeps the real
#: values; only the comparison ignores them, exactly as the parity test does.
_VOLATILE_TOKENS = ("files/s", "s •", "scanned •")


def comparable(text: str) -> list[str]:
    """The lines of *text* a stale-check may legitimately compare."""
    return [
        line
        for line in text.splitlines()
        if line.strip() and not any(token in line for token in _VOLATILE_TOKENS)
    ]


def main() -> int:
    check = "--check" in sys.argv
    SNIPPET_DIR.mkdir(exist_ok=True)
    stale: list[str] = []
    for name, argv in sorted(BLOCKS.items()):
        target = SNIPPET_DIR / name
        fresh = capture(argv)
        if check:
            current = target.read_text(encoding="utf-8") if target.is_file() else ""
            if comparable(current) != comparable(fresh):
                stale.append(name)
            continue
        target.write_text(fresh, encoding="utf-8")
        print(f"  wrote {target.relative_to(REPO_ROOT)}  ({len(fresh.splitlines())} lines)")
    if check:
        if stale:
            print(
                f"FAILED: {len(stale)} block(s) differ from real output: {stale}\n"
                "  Regenerate with: just lab-blocks",
                file=sys.stderr,
            )
            return 1
        print(f"lab blocks: {len(BLOCKS)} block(s) match real output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
