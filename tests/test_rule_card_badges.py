# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Mirror Law guard: docs/rules/*.md severity/penalty/category badges must match
``CODE_DEFINITIONS`` (src/zenzic/core/codes.py), the single source of truth.

Regression coverage for V031_RULE_CARD_BADGE_DRIFT_REMEDIATION: 69 of 73 rule
cards were found carrying a static, unwired placeholder badge
(``Penalty: 0.0 points | Category: general``, always ``Severity: Error``)
instead of their real per-code values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "docs" / "rules"

# Severity token stored in codes.py -> (displayed label, icon name, hex color).
# "note" is displayed as "Info" to match the CLI's own note->info user-facing
# mapping (src/zenzic/main.py: `severity = "info" if defn.severity == "note" ...`).
SEVERITY_DISPLAY: dict[str, tuple[str, str, str]] = {
    "error": ("Error", "material-alert-circle", "#e11d48"),
    "warning": ("Warning", "material-alert-outline", "#f59e0b"),
    "note": ("Info", "material-information-outline", "#3b82f6"),
}

BADGE_PATTERN = re.compile(
    r"- :(?P<icon>material-[a-z-]+):\{ \.lg \.middle style=\"color: (?P<color>#[0-9a-f]{6});\" \} "
    r"\*\*Severity: (?P<severity>\w+)\*\*\s*"
    r"---\s*"
    r"Penalty: \*\*(?P<penalty>[\d.]+) points\*\* \| Category: \*\*`(?P<category>[a-z]+)`\*\*",
    flags=re.DOTALL,
)


def _rule_card_paths() -> list[Path]:
    return sorted(p for p in RULES_DIR.glob("Z*.md") if p.stem != "index")


@pytest.mark.parametrize("path", _rule_card_paths(), ids=lambda p: p.stem)
def test_rule_card_badge_matches_codes_py(path: Path) -> None:
    code = path.stem
    defn = CODE_DEFINITIONS.get(code)
    assert defn is not None, f"{code} has a rule card but no CODE_DEFINITIONS entry in codes.py"
    assert defn.severity in SEVERITY_DISPLAY, f"{code}: unknown severity {defn.severity!r}"

    text = path.read_text(encoding="utf-8")
    match = BADGE_PATTERN.search(text)
    assert match is not None, f"{path}: no parseable Severity/Penalty/Category badge found"

    expected_label, expected_icon, expected_color = SEVERITY_DISPLAY[defn.severity]
    expected_category = defn.category if defn.category is not None else "general"

    assert match.group("severity") == expected_label, (
        f"{code}: badge shows Severity '{match.group('severity')}', "
        f"codes.py says severity={defn.severity!r} -> should display '{expected_label}'"
    )
    assert match.group("icon") == expected_icon, (
        f"{code}: badge icon is '{match.group('icon')}', expected '{expected_icon}' for severity={defn.severity!r}"
    )
    assert match.group("color") == expected_color, (
        f"{code}: badge color is '{match.group('color')}', expected '{expected_color}' for severity={defn.severity!r}"
    )
    assert float(match.group("penalty")) == defn.penalty, (
        f"{code}: badge shows Penalty '{match.group('penalty')} points', codes.py says {defn.penalty}"
    )
    assert match.group("category") == expected_category, (
        f"{code}: badge shows Category '{match.group('category')}', codes.py says category={defn.category!r} "
        f"-> should display '{expected_category}'"
    )


# ── Auto-Fixable / Opt-In badge line ─────────────────────────────────────────
# Regression coverage for V031_FINAL_SEVERITY_SWEEP_AND_CONTENT_REMEDIATION's
# corpus-wide sweep (scripts/sweep_rule_card_badges_v2.py): 14 pages found
# with a wrong Auto-Fixable or Opt-In value (Z108/Z603 Auto-Fixable;
# Z518/Z519/Z610-Z619 Opt-In), all fixed in that same directive.
#
# Opt-In ground truth is NOT the "(opt-in)" tag in codes.py's own module
# docstring -- that tag was itself found incomplete (missing Z412/Z610/Z611,
# since fixed in codes.py, but the *tag* is documentation, not code; this
# test verifies the doc pages against the real gating condition directly,
# the same way the sweep script does, so it can't silently drift again if a
# future docstring edit reintroduces a gap).
_OPT_IN_CODES: frozenset[str] = frozenset(
    {
        "Z412",  # scanner.py: gated behind config.policies.traceability_targets
        "Z518",  # scanner.py: gated behind config.policies.enable_passive_voice_check
        "Z519",  # scanner.py: gated behind config.policies.weasel_words
        "Z521",  # governance.py: gated behind self._required_table_columns
        "Z522",  # governance.py: gated behind self._table_cell_enums
        "Z523",  # governance.py: gated behind self._required_heading_order
        "Z610",  # governance.py: gated behind self._required_keys (frontmatter policy group)
        "Z611",  # governance.py: gated behind self._forbidden_domains (link policy group)
        "Z612",  # governance.py: gated behind self._forbidden_keys (frontmatter policy group)
        "Z613",  # governance.py: gated behind self._schema_match (frontmatter policy group)
        "Z614",  # governance.py: gated behind self._allowed_domains (link policy group)
        "Z615",  # governance.py: gated behind self._required_schemes (link policy group)
        "Z616",  # governance.py: gated behind self._cross_namespace (link policy group)
        "Z617",  # governance.py: gated behind self._forbidden_content
        "Z618",  # governance.py: gated behind self._required_headings
        "Z619",  # governance.py: gated behind self._max_complexity > 0
    }
)

FIXABLE_OPT_IN_PATTERN = re.compile(
    r"Auto-Fixable: \*\*(?P<fixable>Yes|No)\*\* \| Opt-In: \*\*(?P<optin>Yes|No)\*\*"
)


@pytest.mark.parametrize("path", _rule_card_paths(), ids=lambda p: p.stem)
def test_rule_card_auto_fixable_and_opt_in_matches_source(path: Path) -> None:
    code = path.stem
    defn = CODE_DEFINITIONS.get(code)
    assert defn is not None, f"{code} has a rule card but no CODE_DEFINITIONS entry in codes.py"

    text = path.read_text(encoding="utf-8")
    match = FIXABLE_OPT_IN_PATTERN.search(text)
    assert match is not None, f"{path}: no parseable Auto-Fixable/Opt-In badge line found"

    expected_fixable = "Yes" if defn.fixable else "No"
    expected_optin = "Yes" if code in _OPT_IN_CODES else "No"

    assert match.group("fixable") == expected_fixable, (
        f"{code}: badge shows Auto-Fixable '{match.group('fixable')}', "
        f"codes.py says fixable={defn.fixable!r} -> should display '{expected_fixable}'"
    )
    assert match.group("optin") == expected_optin, (
        f"{code}: badge shows Opt-In '{match.group('optin')}', "
        f"real gating condition says opt-in={code in _OPT_IN_CODES} -> should display '{expected_optin}'"
    )
