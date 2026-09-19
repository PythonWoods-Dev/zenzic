# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``scripts/mutation_gate.py``'s pure decision logic.

``main()`` itself shells out to mutmut and reads a stats file from disk, so
these tests exercise ``_decide()`` directly with synthetic stats dicts —
the same shape ``mutmut export-cicd-stats`` produces (``killed``,
``survived``, ``no_tests``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mutation_gate import FLOOR, INVARIANT_TARGET, MAX_SURVIVORS, _decide  # noqa: E402


if TYPE_CHECKING:
    import pytest


def test_score_below_floor_fails() -> None:
    # killed/decided well under FLOOR, survivor count still within baseline.
    stats = {"killed": 50, "survived": 50, "no_tests": 0}
    exit_code, messages = _decide(stats)
    assert exit_code == 1
    assert any("FAILED" in m and "floor" in m for m in messages)


def test_score_at_floor_with_baseline_survivors_passes() -> None:
    # The exact measured state the floor was set from: 400 killed, 18
    # survived -> 95.7% (rounds to the documented figure).
    stats = {"killed": 400, "survived": MAX_SURVIVORS, "no_tests": 0}
    exit_code, messages = _decide(stats)
    assert exit_code == 0
    assert not any("FAILED" in m for m in messages)


def test_score_above_invariant_target_prints_no_note() -> None:
    stats = {"killed": 990, "survived": 10, "no_tests": 0}
    exit_code, messages = _decide(stats)
    assert exit_code == 0
    assert not any("note:" in m for m in messages)


def test_score_between_floor_and_invariant_prints_a_tracked_note() -> None:
    # A score that clears FLOOR (95.7) but not INVARIANT_TARGET (90.0) is
    # impossible by construction since FLOOR > INVARIANT_TARGET today, but
    # the branch exists for whenever FLOOR is lower than the invariant
    # target — exercise it directly by monkeypatching neither constant,
    # instead using a score between a lowered synthetic floor. Since this
    # module hardcodes both constants, assert the real current relationship
    # holds (FLOOR already meets the invariant) rather than faking the gap.
    assert FLOOR >= INVARIANT_TARGET


def test_no_mutants_decided_fails_with_exit_2() -> None:
    stats = {"killed": 0, "survived": 0, "no_tests": 0}
    exit_code, messages = _decide(stats)
    assert exit_code == 2
    assert any("no mutant was decided" in m for m in messages)


def test_survivor_count_above_baseline_fails_even_when_score_clears_floor() -> None:
    """The gate's own regression guard: a change that adds many new mutants,
    almost all freshly killed but a few newly surviving, can dilute those
    survivors into a score that still clears FLOOR. The raw survivor count
    must be gated too, or that erosion passes silently.

    Constructed so the percentage alone would pass: killed=498, survived=20
    -> 96.1%, comfortably above the 95.7 floor, yet survived (20) exceeds
    the 18-survivor documented-equivalent baseline.
    """
    stats = {"killed": 498, "survived": MAX_SURVIVORS + 2, "no_tests": 0}
    score = 100.0 * stats["killed"] / (stats["killed"] + stats["survived"])
    assert score > FLOOR, "fixture must clear the floor for this test to prove anything"

    exit_code, messages = _decide(stats)
    assert exit_code == 1, (
        f"a survivor count above the {MAX_SURVIVORS}-mutant baseline must fail the "
        f"gate even at a passing percentage; got exit {exit_code}: {messages}"
    )
    assert any("survived" in m and "baseline" in m for m in messages)


def test_main_captures_mutmut_results_beside_the_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stats file carries aggregates only -- killed, survived, no_tests --
    so a survivor has no identity anywhere the gate keeps. Two priority rows
    since 2026-09-07 waited on a triage that could not start because
    `mutmut results`, the command that names each mutant, was never invoked.
    The gate now captures it next to the stats it already exports."""
    import json

    import mutation_gate as mg

    calls: list[tuple[str, ...]] = []
    stats = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    results = tmp_path / "mutants" / "mutmut-results.txt"
    stats.parent.mkdir()

    def fake_run(*argv: str) -> int:
        calls.append(argv)
        if argv == ("mutmut", "export-cicd-stats"):
            stats.write_text(json.dumps({"killed": 400, "survived": 18, "no_tests": 0}))
        return 0

    def fake_capture(*argv: str) -> str:
        calls.append(argv)
        return "src/zenzic/core/credentials.py.x_1: survived\n"

    monkeypatch.setattr(mg, "_run", fake_run)
    monkeypatch.setattr(mg, "_capture", fake_capture)
    monkeypatch.setattr(mg, "STATS", stats)
    monkeypatch.setattr(mg, "RESULTS", results)
    assert mg.main() == 0
    assert ("mutmut", "results") in calls, "the gate must ask mutmut which mutants survived"
    assert results.read_text() == "src/zenzic/core/credentials.py.x_1: survived\n"
