# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The Z2xx security tier has exactly one authority, and nothing restates it.

``_shared.py``'s SARIF emitter decided which findings make a run
``executionSuccessful: false`` with a hand-written ``{"Z201", ..., "Z205"}``
literal — a second copy of the security tier with nothing enforcing agreement.
It matched the real set, so nothing was wrong *today*; but a future ``Z206``
added to the tier would silently keep SARIF reporting the run as successful,
and SARIF is what CI dashboards and code-scanning integrations read.

Neither existing constant could serve as the alias: ``NON_SUPPRESSIBLE_CODES``
is broader (it carries the ``Z110``/``Z111`` config-abort codes, which are not
security findings) and ``SECURITY_FINDING_CODES`` is narrower (only the two
codes the credential scanner itself emits). So the tier gets its own SSoT,
``SECURITY_TIER_CODES``, and ``NON_SUPPRESSIBLE_CODES`` is composed from it —
one place to add a code, every consumer follows.
"""

from __future__ import annotations

import re
from pathlib import Path

from zenzic.core.codes import NON_SUPPRESSIBLE_CODES, SECURITY_TIER_CODES


_SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"

#: Any brace literal, so its Z2xx members can be compared against the real tier.
_BRACE_LITERAL = re.compile(r"\{[^{}]*\}")
_Z2XX = re.compile(r"\"(Z2\d\d)\"")


def test_security_tier_is_the_full_z2xx_set() -> None:
    assert SECURITY_TIER_CODES == frozenset({"Z201", "Z202", "Z203", "Z204", "Z205"})


def test_non_suppressible_is_composed_from_the_tier_not_a_parallel_copy() -> None:
    """Composition, so a new tier code cannot be added to only one of them."""
    assert SECURITY_TIER_CODES < NON_SUPPRESSIBLE_CODES
    assert NON_SUPPRESSIBLE_CODES - SECURITY_TIER_CODES == frozenset({"Z110", "Z111"})


def test_no_module_restates_the_whole_security_tier_as_a_literal() -> None:
    """Fix the class, not the instance: catch a restatement anywhere in Core.

    Only a literal carrying the *entire* tier counts. A proper subset is a
    different concept, not a copy — ``scanner.SECURITY_FINDING_CODES`` is
    ``{Z201, Z204}``, the codes the credential scanner itself emits, while
    ``Z202``/``Z203``/``Z205`` come from the traversal and scheme checks. Forcing
    that to alias the tier would couple two unrelated ideas and change behaviour;
    it is deliberately left alone.
    """
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name == "codes.py":  # the SSoT itself is allowed to spell them out
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for literal in _BRACE_LITERAL.findall(line):
                if frozenset(_Z2XX.findall(literal)) == SECURITY_TIER_CODES:
                    rel = path.relative_to(_SRC.parent.parent)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "the Z2xx security tier is restated as a literal instead of imported from "
        "codes.SECURITY_TIER_CODES — a copy that agrees today drifts tomorrow:\n  "
        + "\n  ".join(offenders)
    )
