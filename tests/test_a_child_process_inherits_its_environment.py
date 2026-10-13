# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A subprocess launched with an environment built from scratch cannot start on
Windows.

Measured on the Windows runner, 2026-09-19: four tests reported

    Fatal Python error: _Py_HashRandomization_Init: failed to get random numbers
    to initialize Python

and pytest attributed the failure to the product — one of them asserting that
"a declared engine with no configuration was replaced in silence", which was not
true. **The interpreter never started.** Python's hash randomisation seeds from
`CryptGenRandom`, which needs `SystemRoot`; an `env=` dict written as a literal
drops it, along with every other variable the child needs.

The shape is worse than an ordinary failure: a test that cannot run the product
is indistinguishable from one that ran it and found a defect. The CI was
reporting defects that did not exist, and until it stopped it could neither
confirm nor refute any fix.

Every test in this suite that predates those four inherits the environment
(`{**os.environ, ...}`). The convention existed; four new files did not follow
it, and the local gate runs on Linux where a fabricated `PATH` happens to work.
So it is a check rather than a habit.

**What it looks for**: `env=` passed to `subprocess.run`/`Popen`/`check_output`
with a dictionary literal that does not unpack `os.environ`.
"""

from __future__ import annotations

import ast
from pathlib import Path


_TESTS = Path(__file__).resolve().parent
_SCRIPTS = _TESTS.parent / "scripts"
_LAUNCHERS = {"run", "Popen", "check_output", "check_call", "call"}


def _inherits(node: ast.Dict) -> bool:
    """True when the literal unpacks something — `{**os.environ, ...}`."""
    return any(key is None for key in node.keys)


def _offenders(roots: list[Path]) -> list[str]:
    found: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for py in sorted(root.rglob("*.py")):
            source = py.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call):
                    continue
                func = call.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name not in _LAUNCHERS:
                    continue
                for kw in call.keywords:
                    if kw.arg != "env" or not isinstance(kw.value, ast.Dict):
                        continue
                    if not _inherits(kw.value):
                        rel = py.relative_to(_TESTS.parent).as_posix()
                        found.append(f"{rel}:{kw.value.lineno}")
    return found


def test_no_subprocess_is_launched_with_a_fabricated_environment() -> None:
    offenders = _offenders([_TESTS, _SCRIPTS])
    assert not offenders, (
        "a subprocess receives an environment built from scratch, so it loses "
        "`SystemRoot` and the interpreter cannot start on Windows:\n  "
        + "\n  ".join(offenders)
        + "\nUse `{**os.environ, ...}` and override only what the test needs."
    )


def test_the_detector_finds_a_fabricated_environment() -> None:
    """A zero-result sweep is not evidence until the instrument has been shown
    to find something."""
    module = ast.parse(
        'subprocess.run(["x"], env={"NO_COLOR": "1", "PATH": "/usr/bin"})\n'
        'subprocess.run(["x"], env={**os.environ, "NO_COLOR": "1"})\n'
    )
    calls = [n for n in ast.walk(module) if isinstance(n, ast.Call) and n.keywords]
    literals = [
        kw.value
        for c in calls
        for kw in c.keywords
        if kw.arg == "env" and isinstance(kw.value, ast.Dict)
    ]

    assert len(literals) == 2
    assert not _inherits(literals[0])  # the shape that broke the runner
    assert _inherits(literals[1])  # the shape every other test uses
