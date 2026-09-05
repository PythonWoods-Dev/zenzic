# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Corpus-wide sweep of the Auto-Fixable / Opt-In badge line in docs/rules/*.md.

Ground truth:
- Auto-Fixable: CodeDefinition.fixable in src/zenzic/core/codes.py's CODE_DEFINITIONS.
- Opt-In: NOT the "(opt-in)" tag in codes.py's own module docstring -- that
  tag was found to be itself incomplete (missing Z412/Z610/Z611, all three
  confirmed genuinely opt-in by their real gating condition in source; see
  _OPT_IN_CODES below for the citation per code). The real ground truth is
  whether the check's own gating condition in governance.py/scanner.py/
  content.py only runs when a specific policy field is non-empty/non-default
  (i.e. the check is inert unless the user explicitly configures it).

Run from the repo root, report-only (no writes)::

    uv run python scripts/sweep_rule_card_badges_v2.py

Add --fix to rewrite mismatched badge lines in place.
"""

from __future__ import annotations

import sys
from pathlib import Path

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "docs" / "rules"

BADGE_LINE_RE = re.compile(
    r"Auto-Fixable: \*\*(?P<fixable>Yes|No)\*\* \| Opt-In: \*\*(?P<optin>Yes|No)\*\*"
)

# Verified against the actual gating condition in source, not the codes.py
# docstring's "(opt-in)" tag (which was found incomplete -- missing Z412,
# Z610, Z611, all three confirmed genuinely opt-in below).
_OPT_IN_CODES: dict[str, str] = {
    "Z412": "scanner.py: `if config.policies and config.policies.traceability_targets:`",
    "Z518": "scanner.py: `if config.policies.enable_passive_voice_check:`",
    "Z519": "scanner.py: `if config.policies.weasel_words:`",
    "Z521": "governance.py: `if self._required_table_columns:`",
    "Z522": "governance.py: `if self._table_cell_enums:`",
    "Z523": "governance.py: `if self._required_heading_order:`",
    "Z610": "governance.py: `if self._required_keys or ...:`",
    "Z611": "governance.py: `if self._forbidden_domains or ...:` (has_link_policies)",
    "Z612": "governance.py: `if self._required_keys or self._forbidden_keys or ...:`",
    "Z613": "governance.py: `if ... or self._schema_match:`",
    "Z614": "governance.py: `if self._forbidden_domains or self._allowed_domains:`",
    "Z615": "governance.py: `if self._required_schemes:` (has_link_policies)",
    "Z616": "governance.py: `if self._cross_namespace:` (has_link_policies)",
    "Z617": "governance.py: `if self._forbidden_content:`",
    "Z618": "governance.py: `if self._required_headings:`",
    "Z619": "governance.py: `if self._max_complexity > 0:`",
}


def _parse_opt_in_ground_truth() -> dict[str, bool]:
    """Every registered code defaults to non-opt-in unless confirmed
    gated in _OPT_IN_CODES above."""
    return dict.fromkeys(CODE_DEFINITIONS, False) | dict.fromkeys(_OPT_IN_CODES, True)


def main() -> int:
    fix = "--fix" in sys.argv
    opt_in_truth = _parse_opt_in_ground_truth()

    mismatches: list[tuple[str, str, str, str, str, str]] = []
    unparsed: list[str] = []

    for path in sorted(RULES_DIR.glob("Z*.md")):
        code = path.stem
        if code == "index":
            continue
        defn = CODE_DEFINITIONS.get(code)
        if defn is None:
            unparsed.append(f"{code}: no CODE_DEFINITIONS entry")
            continue
        text = path.read_text(encoding="utf-8")
        m = BADGE_LINE_RE.search(text)
        if m is None:
            unparsed.append(f"{code}: no parseable Auto-Fixable/Opt-In badge line")
            continue

        expected_fixable = "Yes" if defn.fixable else "No"
        expected_optin = "Yes" if opt_in_truth[code] else "No"
        actual_fixable = m.group("fixable")
        actual_optin = m.group("optin")

        if actual_fixable != expected_fixable or actual_optin != expected_optin:
            mismatches.append(
                (code, actual_fixable, expected_fixable, actual_optin, expected_optin, str(path))
            )
            if fix:
                new_line = f"Auto-Fixable: **{expected_fixable}** | Opt-In: **{expected_optin}**"
                new_text = text[: m.start()] + new_line + text[m.end() :]
                path.write_text(new_text, encoding="utf-8")

    print(f"Scanned {len(list(RULES_DIR.glob('Z*.md')))} rule cards.")
    print(f"Mismatches found: {len(mismatches)}")
    for code, af, eaf, oi, eoi, _ in mismatches:
        af_note = f"Auto-Fixable: {af} -> {eaf}" if af != eaf else ""
        oi_note = f"Opt-In: {oi} -> {eoi}" if oi != eoi else ""
        note = "; ".join(x for x in (af_note, oi_note) if x)
        print(f"  {code}: {note}")
    if unparsed:
        print(f"Unparsed/skipped: {len(unparsed)}")
        for u in unparsed:
            print(f"  {u}")
    if fix and mismatches:
        print(f"Fixed {len(mismatches)} pages in place.")

    return 1 if mismatches and not fix else 0


if __name__ == "__main__":
    raise SystemExit(main())
