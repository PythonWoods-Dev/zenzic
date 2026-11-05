# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Score history is an append-only series, kept apart from the baseline.

``.zenzic-baseline.json`` holds one snapshot and one signature set; its schema is
``additionalProperties: false``, so a ``history`` array could not be added to it
without a schema version bump. It also exists for a different job — matching
finding signatures so known debt stays suppressed — and overloading it with trend
reporting would couple two unrelated concerns.

So the series lives in its own file, ``.zenzic-history.jsonl``: one JSON object
per run, appended, never rewritten. Append-only JSONL is crash-safe (a truncated
final line costs one entry, not the file), bounded by dropping leading lines, and
readable in a diff. Neither existing state file changes shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from zenzic.core.history import (
    HISTORY_FILENAME,
    append_history_entry,
    read_history,
)


def _entry(score: int, ts: str) -> dict[str, object]:
    return {"timestamp": ts, "score": score, "categories": {"structural": 1.0}}


class TestAppendAndRead:
    def test_append_creates_the_file(self, tmp_path: Path) -> None:
        path = append_history_entry(tmp_path, _entry(90, "2026-01-01T00:00:00+00:00"))
        assert path == tmp_path / HISTORY_FILENAME
        assert path.is_file()
        assert len(read_history(tmp_path)) == 1

    def test_entries_accumulate_in_order(self, tmp_path: Path) -> None:
        for i, score in enumerate((70, 80, 90)):
            append_history_entry(tmp_path, _entry(score, f"2026-01-0{i + 1}T00:00:00+00:00"))
        assert [e["score"] for e in read_history(tmp_path)] == [70, 80, 90]

    def test_append_never_rewrites_earlier_lines(self, tmp_path: Path) -> None:
        append_history_entry(tmp_path, _entry(70, "2026-01-01T00:00:00+00:00"))
        first = (tmp_path / HISTORY_FILENAME).read_text(encoding="utf-8")
        append_history_entry(tmp_path, _entry(80, "2026-01-02T00:00:00+00:00"))
        after = (tmp_path / HISTORY_FILENAME).read_text(encoding="utf-8")
        assert after.startswith(first), "an earlier entry was rewritten"

    def test_one_json_object_per_line(self, tmp_path: Path) -> None:
        for i in range(3):
            append_history_entry(tmp_path, _entry(80 + i, f"2026-01-0{i + 1}T00:00:00+00:00"))
        lines = (tmp_path / HISTORY_FILENAME).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for line in lines:
            assert isinstance(json.loads(line), dict)


class TestAbsenceIsNotAnError:
    def test_reading_a_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_history(tmp_path) == []

    def test_a_truncated_final_line_costs_one_entry_not_the_file(self, tmp_path: Path) -> None:
        """The crash-safety property the format is chosen for."""
        append_history_entry(tmp_path, _entry(70, "2026-01-01T00:00:00+00:00"))
        append_history_entry(tmp_path, _entry(80, "2026-01-02T00:00:00+00:00"))
        path = tmp_path / HISTORY_FILENAME
        path.write_text(path.read_text(encoding="utf-8")[:-12], encoding="utf-8")
        recovered = read_history(tmp_path)
        assert [e["score"] for e in recovered] == [70]

    def test_a_corrupt_middle_line_is_skipped(self, tmp_path: Path) -> None:
        append_history_entry(tmp_path, _entry(70, "2026-01-01T00:00:00+00:00"))
        path = tmp_path / HISTORY_FILENAME
        with path.open("a", encoding="utf-8") as fh:
            fh.write("{ not json\n")
        append_history_entry(tmp_path, _entry(90, "2026-01-03T00:00:00+00:00"))
        assert [e["score"] for e in read_history(tmp_path)] == [70, 90]


class TestBoundedGrowth:
    def test_history_is_capped_and_drops_oldest_first(self, tmp_path: Path) -> None:
        for i in range(5):
            append_history_entry(
                tmp_path, _entry(i, f"2026-01-0{i + 1}T00:00:00+00:00"), max_entries=3
            )
        assert [e["score"] for e in read_history(tmp_path)] == [2, 3, 4]

    def test_cap_keeps_one_object_per_line(self, tmp_path: Path) -> None:
        for i in range(5):
            append_history_entry(
                tmp_path, _entry(i, f"2026-01-0{i + 1}T00:00:00+00:00"), max_entries=2
            )
        lines = (tmp_path / HISTORY_FILENAME).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert all(isinstance(json.loads(line), dict) for line in lines)


class TestExistingStateFilesUntouched:
    """The reason for a separate file: neither existing consumer changes."""

    def test_history_does_not_create_or_modify_the_other_state_files(self, tmp_path: Path) -> None:
        baseline = tmp_path / ".zenzic-baseline.json"
        snapshot = tmp_path / ".zenzic-score.json"
        baseline.write_text(
            '{"version":"1","score":90,"findings_count":0,"signatures":[]}', encoding="utf-8"
        )
        snapshot.write_text('{"score": 90}', encoding="utf-8")
        before = (baseline.read_bytes(), snapshot.read_bytes())
        append_history_entry(tmp_path, _entry(95, "2026-01-01T00:00:00+00:00"))
        assert (baseline.read_bytes(), snapshot.read_bytes()) == before
