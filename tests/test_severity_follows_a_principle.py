# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Severity is assigned by what a code *means*, and this file is the check.

Every severity in `CODE_DEFINITIONS` was decided on its own, next to the code
being added, by looking at what a similar code carried. That is assignment by
precedent, and it is how `Z906 NO_FILES_FOUND` carried `note` and exit `0` over
a documentation directory that did not exist for months: nothing anywhere said
what `note` was *for*, so nothing could notice that this was not it.

The principle, derived from what the codes mean rather than from what they
carry today:

**A · The analysis did not happen.** The run did not produce the coverage it
appears to have produced: the configuration could not be read, or a declared
check did not run. Severity is `error` and the penalty is `0.0` — there is
nothing to score, the absence *is* the finding. A code in this tier below
`error` is a gate that passes over work that was never done.

**B · The analysis ran; the project's configuration is wrong or stale.** The
corpus was read correctly and something the user declared no longer matches it.
Severity is `warning`: nothing is broken for a reader, and the repair is a
configuration edit.

**C · The analysis ran; the content or structure has a defect.** Scored in its
category. `error` when the published page is broken for a reader, `warning`
when the reader is served worse.

**N · Informational by construction.** A true statement about the corpus that
is not a defect and that no author is being asked to fix. `note`.

**S · Security.** Its own tier with its own exit codes, out of scope here.

The classification below is asserted in **both** directions: a code missing
from it fails, and a code named here that no longer exists fails. Adding a code
therefore means classifying it.
"""

from __future__ import annotations

import pytest

from zenzic.core.codes import CODE_DEFINITIONS, CODE_NAMES


#: Tier A — the analysis did not happen. `error`, penalty 0.0, no category.
TIER_A_ANALYSIS_DID_NOT_HAPPEN: dict[str, str] = {
    "Z001": "the configuration's structure is invalid; the pipeline stops before reading a file",
    "Z110": "the configuration file is not parseable TOML; nothing downstream ran",
    "Z111": "the configuration is schema-invalid, or docs_dir names a directory that is not there",
    "Z901": "a rule raised, so that rule did not run over the corpus",
    "Z902": "a rule exceeded its time limit, so that rule did not finish over the file",
}

#: Tier B — the analysis ran; a declaration no longer matches the corpus. `warning`.
TIER_B_CONFIGURATION_IS_STALE: dict[str, str] = {
    "Z112": "an allowlist entry no link matched",
    "Z115": "a source the route manifest does not declare",
    "Z404": "an asset the engine configuration names and the tree does not hold",
    "Z407": "a pattern the engine configuration declares that cannot apply",
    "Z603": "an inline suppression that silences nothing",
    "Z620": "a directory policy that silences nothing",
}

#: Tier N — informational by construction. `note`.
TIER_N_INFORMATIONAL: dict[str, str] = {
    "Z123": "a non-HTTP scheme is a fact about a link, not a defect in it",
    "Z106": (
        "a link cycle is the normal shape of a cross-referenced manual, not a defect. "
        "Recorded on 2026-09-19 as a contradiction of this principle -- 'a defect an "
        "author should fix' -- and the measurement refuted that: enabled on this "
        "repository it reports **823 findings across 244 pages**, concentrated on "
        "`reference/finding-codes.md` (90), the gallery index (64) and `how-to/index.md` "
        "(22). Those are hub pages, and a hub linking its children while the children "
        "link back is required navigation in Di\u00e1taxis. The same check on a corpus of "
        "comparable size reports 4. A rule measuring a shape nobody wants to correct is "
        "an observation about the graph, which is what `note` is for, and opt-in for the "
        "right reason"
    ),
    "Z906": (
        "the documentation directory exists and holds no Markdown -- a project in setup. "
        "This became true only on 2026-09-19: until then the code also covered a directory "
        "that did not exist, which is Tier A, and `note` was wrong for that half"
    ),
}

#: Tier S — security. Severity is governed by the Exit Code Contract, not by this principle.
TIER_S_SECURITY: frozenset[str] = frozenset({"Z201", "Z202", "Z203", "Z204", "Z205"})

#: Contradictions found by applying the principle on 2026-09-19 and **not** fixed
#: in that batch, each with why the fix is larger than a severity edit. Asserted
#: in both directions below, so an entry cannot outlive the contradiction it names.
CONTRADICTIONS_AWAITING_A_RELEASE_DECISION: dict[str, str] = {
    "Z401": (
        "MISSING_DIRECTORY_INDEX is a defect an author should fix, so Tier N is wrong for "
        "it. Same coupling as Z106, plus it already sits in a scored category "
        "(`navigation`) with a 0.0 penalty, so the promotion has to settle that too"
    ),
}


def _scored_codes() -> dict[str, object]:
    """Active codes outside the security tier."""
    return {
        code: defn
        for code, defn in CODE_DEFINITIONS.items()
        if code not in TIER_S_SECURITY and getattr(defn, "status", "active") == "active"
    }


@pytest.mark.parametrize("code", sorted(TIER_A_ANALYSIS_DID_NOT_HAPPEN))
def test_a_code_meaning_the_analysis_did_not_happen_is_an_error(code: str) -> None:
    """Tier A cannot be below `error`, and cannot be scored.

    `Z906` is the precedent this guards: it sat at `note` with exit `0` while
    covering a documentation directory that was not there, and a scan that
    examined nothing reported success for months.
    """
    defn = CODE_DEFINITIONS[code]
    reason = TIER_A_ANALYSIS_DID_NOT_HAPPEN[code]
    assert defn.severity == "error", (
        f"{code} ({CODE_NAMES[code]}) means {reason}, which is Tier A, "
        f"and carries {defn.severity!r}. A gate passes over work that was never done."
    )
    assert defn.penalty == 0.0, (
        f"{code} is Tier A and carries a {defn.penalty} penalty. There is nothing to "
        "score: the absence of the analysis is the finding."
    )


@pytest.mark.parametrize("code", sorted(TIER_B_CONFIGURATION_IS_STALE))
def test_a_stale_declaration_is_a_warning(code: str) -> None:
    defn = CODE_DEFINITIONS[code]
    assert defn.severity == "warning", (
        f"{code} ({CODE_NAMES[code]}) is {TIER_B_CONFIGURATION_IS_STALE[code]} — "
        f"the corpus was read correctly and a declaration no longer matches it, "
        f"which is a warning, not {defn.severity!r}."
    )


@pytest.mark.parametrize("code", sorted(TIER_N_INFORMATIONAL))
def test_only_what_is_informational_by_construction_is_a_note(code: str) -> None:
    defn = CODE_DEFINITIONS[code]
    assert defn.severity == "note", (
        f"{code} is declared informational and carries {defn.severity!r}."
    )


def test_note_is_not_used_for_anything_else() -> None:
    """The direction that matters: `note` must not collect defects.

    A defect parked at `note` is invisible by default and costs nothing, which
    is indistinguishable from not implementing the check.
    """
    notes = {c for c, d in _scored_codes().items() if d.severity == "note"}  # type: ignore[attr-defined]
    unexplained = (
        notes - set(TIER_N_INFORMATIONAL) - set(CONTRADICTIONS_AWAITING_A_RELEASE_DECISION)
    )
    assert not unexplained, (
        f"{sorted(unexplained)} carry `note` and are neither declared informational nor "
        "recorded as a known contradiction. Classify them."
    )


def test_every_active_code_is_classified() -> None:
    """A code added without a tier is a severity assigned by precedent again."""
    classified = (
        set(TIER_A_ANALYSIS_DID_NOT_HAPPEN)
        | set(TIER_B_CONFIGURATION_IS_STALE)
        | set(TIER_N_INFORMATIONAL)
        | set(CONTRADICTIONS_AWAITING_A_RELEASE_DECISION)
    )
    # Tier C is the remainder by construction -- content and structure findings,
    # scored in their category. It is named by exclusion rather than listed so
    # that adding an ordinary content code does not require editing this file;
    # every *other* tier must be declared.
    tier_c = {
        code
        for code, defn in _scored_codes().items()
        if code not in classified and defn.category is not None and defn.penalty > 0.0  # type: ignore[attr-defined]
    }
    unaccounted = set(_scored_codes()) - classified - tier_c
    assert not unaccounted, (
        f"{sorted(unaccounted)} fall in no tier: they are outside the security tier, "
        "not declared Tier A/B/N, and do not have the scored category and non-zero "
        "penalty that makes a code Tier C. Each is a severity nobody has justified."
    )


def test_the_recorded_contradictions_still_contradict() -> None:
    """An entry expires when the thing it describes stops happening."""
    for code, why in CONTRADICTIONS_AWAITING_A_RELEASE_DECISION.items():
        assert code in CODE_DEFINITIONS, (
            f"{code} is recorded as a contradiction and no longer exists"
        )
        assert CODE_DEFINITIONS[code].severity == "note", (
            f"{code} is recorded as wrongly carrying `note` and now carries "
            f"{CODE_DEFINITIONS[code].severity!r}. Remove the entry: {why[:60]}..."
        )
