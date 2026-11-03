# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The commit-msg hook refuses a message that names a private folder's path or a term of the local list."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_commit_message_terms.py"
spec = importlib.util.spec_from_file_location("check_commit_message_terms", SCRIPT)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
sys.modules["check_commit_message_terms"] = checker
spec.loader.exec_module(checker)


def test_the_self_test_passes() -> None:
    assert checker.self_test() == []


@pytest.mark.parametrize("folder", [".claude", ".human", ".governance"])
def test_a_path_inside_a_private_folder_is_refused(folder: str) -> None:
    found = checker.problems(f"docs: as {folder}/notes.md says\n", [])
    assert found == [f"line 1: names a path inside the private folder {folder}/"]


def test_the_bare_folder_names_pass() -> None:
    assert (
        checker.problems("fix(doctor): the config refuses .claude and .human as targets\n", [])
        == []
    )


def test_a_term_of_the_local_list_is_refused_case_insensitively(tmp_path: Path) -> None:
    file = tmp_path / ".commit-message-terms"
    file.write_text("# private words\n\nInternal Plan\n", encoding="utf-8")
    local = checker.terms(file)
    assert local == ["Internal Plan"]
    assert checker.problems("docs: follow the internal plan\n", local) == [
        "line 1: names a term of the local list ('Internal Plan')"
    ]


def test_no_terms_file_means_no_terms(tmp_path: Path) -> None:
    assert checker.terms(tmp_path / "missing") == []


def test_comment_lines_are_not_read() -> None:
    assert checker.problems("feat: x\n# .claude/state/y.md\n", []) == []


def test_the_hook_exits_one_on_a_refused_message_and_zero_otherwise(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.write_text("docs: see .human/README.md\n", encoding="utf-8")
    good = tmp_path / "good"
    good.write_text("docs: the install page\n", encoding="utf-8")
    assert checker.main([str(bad)]) == 1
    assert checker.main([str(good)]) == 0
