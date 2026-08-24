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
