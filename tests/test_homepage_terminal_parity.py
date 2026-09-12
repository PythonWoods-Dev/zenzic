# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The homepage's terminal block must show what the CLI actually prints.

``overrides/partials/homepage/execution_layer.html`` renders a ``zenzic check
all`` session as styled HTML rather than an image, which keeps it selectable,
responsive and theme-aware — but it is hand-maintained, so nothing stopped it
drifting away from the tool it depicts. It had: a summary line missing
``• 1 file impacted`` and reporting the wrong warning count, no ``DQS Final
Score`` line at all, a telemetry line still in the pre-``(N pages, N config)``
format, an omitted ``[LIKELY PLACEHOLDER]`` marker, invented multi-line code
frames the CLI does not emit, and two findings the depicted run does not
produce.

This test reproduces the exact fixture the block was captured from, runs the
real CLI over it, and asserts every visible line between the partial's
``terminal:begin``/``terminal:end`` markers appears in that output. A future
edit to either side that is not mirrored in the other fails here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


PARTIAL = (
    Path(__file__).resolve().parent.parent / "overrides/partials/homepage/execution_layer.html"
)

#: Lines whose content legitimately varies between runs, and so cannot be
#: asserted verbatim. Throughput and elapsed time are machine-dependent; the
#: rule separator is decoration, not output.
_VOLATILE = re.compile(r"files/s|^─+$")

#: The depicted repository, reproduced exactly. Any change to the block's
#: content means changing this fixture too — that coupling is the point.
_FIXTURE: dict[str, str] = {
    "mkdocs.yml": "site_name: Demo\n",
    ".zenzic.toml": 'docs_dir = "docs"\n\n[governance]\nbrand_obsolescence = ["OldPlatform"]\n',
    "docs/deploy.md": "# Deploy\n\n```bash\nAWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n```\n",
    "docs/index.md": (
        "# Welcome\n\n"
        "See the [intro page](./intro.md) for details.\n\n"
        "![architecture](./assets/old-diagram.png)\n\n"
        "This project was migrated from **OldPlatform** in Q1 2026.\n"
    ),
}


def _visible_lines() -> list[str]:
    """Text the reader actually sees inside the terminal block."""
    html = PARTIAL.read_text(encoding="utf-8")
    body = html.split("terminal:begin", 1)[1].split("terminal:end", 1)[0]
    # Drop the remainder of the opening Jinja comment, and the opening of the
    # closing one — neither is rendered, so neither is depicted output.
    body = body.split("#}", 1)[1].rsplit("{#", 1)[0]

    # <pre> holds real newlines; every other line is one block-level element.
    body = re.sub(r"<(div|pre)\b[^>]*>", "\n", body)
    # A space, not an empty string: adjacent inline spans carry no whitespace of
    # their own, and joining them bare would fuse two columns into one token.
    body = re.sub(r"<[^>]+>", " ", body)
    body = body.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')

    lines: list[str] = []
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#}") or _VOLATILE.search(line):
            continue
        lines.append(re.sub(r"\s+", " ", line))
    return lines


@pytest.fixture(autouse=True)
def _interactive_glyphs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the comparison to the glyph set the homepage actually depicts.

    ``zenzic.core.ui`` turns emoji off whenever ``CI`` is set, swapping in ASCII
    fallbacks — ``x`` for ``✘``, ``!`` for ``⚠``, ``i`` for ``💡``, ``-`` for
    ``•`` — because many CI log viewers mangle multi-byte characters. That is
    correct behaviour, but it means one scan has two valid renderings, and the
    block on the page necessarily shows one of them: the interactive one, which
    is what a developer sees in their own terminal.

    Without this the suite passed locally and failed on every runner, comparing
    a Unicode page against ASCII output and reporting it as content drift. The
    fixture is autouse so a future test in this file cannot reintroduce the
    split by forgetting to ask for it.
    """
    monkeypatch.setattr("zenzic.core.ui.SUPPORTS_EMOJI", True)


@pytest.fixture
def real_output(tmp_path: Path) -> str:
    for rel, text in _FIXTURE.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (tmp_path / "docs/assets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/assets/unused.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    result = CliRunner().invoke(
        app, ["check", "all", str(tmp_path / "docs"), "--no-header"], catch_exceptions=False
    )
    # Exit 2 is the whole point of the depicted run: a credential breach.
    assert result.exit_code == 2, f"fixture no longer breaches: {result.output}"
    return re.sub(r"\s+", " ", result.output)


def test_every_depicted_line_appears_in_real_cli_output(real_output: str) -> None:
    lines = _visible_lines()
    assert len(lines) > 15, f"extraction produced too little to be meaningful: {lines!r}"

    missing = [line for line in lines if line not in real_output]
    assert not missing, (
        "the homepage terminal block shows lines the CLI does not print:\n  "
        + "\n  ".join(repr(m) for m in missing)
        + "\n\nRegenerate the block from a real run, or update the fixture in this "
        "test if the depicted scenario changed."
    )


def test_the_block_gains_carets_and_context_when_the_cli_starts_emitting_them(
    real_output: str,
) -> None:
    """The reverse direction: the CLI printing *more* than the block shows.

    The parity test above is one-directional — it catches the block claiming
    output the CLI does not produce, but not the CLI producing output the block
    omits. That gap matters right now: ``_render_snippet`` draws two context
    lines and a ``^^^^`` caret under the offending token, but every finding
    currently falls back to a bare one-line frame because ``reporter.py``
    composes the snippet path as ``docs_root / rel_path`` where ``rel_path`` is
    already project-relative (tracked internally). When that is fixed,
    real output grows rows the homepage does not show, and the block must be
    regenerated in the same change rather than quietly under-selling the tool.
    """
    # Unconditional on both sides. A conditional check would pass vacuously if
    # the depicted scenario were ever changed to one whose findings carry no
    # column data — the block would show only flat frames and still look
    # "in parity", quietly under-selling the tool's best output.
    assert re.search(r"\^\^\^", real_output), (
        "the depicted scenario no longer produces a single caret row, so the "
        "homepage would showcase only bare frames — choose a fixture whose "
        f"findings carry column positions:\n{real_output}"
    )
    depicted = " ".join(_visible_lines())
    assert "^^^" in depicted, (
        "real output carries caret rows but the homepage terminal block shows "
        "none — regenerate execution_layer.html from a current capture"
    )
    assert "│" in depicted, (
        "the block shows no multi-line context frame, only bare ❱ lines — "
        "regenerate it from a current capture"
    )


def test_the_signature_lines_are_actually_present(real_output: str) -> None:
    """Guards the guard: a broken extractor would vacuously pass the test above."""
    lines = _visible_lines()
    for expected in (
        "✘ SECURITY BREACH DETECTED [LIKELY PLACEHOLDER]",
        "DQS Final Score: 0/100 (Security Override — 1 non-suppressible finding detected)",
    ):
        assert expected in lines, f"{expected!r} not extracted from the partial: {lines!r}"
        assert expected in real_output, f"{expected!r} not in real CLI output"


# ─── Generated family blocks ──────────────────────────────────────────────────
#
# The tests above pin ONE hand-built artifact by an absolute path. These glob
# instead, so a new block gains verification by existing rather than by someone
# remembering to register it — and the registration check below runs in both
# directions, so a block with no entry fails the suite instead of shipping as
# unverified quoted output.

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from generate_lab_blocks import BLOCKS, SNIPPET_DIR, capture  # noqa: E402


def test_every_generated_block_is_registered_and_every_registration_has_a_block() -> None:
    """Both directions, because each fails differently.

    A block on disk with no entry in `BLOCKS` is a file nothing verifies — the
    exact shape this whole exercise exists to avoid. An entry with no file is a
    block someone deleted or never generated, and without this the glob below
    would simply iterate over less and report green.
    """
    on_disk = {p.name for p in SNIPPET_DIR.glob("lab-*.txt")} if SNIPPET_DIR.is_dir() else set()
    registered = set(BLOCKS)
    assert on_disk == registered, (
        f"blocks on disk and registrations disagree.\n"
        f"  unregistered files (verified by nothing): {sorted(on_disk - registered)}\n"
        f"  registered but absent (never generated):  {sorted(registered - on_disk)}"
    )


@pytest.mark.parametrize("block_name", sorted(BLOCKS))
def test_every_line_of_a_generated_block_appears_in_real_output(block_name: str) -> None:
    """Every depicted line must be a line the command actually prints.

    The comparison is the same one the homepage block gets, against output
    produced at test time by running the command the block is registered
    against — not against a stored copy, which would only prove the file equals
    itself.
    """
    block = SNIPPET_DIR / block_name
    assert block.is_file(), f"{block_name} is registered but absent; run `just lab-blocks`"
    real = re.sub(r"\s+", " ", capture(BLOCKS[block_name]))

    missing: list[str] = []
    for raw in block.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or _VOLATILE.search(line):
            continue
        if re.sub(r"\s+", " ", line) not in real:
            missing.append(line)
    assert not missing, (
        f"{block_name} shows {len(missing)} line(s) the command does not print:\n  "
        + "\n  ".join(missing[:8])
        + "\nRegenerate with `just lab-blocks`."
    )


def test_a_generated_block_is_not_empty() -> None:
    """A block of nothing would satisfy the line check vacuously.

    The per-line test above iterates the file's lines; an empty file has none,
    so it passes while depicting nothing. This is that test's floor.
    """
    for name in sorted(BLOCKS):
        block = SNIPPET_DIR / name
        if not block.is_file():
            continue
        real_lines = [
            ln
            for ln in block.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not _VOLATILE.search(ln)
        ]
        assert len(real_lines) >= 4, (
            f"{name} carries {len(real_lines)} comparable line(s) — too few to be "
            "a depiction of anything"
        )
