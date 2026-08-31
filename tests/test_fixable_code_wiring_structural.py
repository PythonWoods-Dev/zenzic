# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_FIXABLE_STATUS_PROPAGATION_CHECK_AND_RULE_REASSIMILATION.

Every code marked ``fixable=True`` in ``codes.py`` has a dedicated
``Mutation`` class in ``mutator.py`` (each carrying a ``"Zxxx Auto-Fix: ..."``
docstring convention already established before this test existed). That
declaration alone does not guarantee the fix is actually *reachable*: this
session found 3 of the 6 fixable codes (Z515/Z517/Z520) had a working
Mutation class the CLI's ``zenzic fix`` already used, but no corresponding
branch in the LSP's ``textDocument/codeAction`` handler -- the editor's
manual Quick Fix silently offered nothing for them, undetected until an
unrelated feature's Phase 1 investigation happened to notice it.

This test parses each fix-consuming surface's own source text (not
behavior, to stay fast and dependency-free) and asserts every fixable
code's Mutation class name appears somewhere in it. It does not replace
`tests/test_redteam_remediation.py`'s (or `test_lsp.py`'s) behavioral tests
that a given Mutation actually produces the right edit -- it only guards
the narrower, structural "is this code's fix wired into every consumer at
all" question, the exact class of drift found this session.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
MUTATOR_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "mutator.py"
FIX_CLI_PATH = REPO_ROOT / "src" / "zenzic" / "cli" / "_fix.py"
CODE_ACTION_PATH = REPO_ROOT / "src" / "zenzic" / "lsp" / "server.py"

#: Z603 is deliberately excluded from auto-fix-on-save (`_handle_will_save_wait_until`)
#: only -- it needs dead-suppression line numbers as constructor state, which the
#: on-save trigger does not compute. It remains reachable via manual Quick Fix and
#: `zenzic fix`. This is a stated, deliberate exclusion, not a gap.
WILL_SAVE_WAIT_UNTIL_DELIBERATE_EXCLUSIONS = {"Z603"}


def _code_to_mutation_class() -> dict[str, str]:
    """Parse mutator.py's own "Zxxx Auto-Fix: ..." docstring convention."""
    text = MUTATOR_PATH.read_text(encoding="utf-8")
    mapping: dict[str, str] = {}
    # Matches: class FooMutation:\n    """Z108 Auto-Fix: ..."""
    for m in re.finditer(r'class (\w+):\s*\n\s*"""(Z\d{3}) Auto-Fix:', text):
        class_name, code = m.group(1), m.group(2)
        mapping[code] = class_name
    return mapping


def _fixable_codes() -> set[str]:
    return {code for code, defn in CODE_DEFINITIONS.items() if getattr(defn, "fixable", False)}


def test_every_fixable_code_has_a_mutation_class() -> None:
    """codes.py's fixable=True declaration must have a real mutator.py implementation."""
    mapping = _code_to_mutation_class()
    fixable = _fixable_codes()
    missing = fixable - mapping.keys()
    assert not missing, (
        f"fixable=True in codes.py but no matching 'Zxxx Auto-Fix:' Mutation class "
        f"docstring found in mutator.py: {sorted(missing)}"
    )


def test_every_fixable_code_wired_into_cli_fix_command() -> None:
    """Every fixable code's Mutation class must be instantiated in `zenzic fix`."""
    mapping = _code_to_mutation_class()
    source = FIX_CLI_PATH.read_text(encoding="utf-8")
    missing = [
        code for code, cls in mapping.items() if code in _fixable_codes() and cls not in source
    ]
    assert not missing, (
        f"_fix.py does not reference the Mutation class for: {sorted(missing)} "
        f"-- `zenzic fix` would silently skip these fixable codes."
    )


def test_every_fixable_code_wired_into_lsp_code_action() -> None:
    """Every fixable code must have a reachable Quick Fix in the editor
    (textDocument/codeAction), not just in the CLI."""
    source = CODE_ACTION_PATH.read_text(encoding="utf-8")
    missing = [
        code for code in _fixable_codes() if f'"{code}"' not in _handle_code_action_section(source)
    ]
    assert not missing, (
        f"textDocument/codeAction has no branch for: {sorted(missing)} -- manual "
        f"Quick Fix in the editor would silently offer nothing for these codes. "
        f"(This exact class of drift was found and fixed for Z515/Z517/Z520 this session.)"
    )


def test_every_fixable_code_wired_into_lsp_will_save_wait_until() -> None:
    """Every fixable code (except the stated, deliberate Z603 exclusion) must be
    reachable via auto-fix-on-save (textDocument/willSaveWaitUntil)."""
    source = CODE_ACTION_PATH.read_text(encoding="utf-8")
    section = _will_save_wait_until_section(source)
    expected = _fixable_codes() - WILL_SAVE_WAIT_UNTIL_DELIBERATE_EXCLUSIONS
    missing = [code for code in expected if f'"{code}"' not in section]
    assert not missing, (
        f"_handle_will_save_wait_until's mutation_factory has no entry for: "
        f"{sorted(missing)} -- auto-fix-on-save would silently skip these codes "
        f"even when enabled."
    )


def _handle_code_action_section(source: str) -> str:
    start = source.index("def _handle_code_action(")
    end = source.index("def _handle_will_save_wait_until(")
    return source[start:end]


def _will_save_wait_until_section(source: str) -> str:
    start = source.index("def _handle_will_save_wait_until(")
    end = source.index("def _handle_will_rename_files(")
    return source[start:end]
