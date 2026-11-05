# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A registered code is either constructed somewhere, or declared as never emitted.

Documentation did not prevent a code from being dead: one code had a registry
entry, a rule card and a reference entry and no code path that could produce it;
another had a registry entry, a card and a gallery fixture while the engine
reported its condition under a different code. Both were found by accident.

The registry already carries the field that says which kind a code is —
``CodeDefinition.status``, where ``"inactive"`` means *remains in the namespace
for configuration compatibility and is never emitted*. So the check is agreement
between that field and the source tree, in both directions:

* an ``"active"`` code must appear as a quoted literal in some module other than
  ``codes.py``;
* an ``"inactive"`` code must not.

WHAT "APPEARS" MEANS, AND WHAT IT CANNOT PROVE: a quoted literal is a construction
site or a lookup key. It does not prove the path that uses it is reachable — a
code constructed only inside dead code passes. It catches the shape that actually
occurred: a registered code with no literal anywhere.

``DISPLAY_ONLY`` holds codes the engine prints as text rather than constructing as
a finding. Each entry is checked too, so the exemption cannot outlive its reason.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS


SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"

DISPLAY_ONLY: dict[str, str] = {
    "Z906": (
        "printed as text by `check all` when no Markdown source exists, after which the "
        "command returns; it never reaches `findings[]`, JSON or SARIF"
    ),
}


def _sources() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in SRC.rglob("*.py") if p.name != "codes.py"}


def _quoted(code: str, sources: dict[Path, str]) -> list[Path]:
    pattern = re.compile(r"[\"']" + code + r"[\"']")
    return [p for p, text in sources.items() if pattern.search(text)]


def _bare(code: str, sources: dict[Path, str]) -> list[Path]:
    pattern = re.compile(r"\b" + code + r"\b")
    return [p for p, text in sources.items() if pattern.search(text)]


def test_the_instrument_finds_a_code_that_is_constructed() -> None:
    """A search that matches nothing would make both checks below pass vacuously."""
    assert _quoted("Z101", _sources()), "Z101 is constructed in src/ and the search did not find it"


def test_every_active_code_is_constructed_somewhere() -> None:
    sources = _sources()
    dead = sorted(
        code
        for code, definition in CODE_DEFINITIONS.items()
        if definition.status == "active" and code not in DISPLAY_ONLY and not _quoted(code, sources)
    )
    assert not dead, (
        f"{dead} are registered as active and no module outside codes.py constructs them. "
        "Either the emission site is missing, or the code is a catalogue entry the engine "
        "never produces — in which case set status='inactive' and say so on its card."
    )


def test_no_inactive_code_is_constructed() -> None:
    sources = _sources()
    constructed = {
        code: [str(p.relative_to(SRC)) for p in _quoted(code, sources)]
        for code, definition in CODE_DEFINITIONS.items()
        if definition.status == "inactive"
    }
    constructed = {code: where for code, where in constructed.items() if where}
    assert not constructed, (
        f"declared inactive (never emitted) and constructed anyway: {constructed}. "
        "One of the two is wrong."
    )


def test_display_only_exemptions_are_still_true() -> None:
    sources = _sources()
    for code, reason in DISPLAY_ONLY.items():
        assert code in CODE_DEFINITIONS, f"DISPLAY_ONLY names {code}, which is not a code"
        assert not _quoted(code, sources), (
            f"{code} is exempted as display-only ({reason}) and is now constructed as a "
            "literal — remove the exemption"
        )
        assert _bare(code, sources), f"{code} is exempted as display-only and appears nowhere"
