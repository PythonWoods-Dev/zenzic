# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Mirror Law guard: docs/reference/scoring-algorithm.md's Finding Penalty
Matrix must match ``CODE_DEFINITIONS``/``CODE_NAMES`` (src/zenzic/core/codes.py),
the single source of truth.

Regression coverage for V031_SCORING_ALGORITHM_MD_FULL_REMEDIATION: a full
row-by-row audit found 24 of 65 rows with a wrong penalty and/or category,
4 rows with an abbreviated ``Name`` value, and 7 real registered codes
missing from the table entirely (including Z112 and Z620, both genuinely
scored, non-zero-penalty codes). Modeled on tests/test_rule_card_badges.py,
the closest existing precedent for this class of Mirror-Law reference-table
guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS, CODE_NAMES


REPO_ROOT = Path(__file__).resolve().parents[1]
SCORING_ALGORITHM_PATH = REPO_ROOT / "docs" / "reference" / "scoring-algorithm.md"

#: category token stored in codes.py -> the table's human-readable label.
CATEGORY_LABELS: dict[str, str] = {
    "structural": "Structural Integrity",
    "navigation": "Navigation Graph",
    "content": "Content Excellence",
    "brand": "Governance & Brand",
}

#: Explicit special-case policy for codes whose table Category column is NOT
#: derivable from CodeDefinition.category alone -- each of these has
#: category=None in codes.py but a *different* human label depending on what
#: kind of None-category code it actually is. This table IS the SSoT for
#: that policy; there is no field in codes.py to derive it from mechanically
#: (see V031_SCORING_ALGORITHM_MD_FULL_REMEDIATION Phase C's assessment of
#: why a full generation script was not built).
SPECIAL_CATEGORY_LABELS: dict[str, str] = {
    # Pre-scan configuration guards -- non-suppressible, fire before any
    # analysis begins.
    "Z001": "Configuration Guard",
    "Z110": "Configuration Guard",
    "Z111": "Configuration Guard",
    # Runtime HALT gate -- grouped with the other Guard codes rather than a
    # fifth distinct label, since it shares the same "0.0 pts / never scored"
    # semantics.
    "Z901": "Configuration Guard",
    # Z2xx security codes -- pre-empted by Stage 1's unconditional Security
    # Override before the penalty table is ever consulted.
    "Z201": "Inviolable Override",
    "Z202": "Inviolable Override",
    "Z203": "Inviolable Override",
    "Z204": "Inviolable Override",
    "Z205": "Inviolable Override",
    # Reserved/inactive -- registered in codes.py but never emitted at
    # runtime (see docs/rules/Z504.md, finding-codes.md's Reserved Codes
    # section).
    "Z504": "Baseline Audit",
    # Informational/diagnostic codes with zero DQS penalty and no category
    # bucket at all.
    "Z106": "*(uncategorized)*",
    "Z123": "*(uncategorized)*",
    "Z902": "*(uncategorized)*",
    "Z906": "*(uncategorized)*",
}

#: Codes whose Penalty column is the literal string "Security", not a
#: numeric points value -- pre-empted by Stage 1 before Stage 2's penalty
#: table math ever runs.
SECURITY_OVERRIDE_CODES: frozenset[str] = frozenset({"Z201", "Z202", "Z203", "Z204", "Z205"})

ROW_PATTERN = re.compile(
    r"\| \*\*(?P<code>Z\d+)\*\* \| (?P<name>[A-Z0-9_]+) \| (?P<penalty>[^|]+?) \| "
    r"(?P<category>[^|]+?) \| (?P<active>[^|]+?) \|"
)


def _parse_table(text: str) -> dict[str, dict[str, str]]:
    """Return {code: {"name": ..., "penalty": ..., "category": ...}} for
    every row in the Finding Penalty Matrix table.
    """
    rows: dict[str, dict[str, str]] = {}
    for m in ROW_PATTERN.finditer(text):
        rows[m.group("code")] = {
            "name": m.group("name"),
            "penalty": m.group("penalty").strip(),
            "category": m.group("category").strip(),
        }
    return rows


def _expected_category_label(code: str) -> str:
    if code in SPECIAL_CATEGORY_LABELS:
        return SPECIAL_CATEGORY_LABELS[code]
    defn = CODE_DEFINITIONS[code]
    assert defn.category is not None, (
        f"{code}: category=None but not in SPECIAL_CATEGORY_LABELS -- a new "
        f"None-category code was added to codes.py without deciding which "
        f"special-case label it needs here. Add it to SPECIAL_CATEGORY_LABELS."
    )
    return CATEGORY_LABELS[defn.category]


@pytest.mark.parametrize("code", sorted(CODE_DEFINITIONS.keys()), ids=lambda c: c)
def test_every_registered_code_has_a_table_row(code: str) -> None:
    """Every code in CODE_DEFINITIONS must appear in the Finding Penalty
    Matrix table -- catches the "7 missing rows" class of defect (Z110,
    Z111, Z112, Z620, Z901, Z902, Z906 were all silently absent pre-fix).
    """
    text = SCORING_ALGORITHM_PATH.read_text(encoding="utf-8")
    rows = _parse_table(text)
    assert code in rows, f"{code} is registered in codes.py but has no row in scoring-algorithm.md"


@pytest.mark.parametrize("code", sorted(CODE_DEFINITIONS.keys()), ids=lambda c: c)
def test_table_row_matches_codes_py(code: str) -> None:
    """Each table row's Name/Penalty/Category must match codes.py exactly."""
    text = SCORING_ALGORITHM_PATH.read_text(encoding="utf-8")
    rows = _parse_table(text)
    if code not in rows:
        pytest.skip(
            f"{code}: missing row already reported by test_every_registered_code_has_a_table_row"
        )

    defn = CODE_DEFINITIONS[code]
    row = rows[code]

    assert row["name"] == CODE_NAMES[code], (
        f"{code}: table Name is '{row['name']}', codes.py CODE_NAMES says '{CODE_NAMES[code]}'"
    )

    if code in SECURITY_OVERRIDE_CODES:
        assert row["penalty"] == "Security", (
            f"{code}: table Penalty is '{row['penalty']}', expected the literal "
            f"'Security' marker for a Z2xx Security Override code"
        )
    else:
        assert row["penalty"].startswith(f"{defn.penalty}"), (
            f"{code}: table Penalty is '{row['penalty']}', codes.py says penalty={defn.penalty}"
        )

    expected_category = _expected_category_label(code)
    assert row["category"] == expected_category, (
        f"{code}: table Category is '{row['category']}', expected '{expected_category}' "
        f"(codes.py category={defn.category!r})"
    )
