# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for core check functions and CLI smoke tests.

The MkDocs plugin integration has been removed in v0.7.0. Zenzic is a
sovereign CLI. These tests verify that the underlying pure-Python core
functions are correct, and that the CLI exposes the expected sub-commands.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from zenzic.core.rules import PlaceholderRule, ShortContentRule
from zenzic.core.scanner import (
    calculate_orphans,
    calculate_unused_assets,
    check_asset_references,
)
from zenzic.core.validator import check_snippet_content
from zenzic.main import app
from zenzic.models.config import ZenzicConfig


runner = CliRunner()


# ─── Pure core: calculate_orphans ─────────────────────────────────────────────


def test_calculate_orphans_returns_diff() -> None:
    all_md = {"index.md", "guide.md", "orphan.md"}
    nav = {"index.md", "guide.md"}
    assert calculate_orphans(all_md, nav) == ["orphan.md"]


def test_calculate_orphans_empty_when_all_mapped() -> None:
    pages = {"index.md", "api.md"}
    assert calculate_orphans(pages, pages) == []


def test_calculate_orphans_sorted() -> None:
    result = calculate_orphans({"z.md", "a.md", "m.md"}, set())
    assert result == ["a.md", "m.md", "z.md"]


# ─── Pure core: check_placeholder_content ─────────────────────────────────────


def test_check_placeholder_short_content() -> None:
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("page.md"), "too short")
    assert any(f.rule_id == "Z502" for f in findings)


def test_check_placeholder_pattern_match() -> None:
    config = ZenzicConfig()
    rule = PlaceholderRule(config.placeholder_patterns_compiled)
    # "This is a TODO section..." is a sentence, not a marker. Since 2026-09-19
    # the default patterns describe a marker's shape -- it opens its line, or a
    # colon follows it -- because `\btodo\b` matched ordinary English prose on a
    # foreign corpus ("inboxes, social networks, todo lists").
    findings = rule.check(
        Path("page.md"),
        "# Title\n\nTODO: this section needs more content.\n" * 5,
    )
    assert any(f.rule_id == "Z501" for f in findings)

    prose = rule.check(
        Path("page.md"),
        "# Title\n\nInboxes, social networks, todo lists and native-like apps.\n" * 5,
    )
    assert not any(f.rule_id == "Z501" for f in prose)


def test_check_placeholder_clean_page() -> None:
    config = ZenzicConfig(placeholder_max_words=50)
    content = "# Complete Page\n\n" + "Real content here. " * 60
    rule1 = ShortContentRule(config.placeholder_max_words)
    rule2 = PlaceholderRule(config.placeholder_patterns_compiled)
    assert not rule1.check(Path("page.md"), content)
    assert not rule2.check(Path("page.md"), content)


# ─── Pure core: check_snippet_content ─────────────────────────────────────────


def test_check_snippet_valid_python() -> None:
    md = "```python\nprint('hello')\n```\n"
    assert check_snippet_content(md, "page.md") == []


def test_check_snippet_invalid_python() -> None:
    md = "```python\ndef broken(\n```\n"
    errors = check_snippet_content(md, "page.md")
    assert errors
    assert "SyntaxError" in errors[0].message


def test_check_snippet_non_python_ignored() -> None:
    md = "```bash\nrm -rf /\n```\n"
    assert check_snippet_content(md, "page.md") == []


def test_check_snippet_yaml_multi_doc_no_false_positive() -> None:
    """YAML snippets with ``---`` document separators must not raise Z503.

    Regression (D048 Bug 4): yaml.safe_load() raised "expected single document"
    when a snippet contained ``---`` (a valid YAML document separator).  Docusaurus
    docs frequently show frontmatter examples using ``---`` inside code blocks.
    """
    md = """\
Some text before.

```yaml
---
title: My Page
sidebar_label: My Page
---
title: Second Document
```

Some text after.
"""
    errors = check_snippet_content(md, "guide.mdx")
    assert errors == [], f"Multi-doc YAML snippet raised unexpected errors: {errors}"


def test_check_snippet_yaml_absolute_line_no() -> None:
    """Z503 YAML errors must report absolute file line, not snippet-relative line.

    Regression (D048 Bug 2): line_no was always fence_line + 1, discarding the
    YAML parser's own problem_mark.line.  A syntax error on snippet line 3 at file
    line 183 was reported as line 181 (fence + 1) instead of 183 (fence + 3).
    """
    # Build a file where the YAML fence is at line 10 and the error is on line 3
    # of the snippet (absolute line 13 in the file).
    prefix = "\n" * 9  # 9 blank lines → fence opens at line 10
    md = prefix + "```yaml\nkey: value\nanother: fine\nbad: :\n```\n"
    errors = check_snippet_content(md, "reference.mdx")
    assert errors, "Invalid YAML must produce a SnippetError"
    # The error is on snippet line 3 (bad: :) → absolute line 10 + 3 = 13
    assert errors[0].line_no == 13, (
        f"Expected absolute line 13, got {errors[0].line_no}. "
        "YAML line mapping is not adding snippet-relative offset correctly."
    )


def test_check_asset_references_markdown_image() -> None:
    refs = check_asset_references("![logo](assets/logo.png)", "")
    assert "assets/logo.png" in refs


def test_check_asset_references_relative_path() -> None:
    refs = check_asset_references("![img](../assets/logo.png)", "guide")
    assert "assets/logo.png" in refs


def test_check_asset_references_ignores_http() -> None:
    refs = check_asset_references("![img](https://example.com/logo.png)", "")
    assert not refs


def test_check_asset_references_ignores_escape() -> None:
    """Paths that escape docs root (../../) are not tracked."""
    refs = check_asset_references("![img](../../outside.png)", "")
    assert not refs


# ─── Pure core: calculate_unused_assets ───────────────────────────────────────


def test_calculate_unused_assets() -> None:
    all_a = {"assets/logo.png", "assets/unused.png"}
    used = {"assets/logo.png"}
    assert calculate_unused_assets(all_a, used) == ["assets/unused.png"]


def test_calculate_unused_assets_none_unused() -> None:
    assets = {"assets/logo.png"}
    assert calculate_unused_assets(assets, assets) == []


# ─── CLI smoke tests ──────────────────────────────────────────────────────────


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout


def test_cli_check_subcommands_listed() -> None:
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    for sub in ("links", "orphans", "snippets", "assets", "placeholders", "all"):
        assert sub in result.stdout
