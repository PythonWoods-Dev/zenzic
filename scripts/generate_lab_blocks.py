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
FAMILY_DIR = REPO_ROOT / "docs" / "tutorials" / "examples"

#: Block file name -> the argv that produces it. This mapping is the single
#: registration point: the parity test imports it and asserts it matches the
#: files on disk IN BOTH DIRECTIONS, so a block with no entry fails the suite
#: rather than shipping unverified, and an entry with no block fails too.
BLOCKS: dict[str, tuple[str, ...]] = {
    "lab-z1xx.txt": ("lab", "z101"),
    "lab-z2xx.txt": ("lab", "z201"),
    "lab-z3xx.txt": ("lab", "z302"),
    "lab-z4xx.txt": ("lab", "z405"),
    "lab-z5xx.txt": ("lab", "z501"),
    "lab-z6xx.txt": ("lab", "z601"),
}

#: Families that get no block, each with the KIND of its reason, which the
#: parity test verifies mechanically -- the family directories are read from
#: disk, every one must be here or in BLOCKS, and a reason that stopped being
#: true fails the suite. Until 2026-09-17 this was a tuple nothing imported, and
#: its entry for `z3xx-references` ("names no lab command at all") described the
#: page while `zenzic lab --list` carried Z301, Z302 and Z303: a block was one
#: registration away and no check could say so.
#:
#: Kinds: `no-lab-command` -- the lab lists no code of the family (checked
#: against `zenzic lab --list`); `unpublishable-path` -- the family's lab output
#: embeds an absolute filesystem path (checked against real output).
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
NO_COMMAND: dict[str, str] = {
    "z0xx-core": "unpublishable-path",
}

#: Code bands with no family page and no block, and why. `Z901`, `Z902` and
#: `Z906` are status codes: penalty 0.0, category None, printed as a HALT or a
#: skipped-audit notice rather than emitted into findings[], so there is no
#: scenario to run and no page to hold one. The test checks each claim: no
#: `Z9` code in `lab --list`, no family directory, penalty 0 in the registry.
NO_FAMILY_PAGE: dict[str, str] = {
    "z9xx": "status codes (Z901 RULE_ENGINE_ERROR, Z902 RULE_TIMEOUT, Z906 NO_FILES_FOUND): "
    "penalty 0.0, never in findings[], no lab command, no family page",
}


def families() -> list[str]:
    """The family directories under docs/tutorials/examples, read from disk."""
    return sorted(p.name for p in FAMILY_DIR.iterdir() if p.is_dir() and p.name.startswith("z"))


def family_block(family_dir: str) -> str:
    """`z1xx-links` -> `lab-z1xx.txt`."""
    return f"lab-{family_dir.split('-')[0]}.txt"


#: Marker regions in Markdown that GitHub renders raw, where `--8<--` cannot
#: reach: the region between `<!-- zenzic:block NAME:begin -->` and
#: `<!-- zenzic:block NAME:end -->` is rewritten from the command's real output
#: (`--regions`) and compared to it by `--check` and by the parity test. The
#: README's four-file capture had been transcribed once and never regenerated:
#: 297 files where there were 335, a message that had since gained a suffix.
#: Each entry: (argv, working directory, extra environment).
REGIONS: dict[str, dict[str, tuple[tuple[str, ...], Path, dict[str, str]]]] = {
    "README.md": {
        "readme-capture": (
            ("check", "all", "docs", "--no-header"),
            REPO_ROOT / "tests" / "sandboxes" / "readme_capture",
            {"CI": "1"},  # ASCII glyphs, as an Actions log renders them
        ),
    },
}


def _zenzic() -> Path:
    return Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")


def capture(
    argv: tuple[str, ...], *, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None
) -> str:
    """Real output of one command, banner removed, trailing blanks collapsed."""
    proc = subprocess.run(  # noqa: S603
        [str(_zenzic()), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # Emoji forced on: the blocks depict what a developer sees in their own
        # terminal, and `zenzic.core.ui` swaps in ASCII whenever CI is set. A
        # region may override this (the README depicts an Actions log).
        env={**os.environ, "COLUMNS": "80", "NO_COLOR": "1", "CI": "", **(env or {})},
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


def region_bounds(text: str, name: str) -> tuple[int, int] | None:
    """Character offsets of the fenced text inside a named marker region."""
    begin = f"<!-- zenzic:block {name}:begin -->"
    end = f"<!-- zenzic:block {name}:end -->"
    i = text.find(begin)
    j = text.find(end, i)
    if i < 0 or j < 0:
        return None
    fence_open = text.find("```text\n", i, j)
    fence_close = text.rfind("```", i, j)
    if fence_open < 0 or fence_close <= fence_open:
        return None
    return fence_open + len("```text\n"), fence_close


def region_text(text: str, name: str) -> str:
    bounds = region_bounds(text, name)
    return text[bounds[0] : bounds[1]] if bounds else ""


def main() -> int:
    check = "--check" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    SNIPPET_DIR.mkdir(exist_ok=True)
    stale: list[str] = []
    for name, argv in sorted(BLOCKS.items()):
        if only and name not in only:
            continue
        target = SNIPPET_DIR / name
        fresh = capture(argv)
        if check:
            current = target.read_text(encoding="utf-8") if target.is_file() else ""
            if comparable(current) != comparable(fresh):
                stale.append(name)
            continue
        target.write_text(fresh, encoding="utf-8")
        print(f"  wrote {target.relative_to(REPO_ROOT)}  ({len(fresh.splitlines())} lines)")
    for rel, regions in sorted(REGIONS.items()):
        path = REPO_ROOT / rel
        text = path.read_text(encoding="utf-8")
        for name, (argv, cwd, env) in sorted(regions.items()):
            if only and name not in only:
                continue
            fresh = capture(argv, cwd=cwd, env=env)
            bounds = region_bounds(text, name)
            if bounds is None:
                print(f"FAILED: {rel} has no region named {name!r}", file=sys.stderr)
                return 1
            if check:
                if comparable(text[bounds[0] : bounds[1]]) != comparable(fresh):
                    stale.append(f"{rel}#{name}")
                continue
            text = text[: bounds[0]] + fresh + text[bounds[1] :]
            print(f"  rewrote {rel} region {name}  ({len(fresh.splitlines())} lines)")
        if not check:
            path.write_text(text, encoding="utf-8")
    if check:
        if stale:
            print(
                f"FAILED: {len(stale)} block(s) differ from real output: {stale}\n"
                "  Regenerate with: just lab-blocks",
                file=sys.stderr,
            )
            return 1
        n_regions = sum(len(r) for r in REGIONS.values())
        print(f"lab blocks: {len(BLOCKS)} block(s) and {n_regions} region(s) match real output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
