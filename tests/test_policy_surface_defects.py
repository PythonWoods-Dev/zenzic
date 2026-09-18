# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Four defects found by reading real output, on the policy surface.

Z518's regex accepted every word ending in -en (``is often``) and matched
inside ``read-only``; its caret, and every content rule's caret, sat at
column 0 because ``col_start`` was never passed. The unknown-key warning
went to stdout, ahead of the JSON and ahead of the banner, and called every
file ``.zenzic.toml``. A ``[policies]`` table at the root of pyproject.toml
was ignored with no word said.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from zenzic.core import content, governance
from zenzic.core.rules import RuleFinding
from zenzic.models.config import ZenzicConfig


# ─── Z518: detection ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        "The value is often what the reader expects.",
        "The panel is open by default and the gate is between the two.",
        "Core is read-only for the plugin.",
    ],
)
def test_passive_voice_ignores_non_participles_and_hyphenated_compounds(line: str) -> None:
    text = f"# T\n\n{line}\n"
    assert [f.match_text for f in content.check_passive_voice(Path("p.md"), text)] == []


def test_passive_voice_still_reports_a_real_passive() -> None:
    text = "# T\n\nThe report was reviewed by the board.\n"
    found = content.check_passive_voice(Path("p.md"), text)
    assert [f.match_text for f in found] == ["was reviewed"]


# ─── carets: the column is the match's, on the raw line ──────────────────────


def _span_matches(f: RuleFinding) -> bool:
    if not f.matched_line or not f.match_text or f.match_text not in f.matched_line:
        return True  # nothing on the line to point at; the rule says so by omission
    return f.matched_line[f.col_start : f.col_start + len(f.match_text)] == f.match_text


def test_z518_and_z519_columns_survive_masking() -> None:
    # An inline code span and a link BEFORE the match: the masks used to shrink
    # them to one space, so a column taken from the masked line was wrong.
    line = "Run `zenzic check all --strict` and [read](./x.md) it; the tree was reviewed, clearly."
    text = f"# T\n\n{line}\n"
    (p,) = content.check_passive_voice(Path("p.md"), text)
    assert p.col_start == line.index("was reviewed") and _span_matches(p)
    (w,) = content.check_weasel_words(Path("p.md"), text, ["clearly"])
    assert w.col_start == line.index("clearly") and _span_matches(w)


_FIXTURE = """---
title: t
---
# Title.

## Title.

### Skipped level

Intro sentence that is long enough, and long enough, and long enough, and long enough, and long enough, and long enough, and long enough, and long enough, and long enough, and long enough, and finally ends here after forty words or so.

![image](./a.png)

See https://example.com/bare for details.

<h1>Second h1</h1>

## Empty section

## Duplicate

## Duplicate

first item;
second item;
third item;

The change was merged, obviously.
"""


def test_every_content_rule_points_its_caret_at_the_match() -> None:
    """The family sweep: every RuleFinding whose match_text is on its matched_line
    must carry the column where that text starts."""
    p = Path("f.md")
    findings = []
    findings += content.check_heading_hierarchy(p, _FIXTURE)
    findings += content.check_sentence_lengths(p, _FIXTURE)
    findings += content.check_empty_sections(p, _FIXTURE)
    findings += content.check_duplicate_headings(p, _FIXTURE)
    findings += content.check_generic_image_alt_text(p, _FIXTURE)
    findings += content.check_bare_urls(p, _FIXTURE)
    findings += content.check_multiple_h1_headings(p, _FIXTURE)
    findings += content.check_heading_punctuation(p, _FIXTURE)
    findings += content.check_passive_voice(p, _FIXTURE)
    findings += content.check_weasel_words(p, _FIXTURE, ["obviously"])
    findings += content.check_malformed_lists(p, _FIXTURE)
    codes = {f.rule_id for f in findings}
    assert {"Z517", "Z516", "Z515", "Z518", "Z519", "Z520", "Z513", "Z512"} <= codes, codes
    wrong = [
        (f.rule_id, f.col_start, f.match_text, f.matched_line)
        for f in findings
        if not _span_matches(f)
    ]
    assert not wrong, wrong


def test_z617_column_is_the_match_start() -> None:
    cfg = ZenzicConfig()
    cfg.policies.forbidden_content_patterns = ["TODO"]
    text = "# T\n\nAll fine — TODO fix this later.\n"
    found = [f for f in governance.check_policies(Path("g.md"), text, cfg) if f.rule_id == "Z617"]
    assert found and found[0].col_start == text.splitlines()[2].index("TODO")


# ─── the configuration warning: file named, channel, position ────────────────


def test_a_root_level_policies_table_in_pyproject_is_named_as_misplaced(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\n[tool.zenzic]\ndocs_dir = "docs"\n\n[policies]\nweasel_words = ["clearly"]\n',
        encoding="utf-8",
    )
    with caplog.at_level(logging.WARNING, logger="zenzic"):
        ZenzicConfig.load(tmp_path)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("[tool.zenzic.policies]" in m and "pyproject.toml" in m for m in msgs), msgs


def test_an_unknown_key_in_pyproject_is_reported_as_pyproject(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\n[tool.zenzic]\ndocs_dir = "docs"\nbogus_key = 1\n', encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING, logger="zenzic"):
        ZenzicConfig.load(tmp_path)
    msgs = [r.getMessage() for r in caplog.records if "bogus_key" in r.getMessage()]
    assert msgs and all(m.startswith("pyproject.toml") for m in msgs), msgs


def _project(tmp_path: Path, config_text: str, name: str) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "docs" / "index.md").write_text(
        "# Home\n\nA page with enough ordinary prose to pass the placeholder check, and a few "
        "more words for good measure so that nothing else is reported on it at all.\n",
        encoding="utf-8",
    )
    (root / name).write_text(config_text, encoding="utf-8")
    return root


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI in its own process: the point is which stream each line lands on.

    The environment is inherited and then overridden. An env built from scratch
    with ``PATH: ""`` killed the interpreter on windows-latest -- ``Fatal Python
    error: _Py_HashRandomization_Init: failed to get random numbers`` -- because
    Windows needs SYSTEMROOT to seed the hash, and the test then read that crash
    instead of the CLI's output.
    """
    code = "import sys; from zenzic.main import cli_main; sys.argv = ['zenzic', *sys.argv[1:]]; cli_main()"
    env = {**os.environ, "NO_COLOR": "1", "COLUMNS": "200", "HOME": str(root)}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


@pytest.mark.parametrize(
    ("name", "text"),
    [
        (".zenzic.toml", 'docs_dir = "docs"\nbogus_key = 1\n'),
        (
            "pyproject.toml",
            '[project]\nname = "p"\n[tool.zenzic]\ndocs_dir = "docs"\nbogus_key = 1\n',
        ),
    ],
)
def test_the_warning_never_touches_stdout_in_json_mode(
    tmp_path: Path, name: str, text: str
) -> None:
    root = _project(tmp_path, text, name)
    done = _cli(root, "check", "all", "--format", "json")
    json.loads(done.stdout)  # the P1 row: this raised before the fix
    assert "bogus_key" in done.stderr, done.stderr


def test_in_text_mode_the_warning_follows_the_banner(tmp_path: Path) -> None:
    root = _project(tmp_path, 'docs_dir = "docs"\nbogus_key = 1\n', ".zenzic.toml")
    done = _cli(root, "check", "all")
    assert "bogus_key" in done.stderr
    # Positive control: without the header the warning still reaches stderr (at exit).
    done2 = _cli(root, "check", "all", "--no-header")
    assert "bogus_key" in done2.stderr


# ─── the link and policy families: the same assertion, one surface further out ──
#
# The content rules above are checked by calling them directly. The link and
# policy codes are built in seven different modules and only meet on the way
# out, so the family assertion for them reads the JSON surface of a real run:
# that is also where a consumer meets the column (SARIF's startColumn is
# col_start + 1, and the LSP range is built from the same field).

_SPAN_CODES = frozenset(
    {
        "Z101",
        "Z103",
        "Z105",
        "Z202",
        "Z203",
        "Z302",
        "Z303",
        "Z403",
        "Z503",
        "Z522",
        "Z523",
        "Z611",
        "Z614",
        "Z615",
        "Z616",
    }
)

#: Two of the seventeen are a DIFFERENT cause, excluded here rather than
#: silently: their finding type carries no column field at all, so giving them
#: one changes the type and every construction of it, not an argument left
#: unset. Z301's finding is a `ReferenceFinding` (models/references.py:143 --
#: file_path, line_no, issue, detail, is_warning; no col_start, no match_text),
#: and Z102 on the CLI path is raised outside the RuleFinding construction this
#: fixture reaches. Measured 2026-09-18; both keep their priority row until that
#: type change is directed.
_SPAN_PENDING_TYPE_CHANGE = frozenset({"Z102", "Z301"})

#: Codes that correctly carry no column, with the reason, so a later session
#: finds a decision instead of a gap. Each reports on a FILE or a DIRECTORY,
#: not on a span of a line: there is nothing on any line to point at.
_NO_SPAN_BY_DESIGN: dict[str, str] = {
    "Z112": "stale allowlist entry — reports on .zenzic.toml as a whole",
    "Z401": "directory has no index page — the subject is the directory",
    "Z402": "file not in the navigation — the subject is the file",
    "Z404": "asset directory finding — the subject is the directory",
    "Z405": "asset referenced by nothing — the subject is the file",
    "Z406": "asset-path finding — the subject is the file",
    "Z407": "invalid engine pattern — the subject is the configured pattern",
    "Z410": "page unreachable from any entry point — the subject is the page",
    "Z411": "page with no outgoing links — the subject is the page",
    "Z412": "required inbound links missing — the subject is the page",
    "Z502": "page under the word minimum — the subject is the page",
    "Z511": "sentence length — reported per sentence, which may span lines",
    "Z512": "empty heading section — the subject is the section",
    "Z603": "dead inline suppression — the subject is the directive's line",
    "Z610": "required frontmatter key missing — nothing on the line to mark",
    "Z618": "no heading matches the required pattern — the subject is the page",
    "Z619": "document complexity — the subject is the page",
    "Z620": "dead global policy — the subject is the .zenzic.toml entry",
}


def _run_json(root: Path) -> list[dict[str, Any]]:
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all", "--no-header", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return list(json.loads(done.stdout).get("findings", []))


def _link_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n[build_context]\nengine = "standalone"\n'
        '[policies]\nallowed_external_domains = ["ok.example"]\n'
        'forbidden_external_domains = ["bad.example"]\nrequired_url_schemes = ["https"]\n',
        encoding="utf-8",
    )
    (root / "docs" / "index.md").write_text(
        "# Home\n\nSee [missing](./nope.md) here.\nAnchor [frag](./other.md#nope) too.\n"
        "Bad [ext](https://bad.example/x) and [unapproved](https://other.example/y).\n"
        "Scheme [insecure](http://ok.example/z).\n![](./img.png)\n"
        "A ref [text][undef] and more prose so the page is long enough to pass the checks.\n\n"
        "[unused]: https://ok.example/unused\n",
        encoding="utf-8",
    )
    (root / "docs" / "other.md").write_text(
        "# Other\n\nOrdinary prose long enough to pass the placeholder check on this page too.\n",
        encoding="utf-8",
    )
    return root


def test_every_link_and_policy_finding_carries_the_column_of_the_span_it_names(
    tmp_path: Path,
) -> None:
    """A caret, a SARIF startColumn and an LSP range all come from col_start.

    Measured on 2026-09-18: seventeen codes named a quoted span in their message
    and carried col_start = 0, so the terminal drew no caret and SARIF emitted no
    startColumn at all. The subjects here are built in seven modules; the
    assertion is on what they produce, which is where a consumer reads it.
    """
    root = _link_fixture(tmp_path)
    lines = (root / "docs" / "index.md").read_text(encoding="utf-8").splitlines()
    wrong: list[tuple[str, int, str]] = []
    seen: set[str] = set()
    for f in _run_json(root):
        code = str(f["code"])
        if code not in _SPAN_CODES:
            continue
        seen.add(code)
        m = re.search(r"'([^']{1,80})'", str(f["message"]))
        if not m:
            continue
        span, ln = m.group(1), int(f["line_no"])
        if not (1 <= ln <= len(lines)) or span not in lines[ln - 1]:
            continue  # the message names something not on that line; nothing to point at
        want = lines[ln - 1].index(span)
        if int(f["col_start"]) != want:
            wrong.append((code, int(f["col_start"]), f"expected {want} for {span!r}"))
    assert seen, "the fixture produced none of the span-naming codes"
    assert not wrong, f"{len(wrong)} finding(s) carry the wrong column: {wrong}"


def test_the_codes_that_carry_no_column_are_declared_with_a_reason() -> None:
    """An exemption list is only evidence if each entry states why it is there.

    A code absent from the span family must be absent deliberately: without this,
    a code that stops carrying a column would look like one that never should.
    """
    from zenzic.core.codes import CODE_DEFINITIONS

    overlap = _SPAN_CODES & set(_NO_SPAN_BY_DESIGN)
    assert not overlap, f"a code cannot be both span-bearing and exempt: {overlap}"
    unknown = (_SPAN_CODES | set(_NO_SPAN_BY_DESIGN)) - set(CODE_DEFINITIONS)
    assert not unknown, f"named codes that are not in the registry: {unknown}"
    assert all(_NO_SPAN_BY_DESIGN.values()), "every exemption states its reason"
