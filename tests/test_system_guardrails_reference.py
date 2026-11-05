# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Mirror Law guard: the two documentation pages that enumerate every System
Guardrail must match ``SYSTEM_EXCLUDED_DIRS`` (src/zenzic/models/config.py),
the single source of truth.

Both pages list all twenty names by hand, in two different renderings, and
nothing checked either of them. That is the maintenance shape this cycle kept
finding: a list grows in code and the prose copies drift silently. A third
page, ``docs/reference/glossary.md``, deliberately abbreviates ("`.git`,
`.venv`, `node_modules`, `build`, `dist`, and others — see
``SYSTEM_EXCLUDED_DIRS``") and is **not** bound here; binding an abbreviation
to a full set would force it to stop being an abbreviation.

Modeled on tests/test_scoring_algorithm_reference.py, the closest existing
precedent for this class of Mirror-Law reference guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core import regex as re
from zenzic.models.config import SYSTEM_EXCLUDED_DIRS


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_REFERENCE_PATH = REPO_ROOT / "docs" / "reference" / "configuration-reference.md"
DISCOVERY_PATH = REPO_ROOT / "docs" / "explanation" / "discovery.md"

#: The inline rendering: a single admonition line of comma-separated backticked
#: names under "System Guardrails (always excluded)".
_INLINE_ADMONITION = "System Guardrails (always excluded)"

#: The fenced rendering: a ```text block of whitespace-aligned columns under
#: the L1 heading.
_FENCED_HEADING = "### L1 -- System Guardrails"


def _inline_names() -> set[str]:
    """Names from configuration-reference.md's admonition."""
    text = CONFIG_REFERENCE_PATH.read_text(encoding="utf-8")
    start = text.find(_INLINE_ADMONITION)
    assert start >= 0, f"{CONFIG_REFERENCE_PATH}: admonition {_INLINE_ADMONITION!r} not found"
    # The list is the first backticked run after the admonition, before the
    # paragraph that names SYSTEM_EXCLUDED_DIRS itself.
    end = text.find("SYSTEM_EXCLUDED_DIRS", start)
    assert end > start, (
        f"{CONFIG_REFERENCE_PATH}: no SYSTEM_EXCLUDED_DIRS reference after admonition"
    )
    # ``regex.findall`` is typed ``list[str] | list[tuple[str, ...]]`` because a
    # pattern with several groups yields tuples. This pattern has exactly one
    # group, so every element is a ``str``; the comprehension states that for
    # the type checker rather than casting it away.
    return {m for m in re.findall(r"`([.\w/-]+)`", text[start:end]) if isinstance(m, str)}


def _fenced_names() -> set[str]:
    """Names from discovery.md's ```text block."""
    text = DISCOVERY_PATH.read_text(encoding="utf-8")
    start = text.find(_FENCED_HEADING)
    assert start >= 0, f"{DISCOVERY_PATH}: heading {_FENCED_HEADING!r} not found"
    fence_open = text.find("```text", start)
    assert fence_open > start, f"{DISCOVERY_PATH}: no ```text block after the L1 heading"
    fence_close = text.find("```", fence_open + len("```text"))
    assert fence_close > fence_open, f"{DISCOVERY_PATH}: unterminated ```text block"
    return set(text[fence_open + len("```text") : fence_close].split())


@pytest.mark.parametrize(
    ("label", "extractor", "path"),
    [
        ("configuration-reference.md", _inline_names, CONFIG_REFERENCE_PATH),
        ("discovery.md", _fenced_names, DISCOVERY_PATH),
    ],
    ids=["config-reference", "discovery"],
)
def test_page_enumerates_exactly_the_registered_guardrails(
    label: str, extractor: object, path: Path
) -> None:
    """Every registered guardrail appears on the page, and nothing else does."""
    documented = extractor()  # type: ignore[operator]
    missing = SYSTEM_EXCLUDED_DIRS - documented
    extra = documented - SYSTEM_EXCLUDED_DIRS
    assert not missing, (
        f"{label}: registered in config.py but absent from the page: {sorted(missing)}"
    )
    assert not extra, (
        f"{label}: listed on the page but not in SYSTEM_EXCLUDED_DIRS: {sorted(extra)}"
    )


def test_both_pages_agree_with_each_other() -> None:
    """Catches the case where both drift the same way and still match nothing."""
    assert _inline_names() == _fenced_names()
