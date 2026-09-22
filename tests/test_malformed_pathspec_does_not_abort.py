# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A malformed MkDocs pattern must not take the scan down.

Reading ``not_in_nav`` introduced a path where an unparseable pattern aborts the
whole run: ``pathspec`` parses gitignore syntax by compiling it with ``re2``
directly, so a bad character class raises ``re2._re2.Error`` — which is not a
``ValueError`` and not ``zenzic.core.regex.error`` either, because the shim that
translates RE2 failures only covers compiles routed through it.

The boundary, measured against pathspec 1.1.1:

* ``!`` and ``\\`` raise ``GitIgnorePatternError`` (a ``ValueError``);
* ``[[:bad:]`` raises ``re2._re2.Error`` (a bare ``Exception``);
* ``docs/[orphan.md``, ``[``, ``a[b`` parse cleanly and simply match nothing.

Only the first three are detectable. The fourth group is why a "pattern that
matches nothing" cannot be distinguished from one whose targets were all fixed.
"""

from __future__ import annotations

import pytest

from zenzic.core.adapters._utils import _extract_not_in_nav_spec


UNPARSEABLE = ["!", "\\", "[[:bad:]"]
PARSEABLE_BUT_INERT = ["docs/[orphan.md", "[", "a[b"]


@pytest.mark.parametrize("pattern", UNPARSEABLE)
def test_unparseable_pattern_returns_none_instead_of_raising(pattern: str) -> None:
    assert _extract_not_in_nav_spec({"not_in_nav": pattern + "\n"}) is None


@pytest.mark.parametrize("pattern", PARSEABLE_BUT_INERT)
def test_parseable_pattern_still_builds_a_spec(pattern: str) -> None:
    """Positive control: the guard must not swallow patterns that are merely useless."""
    spec = _extract_not_in_nav_spec({"not_in_nav": pattern + "\n"})
    assert spec is not None
    assert spec.match_file("docs/orphan.md") is False


def test_a_valid_pattern_is_unaffected() -> None:
    spec = _extract_not_in_nav_spec({"not_in_nav": "docs/orphan.md\n"})
    assert spec is not None
    assert spec.match_file("docs/orphan.md") is True
