# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Compare the findings Zenzic produces on two Python interpreters.

**Why this exists.** `pathlib.PurePath.suffix` changed semantics in Python 3.12 -- it
gained a `name.lstrip('.')` step. `is_emitted_verbatim` read it, and that function decides
which links receive the URL-depth correction, so the same corpus analysed on 3.10 and on
3.14 could produce different findings. Determinism is this project's first Tier-0
invariant, and it had been violated across the supported version range since that function
was written.

**Nothing could see it.** Every other mechanism here compares the engine against itself or
against a fixture -- the CLI/LSP parity guard, the schema contract, the documented-command
gate, mutation testing. None compares the engine against *itself on another interpreter*,
which is the only instrument that finds this class. It surfaced by accident, from a
performance profile on a Windows runner, via a test written to protect an unrelated
optimisation.

**How it works.** Two modes:

* ``--emit <file>``   run the engine over the example gallery and write a normalised
  findings digest as JSON. Called once per interpreter.
* ``--compare a b``   diff two digests and fail if they differ.

The cost is one JSON dump per existing matrix leg plus a diff. It adds no test run: CI
already executes 3.10 and 3.14.

**What it cannot catch, and this must stay written down.** It compares findings over the
fixtures in `examples/`. A divergence in an input shape no fixture contains is invisible to
it -- which is exactly where the defect that motivated it lived: of the 35 inputs where the
two interpreters disagree, **zero** appear in this project's own corpus, and no real path
part even has the shape. So this gate would not have caught the bug it was built for. It
catches the *next* one, if that one touches a shape a fixture exercises. An honest 80%
beats the zero that preceded it, and the limit is stated so nobody reads a green run as
proof of determinism.

A fuller instrument would generate inputs rather than read fixtures -- property-based
differential testing across interpreters. That is a larger build and is recorded as a
backlog item rather than pretended to here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

#: Keys compared per finding. `message` is included deliberately: a divergence that
#: changes only the wording is still a divergence a consumer's tooling can see.
FIELDS = ("code", "rel_path", "line_no", "severity", "message")


def _digest_for(example: Path) -> list[dict[str, object]]:
    """Findings for one example directory, normalised and ordered."""
    proc = subprocess.run(  # noqa: S603
        # The console script rather than `-m`: the package has no `__main__`, and the
        # binary is what a user runs. It sits beside the running interpreter, which is
        # what ties this measurement to the version under test.
        [str(Path(sys.executable).with_name("zenzic")), "check", "all", "--format", "json"],
        cwd=example,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not proc.stdout.strip():
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # A example that emits no JSON object is a legitimate outcome under
        # Silent-on-Success; a malformed one is not, and saying which matters.
        return [
            {
                "code": "__UNPARSEABLE__",
                "rel_path": example.name,
                "line_no": 0,
                "severity": "error",
                "message": proc.stdout[:200],
            }
        ]
    out = [{k: f.get(k) for k in FIELDS} for f in payload.get("findings", [])]
    return sorted(out, key=lambda f: tuple(str(f[k]) for k in FIELDS))


def emit(target: Path) -> int:
    """Write the digest for every example, tagged with the interpreter."""
    if not EXAMPLES.is_dir():
        print(f"no examples/ directory at {EXAMPLES}", file=sys.stderr)
        return 2
    corpora = sorted(p for p in EXAMPLES.iterdir() if (p / ".zenzic.toml").is_file())
    digest = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "examples": {p.name: _digest_for(p) for p in corpora},
    }
    total = sum(len(v) for v in digest["examples"].values())
    target.write_text(json.dumps(digest, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"interpreter-determinism digest: {len(corpora)} example(s), {total} finding(s), "
        f"python {digest['python']} -> {target}"
    )
    if total == 0:
        # A comparison of two empty digests proves nothing, and a silent zero here
        # would make this gate permanently and meaninglessly green -- a zero result is
        # evidence only once the instrument has been shown capable of a non-zero one.
        print(
            "FAILED: the digest is empty, so a comparison against it would be vacuous. "
            "Either examples/ carries no fixture with a .zenzic.toml, or the engine "
            "emitted nothing anywhere.",
            file=sys.stderr,
        )
        return 1
    return 0


def compare(first: Path, second: Path) -> int:
    a = json.loads(first.read_text(encoding="utf-8"))
    b = json.loads(second.read_text(encoding="utf-8"))
    if a["python"] == b["python"]:
        print(
            f"FAILED: both digests are from Python {a['python']}. Comparing an "
            "interpreter against itself cannot detect a version divergence.",
            file=sys.stderr,
        )
        return 1
    problems: list[str] = []
    for name in sorted(set(a["examples"]) | set(b["examples"])):
        fa, fb = a["examples"].get(name), b["examples"].get(name)
        if fa is None or fb is None:
            problems.append(f"{name}: present under only one interpreter")
            continue
        if fa != fb:
            only_a = [f for f in fa if f not in fb]
            only_b = [f for f in fb if f not in fa]
            problems.append(
                f"{name}: {len(only_a)} finding(s) only on {a['python']}, "
                f"{len(only_b)} only on {b['python']}"
            )
            for f in (only_a + only_b)[:4]:
                problems.append(
                    f"    {f['code']} {f['rel_path']}:{f['line_no']} {f['message'][:90]}"
                )
    total = sum(len(v) for v in a["examples"].values())
    if problems:
        print(
            f"FAILED: the engine is not deterministic across Python {a['python']} and "
            f"{b['python']}:",
            file=sys.stderr,
        )
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(
        f"interpreter determinism: identical findings on Python {a['python']} and "
        f"{b['python']} across {len(a['examples'])} example(s), {total} finding(s). "
        "Limit: fixtures only — a divergence in a shape no example contains is invisible "
        "here (see this file's docstring)."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit", type=Path, help="write this interpreter's digest here")
    parser.add_argument("--compare", type=Path, nargs=2, help="diff two digests")
    args = parser.parse_args()
    if args.emit:
        return emit(args.emit)
    if args.compare:
        return compare(*args.compare)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
