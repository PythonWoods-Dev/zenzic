# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``explain`` must not present an unemittable code as live, and its field set
must not depend on whether a code has a scoring category.

Two defects, measured:

1. ``Z109`` carries ``status="inactive"`` — a catalogued alias consolidated into
   ``Z101`` at runtime — and ``explain`` rendered ``Activation: on by default``.
   No command surfaced status at all.

2. The metadata table drove its fields from category, not penalty:
   ``Z407`` and ``Z906`` share penalty ``0.0`` and rendered different field sets,
   because only a code with a scoring bucket reached the branch that prints a
   Penalty row. The four codes outside the DQS are genuinely a different shape,
   so the row now states *why* there is no penalty rather than inventing one.
"""

from __future__ import annotations

from typer.testing import CliRunner

from zenzic.core.codes import CODE_DEFINITIONS
from zenzic.main import app


runner = CliRunner()

#: The only codes reaching the metadata table's final branch: outside the DQS,
#: not security, not a config abort, not a halt-level governance gate.
OUTSIDE_DQS = ("Z106", "Z123", "Z901", "Z906")


def _out(code: str) -> str:
    result = runner.invoke(app, ["explain", code])
    assert result.exit_code == 0, result.output
    return result.stdout


def test_an_inactive_code_says_it_is_never_emitted() -> None:
    out = _out("Z109")
    assert "on by default" not in out, "an inactive code must not read as live"
    assert "never emitted" in out.lower() or "alias" in out.lower()


def test_the_alias_reads_as_deliberate_not_broken() -> None:
    """Distinguishing an alias from something broken is the point of the wording.

    The message stays general on purpose. Its branch is guarded by
    ``status != "active"``, which today reaches one code; naming ``Z101`` inside
    a general guard would tell the *next* inactive code's reader it had been
    consolidated into Z101, which would be false the day it is added. The rule
    card carries the specific target.
    """
    out = _out("Z109")
    assert "catalogued alias" in out
    assert "another code" in out or "rule card" in out


def test_an_active_code_still_reports_its_activation() -> None:
    """Positive control: the status row must not displace activation."""
    out = _out("Z402")
    assert "on by default" in out


def test_every_code_renders_a_penalty_row() -> None:
    """The field set is uniform; only its content varies."""
    missing = [c for c in sorted(CODE_DEFINITIONS) if "Penalty" not in _out(c)]
    assert not missing, f"no Penalty row for {missing}"


def test_outside_dqs_codes_say_why_there_is_no_penalty() -> None:
    for code in OUTSIDE_DQS:
        out = _out(code)
        assert "not in the DQS" in out or "outside the DQS" in out, f"{code}: {out[:200]}"


def test_a_scored_zero_penalty_code_still_reads_not_penalised() -> None:
    """Positive control: Z407 has a category and 0.0, and must keep its wording."""
    assert "not penalised" in _out("Z407")
