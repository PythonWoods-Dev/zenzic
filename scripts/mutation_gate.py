#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Mutation gate for the credential scanner.

Runs mutmut over ``src/zenzic/core/credentials.py`` against the suites that
exercise it, reads mutmut's own CI/CD stats export, and fails when the mutation
score drops below the recorded floor.

Why a floor and not the invariant's number
------------------------------------------
The Tier-0 documentation claims "Mutation >= 90%". The first real run of this
harness measured **56.5%** (231 killed, 178 survived, 9 with no covering test).
The harness had been configured in ``pyproject.toml`` for some time but was
never wired into ``just`` or CI, so no score had ever been computed — and with
its original ``tests/`` selection it could not even collect, because suites that
read repository artifacts outside ``also_copy`` fail inside mutmut's sandbox.

**Raised to 68.2%** (285 killed, 133 survived, 0 with no covering test) after
adding two already-existing, self-contained unit-test files
(``test_placeholder_classification.py``, ``test_credentials_obfuscation.py``) to
``pytest_add_cli_args_test_selection`` in ``pyproject.toml`` — both import
``credentials.py`` internals directly and already covered real gaps (e.g. the
``_is_likely_placeholder`` case-fold direction, ``_normalize_line_for_scan``'s
dangerous-character fast-path skip), they were simply never in the list the
mutation run actually uses. Not every remaining survivor is a real gap of this
shape; the rest is tracked as scheduled work, not gated further in this pass.

Gating at 90% today would fail every build; gating at the measured value and
calling the invariant satisfied would be a workaround that changes what is shown
rather than what is true. So this gate is a **ratchet**: it prevents the score
from regressing while the gap to 90% is closed as its own work, and it prints
the gap on every run so it cannot be forgotten.

Raise ``FLOOR`` whenever the score improves. Never lower it to make a build pass.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - build tooling, not the Zero Subprocess Core
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATS = REPO_ROOT / "mutants" / "mutmut-cicd-stats.json"

#: Measured floor. See the module docstring before changing this.
FLOOR = 67.0
#: The number the Tier-0 invariant claims. Printed, not enforced, until it is real.
INVARIANT_TARGET = 90.0


def _run(*argv: str) -> int:
    # S603: the argv is this module's own literals plus sys.executable — no user input
    # reaches it. ADR-002 (Zero Subprocess) binds src/zenzic/core/, not build tooling;
    # a mutation runner that cannot start a process would have nothing to run.
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", *argv], cwd=REPO_ROOT, check=False
    ).returncode


def main() -> int:
    # mutmut exits non-zero when mutants survive, which is the normal state here;
    # the gate is the score, so its exit code is deliberately not propagated.
    _run("mutmut", "run")
    if _run("mutmut", "export-cicd-stats") != 0 or not STATS.is_file():
        print("mutation gate: mutmut produced no stats file", file=sys.stderr)
        return 2

    stats = json.loads(STATS.read_text(encoding="utf-8"))
    killed, survived = stats["killed"], stats["survived"]
    decided = killed + survived
    if decided == 0:
        print("mutation gate: no mutant was decided — the harness ran on nothing", file=sys.stderr)
        return 2

    score = 100.0 * killed / decided
    print(
        f"mutation score: {score:.1f}%  "
        f"({killed} killed, {survived} survived, {stats['no_tests']} with no covering test)"
    )
    print(f"floor: {FLOOR:.1f}%   Tier-0 invariant target: {INVARIANT_TARGET:.1f}%")

    if score < FLOOR:
        print(
            f"FAILED: mutation score {score:.1f}% is below the {FLOOR:.1f}% floor. "
            "A test that used to kill a mutant no longer does.",
            file=sys.stderr,
        )
        return 1
    if score < INVARIANT_TARGET:
        print(
            f"note: {INVARIANT_TARGET - score:.1f} points below the documented invariant; "
            "the gap is tracked, not gated."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
