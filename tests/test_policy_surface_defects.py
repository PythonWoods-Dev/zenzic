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
import subprocess
import sys
from pathlib import Path

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
    code = "import sys; from zenzic.main import cli_main; sys.argv = ['zenzic', *sys.argv[1:]]; cli_main()"
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"NO_COLOR": "1", "COLUMNS": "200", "PATH": "", "HOME": str(root)},
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
