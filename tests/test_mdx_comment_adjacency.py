# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every regex that reads an MDX comment must accept the spelling Prettier emits.

``{ /* … */ }`` is legal MDX: the braces are an expression container and the
whitespace is free. Five places in the engine recognise an MDX comment, and the
assumption that the braces sit adjacent to the comment markers was fixed in four
of them and missed in the fifth — because the sweep looked for *maskers*, and the
fifth was a frontmatter stripper in the policy engine. It shared the belief, not
the construct.

So these tests sweep for the belief. One walks the source for the adjacency-only
spelling of the pattern, which catches a copy that does not exist yet; the other
drives each known pattern through a real file, which catches one that is written
a different way.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()

_SRC = Path(__file__).resolve().parent.parent / "src"

#: The adjacency-only opener, as it appears inside a compiled pattern. Written in
#: two halves so this file does not match its own tripwire.
_ADJACENT_ONLY = "\\{" + "/\\*"

#: Every leading-comment spelling a page may legally open with.
_LEADING = {
    "adjacent": "{/* generated header - do not edit */}",
    "spaced": "{ /* generated header - do not edit */ }",
    "html": "<!-- generated header - do not edit -->",
}


def test_no_source_file_compiles_an_adjacency_only_mdx_comment_pattern() -> None:
    """A tripwire, not a listing: it fires on a copy nobody has written yet.

    Enumerating the five known patterns would pass the day a sixth is added. This
    fails instead, and names the file.
    """
    offenders = [
        f"{p.relative_to(_SRC)}:{n}"
        for p in sorted(_SRC.rglob("*.py"))
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1)
        if _ADJACENT_ONLY in line
    ]
    assert not offenders, (
        "these patterns require `{` adjacent to `/*`, so they do not recognise the "
        "MDX comment spelling Prettier emits: " + ", ".join(offenders)
    )


@pytest.mark.parametrize("spelling", sorted(_LEADING))
def test_a_leading_comment_never_hides_the_frontmatter_beneath_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    """The fifth site, driven end to end.

    A leading comment is how `.mdx` files carry a licence header or a
    generated-file banner; the spelling here is deliberately not a licence
    expression, so the repository's own REUSE linter does not try to parse the
    fixture's string as one.

    The policy engine strips leading comments so it can find the frontmatter
    block. With the spaced spelling unrecognised, the block was never found and
    the file read as having **no frontmatter at all** — so ``Z610`` reported a
    required key as absent while the key sat two lines below it. ``Z612`` and
    ``Z613`` read the same dictionary.
    """
    (tmp_path / ".zenzic.toml").write_text(
        textwrap.dedent("""\
            docs_dir = "docs"
            fail_under = 0

            [build_context]
            engine = "standalone"

            [policies]
            required_frontmatter_keys = ["title"]
            """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.mdx").write_text(
        f"{_LEADING[spelling]}\n"
        "---\ntitle: Present And Correct\n---\n\n"
        "# Present And Correct\n\n"
        "The required key is in the frontmatter, so no policy finding may name it\n"
        "as absent whatever spelling the comment above it uses.\n",
        encoding="utf-8",
    )
    # A page that genuinely lacks the key, so a run reporting nothing at all
    # cannot be mistaken for a run reporting the right thing.
    (docs / "control.mdx").write_text(
        "---\ndescription: no title key here\n---\n\n"
        "# Negative Control\n\n"
        "This page really is missing the required key and must always be reported.\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    out = runner.invoke(app, ["check", "all", "--no-header"], catch_exceptions=False).stdout

    assert "control.mdx:1" in out and "[Z610]" in out, (
        "the probe found nothing at all, so it proves nothing:\n" + out
    )
    assert not [ln for ln in out.splitlines() if "[Z610]" in ln and "page.mdx" in ln], (
        f"a {spelling} leading comment hid the frontmatter beneath it:\n" + out
    )
