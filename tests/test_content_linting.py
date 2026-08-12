# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit and integration tests for Semantic Linting & Readability Metrics (Z510, Z511, Z512)."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from zenzic.cli._shared import _output_sarif_findings
from zenzic.core.content import (
    check_empty_sections,
    check_heading_hierarchy,
    check_sentence_lengths,
)
from zenzic.core.reporter import Finding


def test_z510_heading_hierarchy_detection(tmp_path: Path) -> None:
    """Z510 flags skipped heading levels with line-number fidelity."""
    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n"
        "\n"
        "### Skipped Subheading\n"  # line 3: H1 -> H3 (skips H2)
        "\n"
        "## Valid H2\n"  # line 5
        "### Valid H3\n"  # line 6
        "##### Skipped H5\n"  # line 7: H3 -> H5 (skips H4)
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_heading_hierarchy(file_path, text)
    assert len(findings) == 2
    assert findings[0].rule_id == "Z510"
    assert findings[0].line_no == 3
    assert "H3 skips previous level H1" in findings[0].message

    assert findings[1].rule_id == "Z510"
    assert findings[1].line_no == 7
    assert "H5 skips previous level H3" in findings[1].message


def test_z511_sentence_length_and_line_fidelity(tmp_path: Path) -> None:
    """Z511 flags sentences > max_words while maintaining line-number fidelity across code blocks."""
    file_path = tmp_path / "doc.md"
    long_sentence = (
        "This is an exceptionally long prose sentence that continues through multiple clauses "
        "and ideas without any sentence ending punctuation until it easily exceeds the maximum "
        "readability limit of forty words defined in the Zenzic workspace configuration file "
        "by adding extra explanatory words at the end of the sentence to guarantee it fails."
    )
    text = (
        "# Title\n"
        "\n"
        "```python\n"
        "# Code blocks should be ignored and not trigger Z511\n"
        "def foo():\n"
        "    return 'a' * 100\n"
        "```\n"
        "\n"
        f"{long_sentence}\n"  # line 9
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_sentence_lengths(file_path, text, max_words=40)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z511"
    assert findings[0].line_no == 9
    assert "Sentence of" in findings[0].message


def test_z511_html_block_exclusion(tmp_path: Path) -> None:
    """Z511 ignores raw HTML blocks and does not trigger findings on HTML tags/attributes/content."""
    file_path = tmp_path / "doc.md"
    html_words = " ".join([f"word{i}" for i in range(120)])
    text = (
        "# Title\n"
        "\n"
        "This is a short prose sentence.\n"
        "\n"
        '<div class="zz-feature-visual">\n'
        f"  <p>{html_words}</p>\n"
        "</div>\n"
        "\n"
        "This is another short prose sentence.\n"
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_sentence_lengths(file_path, text, max_words=40)
    assert len(findings) == 0


def test_z512_empty_section_detection(tmp_path: Path) -> None:
    """Z512 flags headings with zero body content before next heading or EOF."""
    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n"
        "\n"
        "Overview text for title.\n"
        "\n"
        "## Empty Section 1\n"  # line 5: empty
        "## Empty Section 2\n"  # line 6: empty
        "## Valid Section\n"  # line 7: has body content
        "\n"
        "Here is body content for valid section.\n"
        "\n"
        "## Empty Section At EOF\n"  # line 11: empty at EOF
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_empty_sections(file_path, text)
    assert len(findings) == 3
    assert findings[0].rule_id == "Z512"
    assert findings[0].line_no == 5
    assert "Empty Section 1" in findings[0].message

    assert findings[1].rule_id == "Z512"
    assert findings[1].line_no == 6

    assert findings[2].rule_id == "Z512"
    assert findings[2].line_no == 11


def test_sarif_payload_contains_z510_z511_z512_rules() -> None:
    """SARIF output payload automatically includes Z510, Z511, Z512 rule metadata."""
    findings = [
        Finding(
            rel_path="docs/a.md", line_no=3, code="Z510", severity="warning", message="Skipped H2"
        ),
        Finding(
            rel_path="docs/b.md",
            line_no=9,
            code="Z511",
            severity="warning",
            message="Long sentence",
        ),
        Finding(
            rel_path="docs/c.md",
            line_no=4,
            code="Z512",
            severity="warning",
            message="Empty section",
        ),
    ]

    out_buffer = StringIO()
    with patch("sys.stdout", out_buffer):
        _output_sarif_findings(findings, "0.27.0")

    sarif_data = json.loads(out_buffer.getvalue())
    rules = sarif_data["runs"][0]["tool"]["driver"]["rules"]
    rule_ids = {r["id"] for r in rules}

    assert "Z510" in rule_ids
    assert "Z511" in rule_ids
    assert "Z512" in rule_ids

    z510_rule = next(r for r in rules if r["id"] == "Z510")
    assert (
        z510_rule["shortDescription"]["text"]
        == "Heading hierarchy level skipped (e.g., H3 follows H1 without an intervening H2)"
    )


def test_z511_semicolon_sentence_splitting(tmp_path: Path) -> None:
    """Z511 recognizes semicolons as sentence boundaries, evaluating clauses independently."""
    file_path = tmp_path / "doc.md"
    clause1 = " ".join([f"worda{i}" for i in range(25)])
    clause2 = " ".join([f"wordb{i}" for i in range(25)])
    text = f"# Title\n\n{clause1}; {clause2}.\n"
    file_path.write_text(text, encoding="utf-8")

    findings = check_sentence_lengths(file_path, text, max_words=40)
    assert len(findings) == 0

    # Verify that if any single clause separated by a semicolon exceeds max_words, it is flagged
    long_clause = " ".join([f"wordc{i}" for i in range(45)])
    text_long = f"# Title\n\n{clause1}; {long_clause}.\n"
    findings_long = check_sentence_lengths(file_path, text_long, max_words=40)
    assert len(findings_long) == 1
    assert findings_long[0].rule_id == "Z511"
