# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Atomic Write Barrier and AST Auto-Fix Hardening."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zenzic.cli._fix import _atomic_write
from zenzic.core.mutator import EmptyLinkTextMutation, Mutator
from zenzic.core.parser import parse, serialize
from zenzic.core.validator import _extract_empty_link_texts
from zenzic.main import app


runner = CliRunner()


def test_atomic_write_symlink_preservation(tmp_path: Path) -> None:
    """The Symlink Trap: atomic write resolves symlinks, leaving the link intact and updating target."""
    target_file = tmp_path / "real_file.md"
    symlink_file = tmp_path / "symlink_file.md"

    target_file.write_text("Original content", encoding="utf-8")
    symlink_file.symlink_to(target_file)

    assert symlink_file.is_symlink()

    # Call _atomic_write on the symlink
    _atomic_write(symlink_file, "Updated content")

    # Verify the target file got the new content
    assert target_file.read_text(encoding="utf-8") == "Updated content"

    # Verify the symlink itself remains a symlink and is not replaced by a regular file
    assert symlink_file.is_symlink()
    assert symlink_file.resolve() == target_file.resolve()


def test_atomic_write_keyboard_interrupt_cleanup(tmp_path: Path) -> None:
    """Permission/Termination Denial: KeyboardInterrupt does not leak temporary files."""
    test_file = tmp_path / "test_file.md"
    test_file.write_text("Original content", encoding="utf-8")

    # Mock os.replace to raise KeyboardInterrupt
    with patch("os.replace", side_effect=KeyboardInterrupt("Simulated Ctrl-C")):
        with pytest.raises(KeyboardInterrupt, match="Simulated Ctrl-C"):
            _atomic_write(test_file, "New content")

    # Check that no temp files starting with .zenzic-tmp- exist in the directory
    temp_files = list(tmp_path.glob(".zenzic-tmp-*"))
    assert len(temp_files) == 0, f"Leaked temporary files found: {temp_files}"


def test_formatted_empty_link_validation_and_mutation() -> None:
    """AST Drift / Empty Link Bypass: Formatted empty links are correctly flagged and mutated."""
    empty_formats = [
        "[](url)",
        "[ ](url)",
        "[**](url)",
        "[*_~` `~_*](url)",
        "[*](url)",
        "[**][ref]",
    ]

    # 1. Test Validator Flags them
    for text in empty_formats:
        findings = _extract_empty_link_texts(text)
        assert len(findings) == 1, f"Expected validator to flag: {text}"

    # 2. Test Mutator Fixes them
    mutator = Mutator([EmptyLinkTextMutation()])

    for text in empty_formats:
        if "ref" in text:
            # References aren't inline links in standard parsing as LinkNode, skip mutation test
            continue
        ast = parse(text)
        new_ast, changed = mutator.mutate(ast)
        assert changed, f"Expected mutator to change: {text}"

        serialized = serialize(new_ast)
        assert serialized == "[TODO](url)", f"Got: {serialized}"


def test_empty_link_text_mutation_is_idempotent() -> None:
    """EmptyLinkTextMutation.apply() must be idempotent: mutate(mutate(ast)) == mutate(ast).

    Holds by construction — apply() only injects "TODO" when the link has no
    text content, and the injected "TODO" text itself satisfies that
    precondition on any subsequent pass — but had no dedicated regression
    test (`03-priority-table.md`, docs-hygiene auditor discovery). Auto-fix
    tooling commonly runs to a fixed point (apply repeatedly until no
    further changes); a mutation that isn't genuinely idempotent would
    either loop forever or drift the content on repeated runs.
    """
    mutator = Mutator([EmptyLinkTextMutation()])

    ast = parse("[](url)")
    first_ast, first_changed = mutator.mutate(ast)
    assert first_changed
    assert serialize(first_ast) == "[TODO](url)"

    second_ast, second_changed = mutator.mutate(first_ast)
    assert not second_changed
    assert serialize(second_ast) == "[TODO](url)"


def test_polyglot_extractor_comment_masking() -> None:
    """An HTML tag or a Z205 scheme inside an HTML or MDX comment is ignored by PolyglotExtractor."""
    from zenzic.core.validator import PolyglotExtractor

    extractor = PolyglotExtractor()

    # 1. HTML comment with Z205 scheme
    text = "<!-- <a href='javascript:alert(1)'>XSS</a> -->"
    nodes = extractor.extract(text)
    assert len(nodes) == 0, "Should ignore tags inside HTML comments"

    # 2. MDX comment with Z205 scheme
    text = "{/* <a href='javascript:alert(1)'>XSS</a> */}"
    nodes = extractor.extract(text)
    assert len(nodes) == 0, "Should ignore tags inside MDX comments"

    # 3. HTML tag outside comments but comments present
    text = "<!-- comment -->\n<a href='safe.md'>link</a>\n{/* comment */}"
    nodes = extractor.extract(text)
    assert len(nodes) == 1
    assert nodes[0].href == "safe.md"
    assert nodes[0].line_no == 2


def test_polyglot_extractor_fence_evasion() -> None:
    """A closing fence with trailing characters is NOT recognized as a closing fence, keeping masking active."""
    from zenzic.core.validator import PolyglotExtractor

    extractor = PolyglotExtractor()

    # A fence is opened, then closed with ```extra. It should NOT be closed.
    # Therefore, the tag <a href="safe.md"> inside/after it should remain masked.
    text = (
        "```\n<a href='safe.md'>inside</a>\n```extra\n<a href='safe.md'>after-fake-close</a>\n```\n"
    )
    nodes = extractor.extract(text)
    # The first tag is inside the block. The second tag is also inside the block because ```extra didn't close it.
    # The last ``` finally closes the block.
    # So both should be masked, resulting in 0 extracted nodes.
    assert len(nodes) == 0, (
        "Should treat both tags as inside the code block because of malformed closing fence"
    )

    # If it is closed correctly (without extra info), the tag after should be extracted
    text_closed = "```\n<a href='safe.md'>inside</a>\n```\n<a href='safe.md'>after-real-close</a>\n"
    nodes_closed = extractor.extract(text_closed)
    assert len(nodes_closed) == 1
    assert nodes_closed[0].href == "safe.md"
    assert nodes_closed[0].line_no == 4


# ── zenzic fix --rename (V031_FIXABLE_FIELD_EXPANSION_RULE17_CHECKLIST_AND_CLI_RENAME_FEATURE) ──


def _init_repo(tmp_path: Path) -> Path:
    (tmp_path / ".zenzic.toml").write_text("")
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    return docs


def test_fix_rename_dry_run_default_shows_diff_and_does_not_modify(tmp_path: Path) -> None:
    """--dry-run is the default (matches the existing `fix` command's own default) --
    real fixture: A links to B, rename B to B2, confirm the diff is shown but the file
    on disk is untouched."""
    docs = _init_repo(tmp_path)
    (docs / "b.md").write_text("# B\nContent.\n")
    a_file = docs / "a.md"
    a_file.write_text("# A\nSee [B](./b.md) for details.\n")

    result = runner.invoke(
        app, ["fix", "--rename", str(docs / "b.md"), str(docs / "b2.md")], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert "b2.md" in result.output
    assert a_file.read_text() == "# A\nSee [B](./b.md) for details.\n", (
        "dry-run must not modify the file on disk"
    )


def test_fix_rename_apply_rewrites_inbound_link(tmp_path: Path) -> None:
    """--apply actually rewrites the inbound link on disk."""
    docs = _init_repo(tmp_path)
    (docs / "b.md").write_text("# B\nContent.\n")
    a_file = docs / "a.md"
    a_file.write_text("# A\nSee [B](./b.md) for details.\n")

    result = runner.invoke(
        app,
        ["fix", "--rename", str(docs / "b.md"), str(docs / "b2.md"), "--apply"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "[B](b2.md)" in a_file.read_text()


def test_fix_rename_skips_alias_style_href(tmp_path: Path) -> None:
    """Same safety gate as the LSP version: a docs-root-relative ('/...') href is
    left untouched, not guessed at."""
    docs = _init_repo(tmp_path)
    (docs / "b.md").write_text("# B\nContent.\n")
    a_file = docs / "a.md"
    a_file.write_text("# A\nSee [B](/b.md) for details.\n")

    result = runner.invoke(
        app,
        ["fix", "--rename", str(docs / "b.md"), str(docs / "b2.md"), "--apply"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert a_file.read_text() == "# A\nSee [B](/b.md) for details.\n"


def test_fix_rename_no_op_when_no_inbound_links(tmp_path: Path) -> None:
    """Clean, honest reporting when nothing needs fixing -- not a silent no-op."""
    docs = _init_repo(tmp_path)
    (docs / "b.md").write_text("# B\nContent.\n")
    (docs / "unrelated.md").write_text("# Unrelated\nNo links here.\n")

    result = runner.invoke(
        app,
        ["fix", "--rename", str(docs / "b.md"), str(docs / "b2.md"), "--apply"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "No inbound links" in result.output or "0 file" in result.output.lower()


def test_fix_rename_partial_success_multiple_files_reported_individually(tmp_path: Path) -> None:
    """Safety (Phase 3): renaming a heavily-linked page reports each affected file
    individually -- not a single opaque success/failure for the whole batch."""
    docs = _init_repo(tmp_path)
    (docs / "b.md").write_text("# B\nContent.\n")
    a_file = docs / "a.md"
    c_file = docs / "c.md"
    a_file.write_text("# A\nSee [B](./b.md) for details.\n")
    c_file.write_text("# C\nAlso see [B](./b.md) here.\n")

    result = runner.invoke(
        app,
        ["fix", "--rename", str(docs / "b.md"), str(docs / "b2.md"), "--apply"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "a.md" in result.output
    assert "c.md" in result.output
    assert "[B](b2.md)" in a_file.read_text()
    assert "[B](b2.md)" in c_file.read_text()
