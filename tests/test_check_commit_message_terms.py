# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The commit-msg hook refuses a message that names a term of the local list, a private folder's path included."""

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


def test_a_term_of_the_local_list_is_refused_case_insensitively(tmp_path: Path) -> None:
    file = tmp_path / ".commit-message-terms"
    file.write_text("# private words\n\nInternal Plan\n", encoding="utf-8")
    local = checker.terms(file)
    assert local == ["Internal Plan"]
    assert checker.problems("docs: follow the internal plan\n", local) == [
        "line 1: names a term of the local list ('Internal Plan')"
    ]


def test_a_folder_listed_with_its_slash_refuses_a_path_inside_it_and_not_its_bare_name() -> None:
    local = ["notes-private/"]
    assert checker.problems("docs: as notes-private/plan.md says\n", local) == [
        "line 1: names a term of the local list ('notes-private/')"
    ]
    assert checker.problems("fix: the config refuses notes-private as a target\n", local) == []


def test_the_public_script_names_no_folder_of_its_own() -> None:
    assert not hasattr(checker, "PRIVATE_FOLDERS")
    assert checker.problems("docs: anything/at/all\n", []) == []


def test_no_terms_file_means_no_terms(tmp_path: Path) -> None:
    assert checker.terms(tmp_path / "missing") == []


def test_comment_lines_are_not_read() -> None:
    assert checker.problems("feat: x\n# secret plan\n", ["secret plan"]) == []


@pytest.mark.parametrize(
    ("message", "code"), [("docs: the secret plan\n", 1), ("docs: the install page\n", 0)]
)
def test_the_hook_exits_one_on_a_refused_message_and_zero_otherwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str, code: int
) -> None:
    monkeypatch.setattr(checker, "terms", lambda: ["secret plan"])
    file = tmp_path / "msg"
    file.write_text(message, encoding="utf-8")
    assert checker.main([str(file)]) == code
