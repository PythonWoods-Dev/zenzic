# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regenerate docs/rules/*.md Severity/Penalty/Category badges from codes.py.

``src/zenzic/core/codes.py`` (``CODE_DEFINITIONS``) is the single source of
truth. This script rewrites each rule card's badge block to match it,
eliminating the class of drift found in V031_RULE_CARD_BADGE_DRIFT_REMEDIATION
(a static placeholder badge — always "Error" / "0.0 points" / "general" — that
was never wired to real per-code data for any card predating the v0.31.0
Epic 3 cycle).

Z412, Z521, Z522, Z523 are explicitly excluded — their badges were already
hand-verified correct and are left untouched by directive; the accompanying
test (tests/test_rule_card_badges.py) still verifies them as a
non-regression check.

Run from the repo root::

    uv run python scripts/sync_rule_card_badges.py
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "docs" / "rules"

EXCLUDED_CODES = frozenset({"Z412", "Z521", "Z522", "Z523"})

# Severity token in codes.py -> (displayed label, icon name, hex color).
# "note" displays as "Info" to match the CLI's own note->info mapping
# (src/zenzic/main.py: `severity = "info" if defn.severity == "note" ...`).
SEVERITY_DISPLAY: dict[str, tuple[str, str, str]] = {
    "error": ("Error", "material-alert-circle", "#e11d48"),
    "warning": ("Warning", "material-alert-outline", "#f59e0b"),
    "note": ("Info", "material-information-outline", "#3b82f6"),
}

#: The Auto-Fixable | Opt-In line. `fixable` has been in the registry since
#: v0.20.0 and this script still did not write it, so all 70 cards carried it by
#: hand; `activation` now makes the Opt-In half derivable too.
FIXABLE_OPT_IN_PATTERN = re.compile(
    r"Auto-Fixable: \*\*(?:Yes|No)\*\* \| Opt-In: \*\*(?:Yes|No)\*\*"
)


BADGE_PATTERN = re.compile(
    r"- :(?P<icon>material-[a-z-]+):\{ \.lg \.middle style=\"color: (?P<color>#[0-9a-f]{6});\" \} "
    r"\*\*Severity: (?P<severity>\w+)\*\*\s*"
    r"---\s*"
    r"Penalty: \*\*(?P<penalty>[\d.]+) points\*\* \| Category: \*\*`(?P<category>[a-z]+)`\*\*",
    flags=re.DOTALL,
)


def _expected_badge(code: str) -> str | None:
    defn = CODE_DEFINITIONS.get(code)
    if defn is None or defn.severity not in SEVERITY_DISPLAY:
        return None
    label, icon, color = SEVERITY_DISPLAY[defn.severity]
    category = defn.category if defn.category is not None else "general"
    return (
        f'- :{icon}:{{ .lg .middle style="color: {color};" }} **Severity: {label}**\n'
        f"\n"
        f"    ---\n"
        f"\n"
        f"    Penalty: **{defn.penalty} points** | Category: **`{category}`**"
    )


def _expected_fixable_optin(code: str) -> str | None:
    defn = CODE_DEFINITIONS.get(code)
    if defn is None:
        return None
    fixable = "Yes" if defn.fixable else "No"
    optin = "Yes" if defn.activation != "default" else "No"
    return f"Auto-Fixable: **{fixable}** | Opt-In: **{optin}**"


def main() -> None:
    changed: list[str] = []
    skipped: list[str] = []
    for path in sorted(RULES_DIR.glob("Z*.md")):
        code = path.stem
        if code == "index" or code in EXCLUDED_CODES:
            continue
        text = path.read_text(encoding="utf-8")
        match = BADGE_PATTERN.search(text)
        if match is None:
            skipped.append(f"{code}: no parseable badge found")
            continue
        expected = _expected_badge(code)
        if expected is None:
            skipped.append(f"{code}: no CODE_DEFINITIONS entry")
            continue
        new_text = text[: match.start()] + expected + text[match.end() :]
        fo_match = FIXABLE_OPT_IN_PATTERN.search(new_text)
        fo_expected = _expected_fixable_optin(code)
        if fo_match is not None and fo_expected is not None:
            new_text = new_text[: fo_match.start()] + fo_expected + new_text[fo_match.end() :]
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(code)

    print(f"Updated {len(changed)} rule cards: {', '.join(changed)}")
    if skipped:
        print(f"Skipped {len(skipped)}: {'; '.join(skipped)}")


if __name__ == "__main__":
    main()
