# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Append-only score history, kept separate from the baseline.

``.zenzic-baseline.json`` records one snapshot plus a signature set, and its
schema is ``additionalProperties: false`` — a ``history`` array could not be
added without a schema version bump. It also serves a different purpose: matching
finding signatures so known debt stays suppressed. Trend reporting is unrelated
to that job, and folding the two together would couple them permanently.

So the series lives in its own file, one JSON object per line:

    {"timestamp": "...", "score": 98, "categories": {...}, "commit": "abc1234"}

JSONL rather than a JSON array because the only write this file ever takes is an
append. A truncated final line — an interrupted CI job, a full disk — costs the
last entry, not the file, and neither existing state file changes shape.

Every function here is pure I/O over a path; nothing caches, and a missing file
is an empty history rather than an error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


#: Root-level, beside ``.zenzic-score.json`` and ``.zenzic-baseline.json``.
HISTORY_FILENAME = ".zenzic-history.jsonl"

#: Entries kept before the oldest are dropped. Roughly a year of daily CI runs;
#: large enough to show a trend, small enough that the file stays diff-friendly.
DEFAULT_MAX_ENTRIES = 500


def history_path(repo_root: Path) -> Path:
    """Absolute path to the history file for *repo_root* (may not exist)."""
    return repo_root / HISTORY_FILENAME


def read_history(repo_root: Path) -> list[dict[str, Any]]:
    """Every readable entry, oldest first.

    Unparseable lines are skipped rather than raising: a partially written final
    line is the expected outcome of an interrupted run, and losing that one entry
    must not make the rest of the series unreadable.
    """
    path = history_path(repo_root)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def append_history_entry(
    repo_root: Path,
    entry: dict[str, Any],
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> Path:
    """Append *entry* as one line, trimming the oldest once past *max_entries*.

    The common path is a plain append — no read, no rewrite. Trimming only
    happens on the runs that actually cross the cap, and rewrites the file whole
    at that point, which is the one moment the append-only property is
    deliberately traded for bounded growth.
    """
    path = history_path(repo_root)
    line = json.dumps(entry, separators=(",", ":"), sort_keys=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    if max_entries > 0:
        existing = read_history(repo_root)
        if len(existing) > max_entries:
            kept = existing[-max_entries:]
            path.write_text(
                "".join(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n" for e in kept),
                encoding="utf-8",
            )
    return path


def summarize_trend(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """First/last/min/max/delta over *entries*, or ``None`` when there are none.

    Returns ``None`` rather than a zeroed structure so a caller can distinguish
    "no history yet" from "history exists and is flat".
    """
    scores = [e["score"] for e in entries if isinstance(e.get("score"), int | float)]
    if not scores:
        return None
    return {
        "runs": len(scores),
        "first": scores[0],
        "last": scores[-1],
        "min": min(scores),
        "max": max(scores),
        "delta": scores[-1] - scores[0],
    }
