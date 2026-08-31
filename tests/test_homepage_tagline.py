# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The homepage carries the canonical tagline byte-exact.

Rule 27 makes the tagline an absolute, never-diluted constraint: any content
quoting it must reproduce the exact text, unmodified. The failure mode this
guards is not deletion — which anyone would notice — but quiet erosion: a
comma becoming a semicolon, the em dash gaining spaces, "lightweight" being
dropped as redundant. Each edit is defensible alone and none survives Rule 27.
"""

from __future__ import annotations

import re
from pathlib import Path


HERO = Path(__file__).resolve().parent.parent / "overrides/partials/homepage/hero.html"

#: Byte-exact, from Rule 27 (`.claude/references/04-ai-operational-protocols.md`).
#: The em dash is U+2014 with no surrounding spaces. Do not reflow this string.
CANONICAL = (
    "Formatters handle syntax. Prose linters handle grammar. Zenzic protects the "
    "graph—and optionally enforces lightweight editorial policy without a "
    "separate tool."
)


def _text() -> str:
    html = HERO.read_text(encoding="utf-8")
    stripped = re.sub(r"<[^>]+>", " ", re.sub(r"\{#.*?#\}", " ", html, flags=re.S))
    return re.sub(r"\s+", " ", stripped)


def test_the_tagline_is_present_verbatim() -> None:
    assert CANONICAL in _text(), (
        "the canonical tagline is missing or altered in hero.html — Rule 27 "
        "requires it reproduced exactly, unmodified"
    )


def test_the_tagline_did_not_replace_the_headline() -> None:
    """It is a sub-head beneath the headline, not a substitute for it."""
    text = _text()
    assert "Deterministic Document Integrity" in text, "the hero headline was removed"
    assert text.index("Deterministic Document Integrity") < text.index(CANONICAL), (
        "the tagline must sit beneath the existing headline, not above or instead of it"
    )
