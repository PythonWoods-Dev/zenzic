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
    check_bare_urls,
    check_duplicate_headings,
    check_empty_sections,
    check_generic_image_alt_text,
    check_heading_hierarchy,
    check_heading_punctuation,
    check_multiple_h1_headings,
    check_passive_voice,
    check_sentence_lengths,
    check_weasel_words,
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


def test_z513_duplicate_heading_detection(tmp_path: Path) -> None:
    """Z513 detects duplicate headings within the same document (case/whitespace/anchor invariant)."""
    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n\n"
        "## Setup Guide\n"
        "Some text.\n\n"
        "## setup guide\n"  # line 6: duplicate (case insensitive)
        "More text.\n\n"
        "## Setup Guide {#custom-anchor}\n"  # line 9: duplicate (with anchor)
        "Even more text.\n"
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_duplicate_headings(file_path, text)
    assert len(findings) == 2
    assert findings[0].rule_id == "Z513"
    assert findings[0].line_no == 6
    assert "first occurrence at line 3" in findings[0].message

    assert findings[1].rule_id == "Z513"
    assert findings[1].line_no == 9
    assert "first occurrence at line 3" in findings[1].message


def test_z514_generic_image_alt_text_detection(tmp_path: Path) -> None:
    """Z514 detects generic filler words in image alt attributes for Markdown and HTML."""
    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n\n"
        "![image](assets/diagram.png)\n"  # line 3: generic
        "![screenshot of architecture](assets/arch.png)\n"  # line 4: generic phrase
        ' <img src="assets/pic.png" alt="picture" />\n'  # line 5: generic html
        "![Detailed architectural diagram of the VSM graph](assets/vsm.png)\n"  # line 6: valid
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_generic_image_alt_text(file_path, text)
    assert len(findings) == 3
    assert all(f.rule_id == "Z514" for f in findings)
    assert findings[0].line_no == 3
    assert findings[1].line_no == 4
    assert findings[2].line_no == 5


def test_z515_bare_url_detection_and_mutator(tmp_path: Path) -> None:
    """Z515 detects bare prose URLs and Mutator wraps them in angle brackets."""
    from zenzic.core.mutator import BareUrlMutation, Mutator
    from zenzic.core.parser import parse, serialize

    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n\n"
        "Visit https://zenzic.dev for documentation.\n"  # line 3: bare
        "Check <https://zenzic.dev/guide> and [Zenzic](https://zenzic.dev/about).\n"  # line 4: valid
        "See `https://zenzic.dev/api` in code span.\n"  # line 5: valid
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_bare_urls(file_path, text)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z515"
    assert findings[0].line_no == 3
    assert findings[0].match_text == "https://zenzic.dev"

    ast = parse(text)
    mutator = Mutator([BareUrlMutation()])
    new_ast, changed = mutator.mutate(ast)
    assert changed is True

    new_text = serialize(new_ast)
    assert "Visit <https://zenzic.dev> for documentation." in new_text
    assert "<https://zenzic.dev/guide>" in new_text
    assert "[Zenzic](https://zenzic.dev/about)" in new_text
    assert "`https://zenzic.dev/api`" in new_text


def test_z516_multiple_h1_headings_detection(tmp_path: Path) -> None:
    """Z516 flags documents with more than one H1 heading with severity error."""
    file_path = tmp_path / "doc.md"
    text = (
        "# First Title\n\n"
        "Intro text.\n\n"
        "## Subheading\n\n"
        "# Second Title\n\n"  # line 7: multiple H1
        "<h1>Third Title</h1>\n"  # line 9: multiple H1 (HTML)
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_multiple_h1_headings(file_path, text)
    assert len(findings) == 2
    assert findings[0].rule_id == "Z516"
    assert findings[0].severity == "error"
    assert findings[0].line_no == 7

    assert findings[1].rule_id == "Z516"
    assert findings[1].severity == "error"
    assert findings[1].line_no == 9


def test_z517_heading_punctuation_detection_and_mutator(tmp_path: Path) -> None:
    """Z517 detects trailing invalid punctuation on headings and Mutator auto-fixes it."""
    from zenzic.core.mutator import HeadingPunctuationMutation, Mutator
    from zenzic.core.parser import parse, serialize

    file_path = tmp_path / "doc.md"
    text = (
        "# Title.\n\n"  # line 1: invalid period
        "## Section:\n\n"  # line 3: invalid colon
        "### Subsection;\n\n"  # line 5: invalid semicolon
        "## Valid Question?\n\n"  # line 7: allowed
        "## Valid Exclamation!\n\n"  # line 9: allowed
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_heading_punctuation(file_path, text)
    assert len(findings) == 3
    assert all(f.rule_id == "Z517" for f in findings)
    assert findings[0].line_no == 1
    assert findings[1].line_no == 3
    assert findings[2].line_no == 5

    ast = parse(text)
    mutator = Mutator([HeadingPunctuationMutation()])
    new_ast, changed = mutator.mutate(ast)
    assert changed is True

    new_text = serialize(new_ast)
    assert "# Title\n" in new_text
    assert "## Section\n" in new_text
    assert "### Subsection\n" in new_text
    assert "## Valid Question?\n" in new_text
    assert "## Valid Exclamation!\n" in new_text


def test_z518_passive_voice_detection(tmp_path: Path) -> None:
    """Z518 detects passive voice in prose while ignoring code and links."""
    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n\n"
        "The file was created by the script.\n"  # line 3: passive
        "Zenzic validates the file.\n"  # line 4: active
        "`The message is sent by server` in code.\n"  # line 5: inline code ignored
        "<!-- This was written by human -->\n"  # line 6: comment ignored
        "[is built by](https://example.com/built)\n"  # line 7: link target/markup
    )
    file_path.write_text(text, encoding="utf-8")

    findings = check_passive_voice(file_path, text)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z518"
    assert findings[0].line_no == 3
    assert "was created" in findings[0].match_text


def test_z519_weasel_words_detection(tmp_path: Path) -> None:
    """Z519 detects configured weasel words in technical prose."""
    file_path = tmp_path / "doc.md"
    text = (
        "# Title\n\n"
        "Clearly, you simply configure the gateway.\n"  # line 3: two weasel words
        "Configure the gateway directly.\n"  # line 4: no weasel words
        "Run `simply` command in terminal.\n"  # line 5: code span ignored
    )
    file_path.write_text(text, encoding="utf-8")

    weasel_words = ["clearly", "simply", "obviously"]
    findings = check_weasel_words(file_path, text, weasel_words)
    assert len(findings) == 2
    assert all(f.rule_id == "Z519" for f in findings)
    assert findings[0].line_no == 3
    assert findings[0].match_text == "Clearly"
    assert findings[1].line_no == 3
    assert findings[1].match_text == "simply"


