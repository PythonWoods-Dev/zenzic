# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Test suite for Table AST and GFM Table Parser."""

import pickle

from zenzic.core.ast import Document, Paragraph, TableCell, TableNode, TableRow
from zenzic.core.parser import parse, parse_table_cells, serialize


def test_table_ast_pickle_safe() -> None:
    """Ensure Table AST nodes satisfy the Plugin Pickling Contract."""
    cell = TableCell(text="Status", align="center", is_header=True, col_index=0, row_index=0)
    row = TableRow(cells=[cell], is_header=True, row_index=0, raw_line="| Status |")
    table = TableNode(
        headers=["Status"],
        rows=[row],
        raw_lines=["| Status |", "| :---: |"],
        alignments=["center"],
        line_no=10,
    )

    pickled = pickle.dumps(table)
    unpickled = pickle.loads(pickled)

    assert unpickled.headers == ["Status"]
    assert unpickled.alignments == ["center"]
    assert unpickled.line_no == 10
    assert len(unpickled.rows) == 1
    assert unpickled.rows[0].cells[0].text == "Status"
    assert unpickled.rows[0].cells[0].align == "center"


def test_parse_table_cells_handles_escapes_and_code_spans() -> None:
    """Ensure cell parsing splits on unescaped pipes outside code spans."""
    line = r"| Col 1 | `code | span` | Escaped \| pipe |"
    cells = parse_table_cells(line)
    assert len(cells) == 3
    assert cells[0] == "Col 1"
    assert cells[1] == "`code | span`"
    assert cells[2] == r"Escaped \| pipe"


def test_parse_standard_gfm_table() -> None:
    source = (
        "# Overview\n\n"
        "| Name | Status | Description |\n"
        "| :--- | :---: | ---: |\n"
        "| Auth | `stable` | Authentication service |\n"
        "| VSM | `draft` | Virtual Site Map |\n\n"
        "Trailing paragraph.\n"
    )
    ast = parse(source)
    assert isinstance(ast, Document)

    # Children: Heading(# Overview), Blank Paragraph, TableNode, Blank Paragraph, Paragraph
    table = [c for c in ast.children if isinstance(c, TableNode)]
    assert len(table) == 1
    t = table[0]

    assert t.headers == ["Name", "Status", "Description"]
    assert t.alignments == ["left", "center", "right"]
    assert len(t.rows) == 3  # Header row + 2 data rows
    assert t.rows[0].is_header is True
    assert t.rows[1].is_header is False
    assert [c.text for c in t.rows[1].cells] == ["Auth", "`stable`", "Authentication service"]
    assert [c.text for c in t.rows[2].cells] == ["VSM", "`draft`", "Virtual Site Map"]


def test_table_lossless_roundtrip() -> None:
    tables = [
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n",
        "| Name | Status |\n| :--- | :---: |\n| Engine | draft |\n| CLI | stable |\n",
        "Col 1 | Col 2\n--- | ---\nVal 1 | Val 2\n",
        r"# Heading\n\n| A | B |\n| --- | --- |\n| `x | y` | text \| with pipe |\n\nDone.\n",
    ]
    for src in tables:
        ast = parse(src)
        out = serialize(ast)
        assert out == src, f"Roundtrip failed for:\n{src}\nGot:\n{out}"


def test_non_table_pipe_lines_remain_paragraphs() -> None:
    source = "This is a sentence with a | pipe in it.\nNot a table.\n"
    ast = parse(source)
    tables = [c for c in ast.children if isinstance(c, TableNode)]
    assert len(tables) == 0
    assert len(ast.children) == 1
    assert isinstance(ast.children[0], Paragraph)
