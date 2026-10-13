# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""An engine pattern that cannot be parsed is reported, not swallowed.

MkDocs aborts the build on an unparseable ``not_in_nav``/``exclude_docs``/
``draft_docs`` pattern: *"Invalid git pattern"*, *"Aborted with a configuration
error!"*. Zenzic cannot abort — it is an analyser, and killing the scan would
deny every other finding in the repository — so it reports the pattern and
carries on.

Silence is what this replaces. Before Z407 the declaration simply had no
effect, and the only visible trace was the finding the author expected to be
suppressed still firing, with nothing saying why.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.adapters._mkdocs import check_engine_patterns


UNPARSEABLE = ["!", "\\", "[[:bad:]"]


def _project(tmp_path: Path, key: str, pattern: str) -> Path:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        f"site_name: T\n{key}: |\n  {pattern}\nnav:\n  - Home: index.md\n", encoding="utf-8"
    )
    return tmp_path


def test_unparseable_pattern_is_reported(tmp_path: Path) -> None:
    issues = check_engine_patterns(_project(tmp_path, "not_in_nav", "[[:bad:]"))
    assert len(issues) == 1
    rel_path, message = issues[0]
    assert rel_path == "mkdocs.yml"
    assert "not_in_nav" in message


def test_every_unparseable_form_is_reported(tmp_path: Path) -> None:
    """All three raise, in two unrelated exception families."""
    for i, pattern in enumerate(UNPARSEABLE):
        root = _project(tmp_path / f"p{i}", "not_in_nav", pattern)
        assert check_engine_patterns(root), f"{pattern!r} produced no issue"


def test_all_three_keys_are_checked(tmp_path: Path) -> None:
    for i, key in enumerate(("not_in_nav", "exclude_docs", "draft_docs")):
        root = _project(tmp_path / f"k{i}", key, "[[:bad:]")
        issues = check_engine_patterns(root)
        assert issues, f"{key} unparseable pattern produced no issue"
        assert key in issues[0][1]


def test_a_valid_pattern_reports_nothing(tmp_path: Path) -> None:
    """Positive control: the check must not fire on patterns that parse."""
    assert check_engine_patterns(_project(tmp_path, "not_in_nav", "archive.md")) == []


def test_a_useless_but_parseable_pattern_reports_nothing(tmp_path: Path) -> None:
    """``docs/[orphan.md`` parses and matches nothing — indistinguishable from a
    pattern whose targets were all fixed, so it is not this check's business."""
    assert check_engine_patterns(_project(tmp_path, "not_in_nav", "docs/[orphan.md")) == []


def test_absent_keys_report_nothing(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: T\n", encoding="utf-8")
    assert check_engine_patterns(tmp_path) == []
