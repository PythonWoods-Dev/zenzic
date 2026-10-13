# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every gallery fixture demonstrates the code it is named after.

The cheap version of this check compares `CODE_DEFINITIONS` against the names of
the directories under `examples/`. It sees a code with no fixture, and it is
blind to the failure that matters more: a directory named `z106-circular-link`
whose content fires only `Z502` satisfies it completely. A fixture that
demonstrates the wrong thing is worse than a missing one, because the missing
one is visible in a count.

So this runs each fixture and requires its own code in the output — the same
shape as the terminal-block parity test, and the reason the coverage is real
rather than nominal.

WHAT IT STILL CANNOT REACH, stated rather than discovered later:

1. **It cannot tell a good demonstration from a technically-correct one.** A
   fixture firing its code for an incidental reason passes. The code is present;
   whether it is present for the reason the card describes is a reading.
2. **It says nothing about the four codes with no fixture.** Those are recorded
   in `MUST_HAVE_NO_FIXTURE` below with their reasons, and the set is asserted
   in both directions so a code cannot be quietly added to it.
3. **It runs the aggregate command.** A code reachable only through a per-check
   subcommand, or only with a flag no fixture sets, would read as missing. Four
   such codes are in ``CANNOT_BE_OBSERVED`` — three config-load errors that
   abort before a findings payload exists, and one needing real network I/O.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zenzic.core.codes import CODE_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"
ZENZIC = Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")

#: Codes that cannot have a gallery fixture, each with the reason it cannot.
#: Asserted in BOTH directions below: a code here that gains a fixture fails,
#: and a code missing a fixture that is not here fails. The set is the record,
#: so "why is there no example for this?" has an answer in the repository
#: rather than in someone's memory.
MUST_HAVE_NO_FIXTURE: dict[str, str] = {
    "Z901": (
        "fires when a plugin rule raises. Demonstrating it requires shipping "
        "deliberately broken plugin code inside a fixture the gallery presents "
        "as exemplary."
    ),
    "Z902": (
        "fires when a worker stalls past a time limit. A real timeout is "
        "non-deterministic, which the gallery's fixtures may not be."
    ),
    "Z906": (
        "requires a docs directory containing no Markdown at all. git cannot "
        "track an empty directory, and any placeholder file makes the run "
        "report Z405 instead — verified. It is also printed and then returned "
        "on, so it never reaches findings[], JSON or SARIF."
    ),
}


#: Codes whose fixture exists and is correct, but which cannot be OBSERVED by
#: `check all --format json` — a different thing from having no fixture. Each
#: was found by this check on its first run, not anticipated.
CANNOT_BE_OBSERVED: dict[str, str] = {
    "Z001": "a config-load error: the run aborts before any findings payload is built",
    "Z110": "a config-load error: same path as Z001",
    "Z111": "a config-load error: same path as Z001",
    "Z109": (
        "external link validation is opt-in (`--links`) and makes real network "
        "requests, which a fixture run must not depend on"
    ),
}


def _fixture_dirs() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for d in sorted(EXAMPLES.iterdir()):
        if not d.is_dir() or not (d / ".zenzic.toml").exists():
            continue
        prefix = d.name.split("-")[0].upper()
        if prefix in CODE_DEFINITIONS:
            out[prefix] = d
    return out


def test_every_code_has_a_fixture_or_a_recorded_reason() -> None:
    """Both directions, because each is a different kind of drift."""
    fixtures = _fixture_dirs()
    missing = sorted(set(CODE_DEFINITIONS) - set(fixtures) - set(MUST_HAVE_NO_FIXTURE))
    assert not missing, (
        f"code(s) with no gallery fixture and no recorded reason: {missing}. "
        "Add a fixture, or add the code to MUST_HAVE_NO_FIXTURE with why it cannot have one."
    )
    contradicted = sorted(set(MUST_HAVE_NO_FIXTURE) & set(fixtures))
    assert not contradicted, (
        f"{contradicted} are recorded as impossible to demonstrate and have a fixture. "
        "One of the two is wrong."
    )
    stale = sorted(set(MUST_HAVE_NO_FIXTURE) - set(CODE_DEFINITIONS))
    assert not stale, (
        f"MUST_HAVE_NO_FIXTURE names {stale}, which are not codes any more. "
        "A removed code leaves its exemption behind unless this fails."
    )


def test_the_unobservable_set_names_only_real_codes_with_real_fixtures() -> None:
    """The exemption list is itself checked, in both directions.

    An exemption that outlives its code, or names a code with no fixture, turns
    this file into a list of excuses. Both fail here.
    """
    fixtures = _fixture_dirs()
    stale = sorted(c for c in CANNOT_BE_OBSERVED if c not in CODE_DEFINITIONS)
    assert not stale, f"CANNOT_BE_OBSERVED names non-codes: {stale}"
    unfixtured = sorted(c for c in CANNOT_BE_OBSERVED if c not in fixtures)
    assert not unfixtured, (
        f"{unfixtured} are exempted from observation but have no fixture at all — "
        "they belong in MUST_HAVE_NO_FIXTURE, which is a different claim."
    )
    overlap = sorted(set(CANNOT_BE_OBSERVED) & set(MUST_HAVE_NO_FIXTURE))
    assert not overlap, f"{overlap} claim both to have and not to have a fixture"


#: What each fixture emits *besides* its own code, measured 2026-09-19 by running
#: `check all --format json` in all 70 fixture directories.
#:
#: This closes an inventory that had been measured and left as a recommendation
#: since 2026-09-15: ten fixtures then, thirteen now, and nobody would have seen
#: the set move. A measurement nothing enforces drifts silently, which is the
#: same failure shape as a rule with no mechanical check.
#:
#: An entry here is a claim that the extra code is *structurally unavoidable* for
#: the thing the fixture demonstrates, and each carries its reason. Entries
#: without one are the ones to clean up, not to keep -- this list exists to stop
#: the set growing unnoticed, not to bless it. Adding a line is how a deliberate
#: change is recorded; a new emission with no line is a failure.
EXPECTED_COLLATERAL: dict[str, dict[str, str]] = {
    # Structurally unavoidable: a link to an orphan page is itself an orphan link,
    # and a page nothing links to is also unreachable in the graph. These four
    # fixtures cannot demonstrate one without the other.
    "Z103": {"Z402": "the page the orphan link points at is itself an orphan"},
    "Z402": {"Z410": "an orphan page is unreachable in the graph by construction"},
    "Z410": {"Z402": "the same page, seen from the other rule"},
    "Z407": {
        "Z402": "a malformed nav pattern leaves the page it meant to declare an orphan",
        "Z410": "and therefore unreachable",
    },
    "Z411": {
        "Z103": "the dead-end page is linked from a page nothing links to",
        "Z402": "so that page is an orphan",
        "Z410": "and unreachable",
    },
    # Structurally unavoidable: the finding *is* a broken link, seen by two rules.
    "Z105": {"Z101": "a site-absolute path that resolves nowhere is also a broken link"},
    "Z115": {"Z101": "a page missing from the manifest cannot resolve -- that is the point"},
    # Intended by the fixture's own README.
    "Z205": {"Z603": "the fixture declares a suppression that cannot silence a security code"},
    # Not structural. These are fixtures whose sample page happens to trip a
    # content rule, and they should be rewritten rather than kept here.
    "Z120": {"Z101": "TO CLEAN: the sample link is also broken"},
    "Z124": {"Z101": "TO CLEAN: the sample link is also broken"},
    "Z506": {"Z512": "TO CLEAN: the short sample section reads as empty"},
    "Z610": {"Z512": "TO CLEAN: the frontmatter sample has an empty section under it"},
    "Z523": {"Z516": "TO CLEAN: the out-of-order sample carries two H1s"},
}


@pytest.mark.parametrize("code", sorted(c for c in _fixture_dirs() if c not in CANNOT_BE_OBSERVED))
def test_each_fixture_actually_demonstrates_its_own_code(code: str) -> None:
    """The half a name comparison cannot do: run it and look."""
    fixture = _fixture_dirs()[code]
    if not ZENZIC.exists():
        pytest.fail(f"no zenzic console script at {ZENZIC}")
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "all", ".", "--format", "json"],
        cwd=fixture,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )
    start = proc.stdout.find("{")
    assert start >= 0, (
        f"{fixture.name} produced no JSON at all: {proc.stdout[:300]!r} {proc.stderr[:200]!r}"
    )
    payload = json.loads(proc.stdout[start:])
    emitted = {f["code"] for f in payload.get("findings", [])}
    assert code in emitted, (
        f"{fixture.name} is named for {code} and does not emit it. "
        f"It emits {sorted(emitted) or 'nothing'}. A fixture demonstrating the wrong "
        f"thing passes a name comparison and is worse than a missing one."
    )

    # The other half: what else does it emit? A fixture that demonstrates its own
    # code *and* three unrelated ones teaches the reader the wrong lesson and
    # makes `zenzic lab` output noisy. Declared collateral is allowed, with its
    # reason; anything else is a failure here rather than a slow drift nobody
    # measures.
    undeclared = sorted(emitted - {code} - set(EXPECTED_COLLATERAL.get(code, {})))
    assert not undeclared, (
        f"{fixture.name} also emits {undeclared}, which is not declared in "
        f"EXPECTED_COLLATERAL. Either the fixture grew a defect, or the extra code "
        f"is structurally unavoidable -- in which case add it there with the reason."
    )
