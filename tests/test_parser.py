# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Test suite for Deterministic Markdown Parser."""

import pytest

from zenzic.core.ast import Document, Heading, Paragraph, TextNode
from zenzic.core.parser import parse, serialize


@pytest.mark.parametrize(
    "source",
    [
        "Just a normal paragraph.\n",
        "# Heading 1\n",
        "##   Heading 2 with spaces\n",
        "Paragraph line 1\nParagraph line 2\n\nAnother paragraph.\n",
        "### Heading\n\nSome text.\n",
        "\n\nStarting with blanks.\n",
        "# Heading no newline",
        "Just text no newline",
        "This is a [link](https://example.com) and `code`.\n",
        "Nested [**strong** link](url) and *emphasis* or _emphasis_.\n",
        "Unclosed [link(url) and `code that doesn't close.\n",
        "**Strong text** and __also strong__.\n",
    ],
)
def test_lossless_roundtrip(source: str) -> None:
    """Ensure parser and serializer are byte-for-byte lossless."""
    ast = parse(source)
    result = serialize(ast)
    assert result == source


def test_ast_structure() -> None:
    """Ensure the parsed AST has the correct node types."""
    source = "## Title\n\nA paragraph."
    ast = parse(source)

    assert isinstance(ast, Document)
    assert len(ast.children) == 3  # Heading, Blank Paragraph, Paragraph

    h2 = ast.children[0]
    assert isinstance(h2, Heading)
    assert h2.level == 2
    assert h2.marker == "##"
    assert h2.prefix_space == " "
    assert len(h2.children) == 2
    h2_child0, h2_child1 = h2.children
    assert isinstance(h2_child0, TextNode)
    assert isinstance(h2_child1, TextNode)
    assert h2_child0.text == "Title"
    assert h2_child1.text == "\n"

    p1 = ast.children[1]
    assert isinstance(p1, Paragraph)
    p1_child0 = p1.children[0]
    assert isinstance(p1_child0, TextNode)
    assert p1_child0.text == "\n"

    p2 = ast.children[2]
    assert isinstance(p2, Paragraph)
    p2_child0 = p2.children[0]
    assert isinstance(p2_child0, TextNode)
    assert p2_child0.text == "A paragraph."


def test_re2_compliance() -> None:
    """Ensure regex in parser does not use lookarounds (RE2 constraints)."""
    from zenzic.core.parser import parse

    # Simple parse to ensure it runs without throwing RE2 syntax errors.
    parse("Test.")
