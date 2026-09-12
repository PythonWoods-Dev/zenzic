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
mutation run actually uses.

**Raised to 95.7%** (400 killed, 18 survived, 0 with no covering test) by a
full triage of all 133 survivors then measured against this floor.
Two more already-existing, already-correct test files were in scope but not in this list
(``test_forbidden_term_span_overlap.py``, whose thorough overlap-suppression
tests alone closed 12 of ``scan_security_findings``'s 24 survivors) and one new
file was added (``tests/test_credential_scanner_mutation_survivors.py``, 41
tests) closing the rest: dead branches with zero coverage anywhere in the suite
(the linear fallback of ``scan_line_for_forbidden_terms`` — the exact path
``zenzic guard scan``, the pre-commit hook itself, always uses; the base64
speculative-decode success path), unasserted ``SecurityFinding`` fields on
otherwise-tested happy paths, and several ``continue``-vs-``break`` branch
mutants where an already-seen secret type or an ambiguous credential line
would otherwise have silently aborted scanning the rest of a line or file. No
currently-shipped defect was found in the process — every gap was a missing
assertion or an unexercised branch, not wrong behavior.

The 18 remaining survivors are documented, individually, as equivalent
mutants in that triage's own report and in this module's test file — not
gated further because no real test can distinguish them from the code they
mutate (an unreachable initial sentinel, a Python stdlib default that already
matches the literal being removed, a window whose truncation can never reach
content a real signature needs, and similar). This is why the floor sits at
95.7% rather than 100%: the remaining gap is structural, not a queue of
undone work.

Gating at 90% before this triage would have failed every build; gating at the
measured value and calling the invariant satisfied would have been a
workaround that changes what is shown rather than what is true. So this gate
is a **ratchet**: it prevents the score from regressing, and now that the
measured value clears the documented 90% target, the invariant is genuinely
met rather than merely tracked.

Raise ``FLOOR`` whenever the score improves. Never lower it to make a build pass.

Why the raw survivor count is gated too
----------------------------------------
The percentage alone cannot catch every regression: a change that adds many new
mutants to the module, almost all freshly killed but a few newly surviving,
dilutes those new survivors into a score that can stay flat or even rise while
clearing ``FLOOR``. ``MAX_SURVIVORS`` gates the raw count against the 18-mutant
baseline the floor was measured at, so a genuinely new survivor fails the gate
even when the percentage alone would not have noticed.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 - build tooling, not the Zero Subprocess Core
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATS = REPO_ROOT / "mutants" / "mutmut-cicd-stats.json"

#: Measured floor. See the module docstring before changing this.
FLOOR = 95.7
#: The number the Tier-0 invariant claims. Printed, not enforced, until it is real.
INVARIANT_TARGET = 90.0
#: The survivor count the 95.7% floor was measured at (18, all individually
#: documented as equivalent mutants — see the module docstring). The
#: percentage alone cannot catch every regression: a change that adds many
#: new mutants, most freshly killed but a few newly surviving, can dilute
#: those new survivors into a score that still clears FLOOR. Gating the raw
#: count too closes that gap — raise this only alongside a real triage that
#: documents each new equivalent mutant by name, the same discipline FLOOR
#: already follows.
MAX_SURVIVORS = 18


def _run(*argv: str) -> int:
    # S603: the argv is this module's own literals plus sys.executable — no user input
    # reaches it. ADR-002 (Zero Subprocess) binds src/zenzic/core/, not build tooling;
    # a mutation runner that cannot start a process would have nothing to run.
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", *argv], cwd=REPO_ROOT, check=False
    ).returncode


def _decide(stats: dict[str, int]) -> tuple[int, list[str]]:
    """Pure decision logic, isolated from the subprocess/file-I/O in ``main()``
    so it is directly unit-testable (see ``tests/test_mutation_gate.py``).

    Returns ``(exit_code, messages)`` — messages are the exact lines ``main()``
    prints, in order; callers do not need to also re-derive the score.
    """
    killed, survived = stats["killed"], stats["survived"]
    decided = killed + survived
    if decided == 0:
        return 2, ["mutation gate: no mutant was decided — the harness ran on nothing"]

    # Rounded to the same 1-decimal precision FLOOR itself is documented and
    # compared at: the raw ratio for the exact measurement FLOOR was set from
    # (400 killed, 18 survived) is 95.6938...%, which is < 95.7 by strict
    # floating-point comparison even though it rounds to the documented
    # figure. Comparing raw-vs-rounded made the gate fail its own baseline.
    score = round(100.0 * killed / decided, 1)
    messages = [
        f"mutation score: {score:.1f}%  "
        f"({killed} killed, {survived} survived, {stats['no_tests']} with no covering test)",
        f"floor: {FLOOR:.1f}%   Tier-0 invariant target: {INVARIANT_TARGET:.1f}%",
    ]

    if score < FLOOR:
        messages.append(
            f"FAILED: mutation score {score:.1f}% is below the {FLOOR:.1f}% floor. "
            "A test that used to kill a mutant no longer does."
        )
        return 1, messages
    if survived > MAX_SURVIVORS:
        messages.append(
            f"FAILED: {survived} mutants survived, above the {MAX_SURVIVORS} "
            "documented-equivalent baseline, even though the score clears the "
            "floor. A change added new mutants that diluted new survivors "
            "into an unchanged-or-higher percentage — kill the new "
            "survivor(s) with a real test, or document them as equivalent "
            "and raise MAX_SURVIVORS to match."
        )
        return 1, messages
    if score < INVARIANT_TARGET:
        messages.append(
            f"note: {INVARIANT_TARGET - score:.1f} points below the documented invariant; "
            "the gap is tracked, not gated."
        )
    return 0, messages


def main() -> int:
    # mutmut exits non-zero when mutants survive, which is the normal state here;
    # the gate is the score, so its exit code is deliberately not propagated.
    _run("mutmut", "run")
    if _run("mutmut", "export-cicd-stats") != 0 or not STATS.is_file():
        print("mutation gate: mutmut produced no stats file", file=sys.stderr)
        return 2

    stats = json.loads(STATS.read_text(encoding="utf-8"))
    exit_code, messages = _decide(stats)
    stream = sys.stderr if exit_code != 0 else sys.stdout
    for message in messages:
        print(
            message, file=stream if message.startswith(("FAILED", "mutation gate:")) else sys.stdout
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
