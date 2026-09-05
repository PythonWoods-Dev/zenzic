# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Mirror Law guard: docs/reference/finding-codes.md Severity/Penalty/Suppressible
fields must match CODE_DEFINITIONS / NON_SUPPRESSIBLE_CODES (src/zenzic/core/codes.py).

Regression coverage for V031_RULE_CARD_BADGE_DRIFT_REMEDIATION: 16 entries in this
file carried stale Severity or Penalty values independent of the docs/rules/*.md
badge drift (see test_rule_card_badges.py), including two NON_SUPPRESSIBLE_CODES
(Z110, Z111) that were incorrectly shown as suppressible.

Z201-Z205 use a deliberate "security_breach"/"security_incident" severity display
distinct from codes.py's raw SARIF-level field, and a "🔒 INVIOLABLE" admonition
callout instead of a plain Suppressible field — both accepted conventions, not
drift, so this group is excluded from the severity and suppressibility checks.
Z504 uses an intentionally minimal format (no Penalty/Exit fields, marked
"(reserved)") and is excluded from the penalty check.

``test_finding_codes_heading_names_match_registry`` closes a narrower, separate
gap (V031_TECHNICAL_DEBT_LEDGER_STRUCTURAL_ASSESSMENT's Rule 21 recommendation,
implemented against this page rather than its original target,
``developers/explanation/governance/technical-debt.md``, which was cut in this
same session before the recommendation could be implemented there): a heading's
own *name* text (the part after ``Z101:``) was never checked against
``CODE_NAMES[code]``, only Severity/Penalty/Suppressible were. This is exactly
the code-identity-drift shape that motivated the original recommendation (a
``Z112`` entry once mislabeled as ``Z108``) — and a live scan while implementing
this found 4 real, previously-undetected instances (``Z120``/``Z121``/``Z122``/
``Z124``), fixed in the same commit as this test.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS, CODE_NAMES, NON_SUPPRESSIBLE_CODES


REPO_ROOT = Path(__file__).resolve().parents[1]
FINDING_CODES_PATH = REPO_ROOT / "docs" / "reference" / "finding-codes.md"

SEVERITY_TO_DISPLAY = {"error": "error", "warning": "warning", "note": "info"}
SPECIAL_SEVERITY_DISPLAYS = frozenset({"security_breach", "security_incident"})
MINIMAL_FORMAT_CODES = frozenset({"Z504"})

HEADING_PATTERN = re.compile(r"^### (Z\d+):.*\{#z\d+\}$")
SEVERITY_PATTERN = re.compile(r"\*\*Severity:\*\*\s*(?:`(\w+)`)?")
PENALTY_PATTERN = re.compile(r"\*\*Penalty:\*\*\s*([^·\n]+)")
SUPPRESSIBLE_PATTERN = re.compile(r"\*\*Suppressible:\*\*\s*(\w+)")


def _entries() -> list[tuple[str, str]]:
    lines = FINDING_CODES_PATH.read_text(encoding="utf-8").splitlines()
    headings = [
        (i, m.group(1)) for i, line in enumerate(lines) if (m := HEADING_PATTERN.match(line))
    ]
    entries = []
    for idx, (line_no, code) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        entries.append((code, "\n".join(lines[line_no:end])))
    return entries


def test_finding_codes_entries_match_registry() -> None:
    failures: list[str] = []

    for code, block in _entries():
        defn = CODE_DEFINITIONS.get(code)
        if defn is None:
            failures.append(f"{code}: no CODE_DEFINITIONS entry")
            continue

        sev_match = SEVERITY_PATTERN.search(block)
        sev_display = sev_match.group(1) if sev_match else None

        if sev_display not in SPECIAL_SEVERITY_DISPLAYS:
            expected_sev = SEVERITY_TO_DISPLAY[defn.severity]
            if sev_display != expected_sev:
                failures.append(
                    f"{code}: Severity shows {sev_display!r}, codes.py severity={defn.severity!r} "
                    f"-> should display {expected_sev!r}"
                )

        if code in MINIMAL_FORMAT_CODES:
            continue

        pen_match = PENALTY_PATTERN.search(block)
        pen_str = pen_match.group(1).strip() if pen_match else None
        num_match = re.search(r"[\d.]+", (pen_str or "").replace("−", "-")) if pen_str else None
        if num_match:
            if float(num_match.group()) != defn.penalty:
                failures.append(
                    f"{code}: Penalty shows {pen_str!r}, codes.py penalty={defn.penalty}"
                )
        elif not (defn.penalty == 0.0 and pen_str and "none" in pen_str.lower()):
            failures.append(f"{code}: Penalty field unparseable or missing: {pen_str!r}")

        if code in NON_SUPPRESSIBLE_CODES and "INVIOLABLE" not in block:
            supp_match = SUPPRESSIBLE_PATTERN.search(block)
            supp_display = supp_match.group(1) if supp_match else None
            if supp_display != "No":
                failures.append(
                    f"{code}: in NON_SUPPRESSIBLE_CODES but doc shows Suppressible={supp_display!r}"
                )

    assert not failures, "finding-codes.md drift from codes.py:\n" + "\n".join(failures)


NAMED_HEADING_PATTERN = re.compile(r"^### (Z\d+): ([A-Z_]+) \{#z\d+\}$")


def test_finding_codes_heading_names_match_registry() -> None:
    """Each heading's own name text (after 'Z101:') must match CODE_NAMES[code].

    Severity/Penalty/Suppressible are already guarded above; this catches the
    narrower case where the *identity* of the heading itself drifts — the same
    shape as the historical Z112-mislabeled-as-Z108 incident that motivated
    this test's addition.
    """
    lines = FINDING_CODES_PATH.read_text(encoding="utf-8").splitlines()
    failures: list[str] = []

    for line in lines:
        m = NAMED_HEADING_PATTERN.match(line)
        if not m:
            continue
        code, name = m.group(1), m.group(2)
        expected = CODE_NAMES.get(code)
        if expected is None:
            failures.append(f"{code}: no CODE_NAMES entry")
        elif expected != name:
            failures.append(f"{code}: heading says {name!r}, CODE_NAMES says {expected!r}")

    assert not failures, "finding-codes.md drift from codes.py:\n" + "\n".join(failures)
