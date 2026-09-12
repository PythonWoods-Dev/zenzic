# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``--format json`` must let a consumer locate every finding, from any command.

``check all`` is the command a CI is most likely to run, and its JSON was the one
a machine could not read: ``references[]`` carried the location and the code
inside a pre-formatted English string, and ``links[]`` carried neither — just the
message, so a link finding could not be resolved to a file at all. Every
per-check command already emitted ``{rel_path, line_no, code, severity,
message}``.

The fix is additive: a ``findings[]`` array beside the existing keys, in the
per-check shape. The grouped string arrays stay, because they are a published
contract and consumers parse them today.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()

_CONFIG = """\
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
"""

_FILES = {
    "docs/index.md": """\
        # Index

        A page whose findings span the pipeline: a broken page link, a missing
        asset, an absolute path, and — on the last line, deliberately — two
        findings that differ only by column, which is the case a line-only
        location cannot represent.

        - [gone](./gone.md)
        - <a href="./missing.png">asset</a>
        - [absolute](/somewhere)
        - <a href="#" data-track="x">jump</a>
        """,
}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    (tmp_path / ".zenzic.toml").write_text(_CONFIG, encoding="utf-8")
    for rel, body in _FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp_path


def _json(corpus: Path, *args: str) -> dict[str, Any]:
    result = runner.invoke(app, [*args, "--format", "json"], catch_exceptions=False)
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def test_check_all_json_carries_a_structured_findings_array(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every finding resolvable to a file, a line and a code — from the aggregate."""
    monkeypatch.chdir(corpus)
    payload = _json(corpus, "check", "all")

    assert "findings" in payload, "the aggregate payload has no findings array"
    assert payload["findings"], "the corpus produced no findings, so this proves nothing"
    for f in payload["findings"]:
        assert set(f) >= {"rel_path", "line_no", "code", "severity", "message"}, f
        assert f["rel_path"], f
        assert f["code"].startswith("Z"), f


def test_the_grouped_string_arrays_are_still_present(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Additive means additive: a consumer parsing the old keys keeps working.

    These arrays are why the fix is not simply "emit the right shape" — replacing
    them would break every consumer reading them today.
    """
    monkeypatch.chdir(corpus)
    payload = _json(corpus, "check", "all")
    for key in ("links", "references", "orphans", "snippets", "unused_assets", "nav_contract"):
        assert key in payload, key
    assert any(isinstance(x, str) for x in payload["references"]), payload["references"]


def test_aggregate_and_per_check_json_agree_on_shared_codes(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same finding must be the same triple in both payloads.

    Not merely "both have a findings array": a consumer switching between
    ``check all`` and ``check references`` must resolve the same finding to the
    same file and line, or the two contracts only look alike.
    """
    monkeypatch.chdir(corpus)

    def triples(payload: dict[str, Any]) -> set[tuple[str, int, str]]:
        return {(f["rel_path"], f["line_no"], f["code"]) for f in payload["findings"]}

    aggregate = triples(_json(corpus, "check", "all"))
    per_check = triples(_json(corpus, "check", "references"))
    shared = {c for _, _, c in aggregate} & {c for _, _, c in per_check}
    assert shared, "no code is emitted by both commands, so there is nothing to compare"

    assert {t for t in aggregate if t[2] in shared} == {t for t in per_check if t[2] in shared}, (
        "the aggregate and per-check payloads disagree about codes they both report"
    )


def test_the_finding_shape_has_one_definition() -> None:
    """Both emitters build it through the same helper.

    Two hand-written copies of the same dictionary literal is the defect this
    cycle spent two directives on, in a different module. One helper, or the two
    payloads drift the day either gains a field.
    """
    import inspect

    from zenzic.cli import _shared

    for emitter in (_shared._output_json_findings, _shared._output_check_all_json_findings):
        assert "_finding_dict" in inspect.getsource(emitter), emitter.__name__


# ── the column, which every format knew and no machine format carried ────────


def test_json_findings_carry_the_column_when_one_is_known(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two findings on one line are distinguishable only by column.

    The engine knows it — the text output prints `docs/index.md:9:14` — and both
    machine formats dropped it, so a consumer saw two findings at line 9 with no
    way to tell which construct each was about.
    """
    monkeypatch.chdir(corpus)
    payload = _json(corpus, "check", "all")
    by_line: dict[int, list[dict[str, Any]]] = {}
    for f in payload["findings"]:
        by_line.setdefault(f["line_no"], []).append(f)
    crowded = [fs for fs in by_line.values() if len(fs) > 1]
    assert crowded, "no line carries two findings, so this proves nothing"

    for f in payload["findings"]:
        assert "col_start" in f, f
    assert any(f["col_start"] > 0 for f in payload["findings"]), (
        "no finding reported a column at all"
    )


def test_sarif_regions_carry_a_one_based_column(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SARIF is the higher-stakes format: a wrong field renders as a finding.

    GitHub Code Scanning underlines `region`. With `startLine` alone it highlights
    the whole line, so two findings about different attributes of the same tag
    were indistinguishable in the interface. `startColumn` is **1-based** in SARIF
    while the engine's `col_start` is 0-based, which is the off-by-one this asserts
    against the real source text rather than against the emitter.
    """
    monkeypatch.chdir(corpus)
    result = runner.invoke(app, ["check", "all", "--format", "sarif"], catch_exceptions=False)
    run = json.loads(result.stdout)["runs"][0]

    source = (corpus / "docs/index.md").read_text(encoding="utf-8").splitlines()
    # The 0-based column the engine reported for the same finding. Cross-checking
    # the two payloads is what makes the base assertable: "1 <= col <= line
    # length" is satisfied by an off-by-one too, so it would pass either way.
    zero_based = {
        (f["rel_path"], f["line_no"], f["code"]): f["col_start"]
        for f in _json(corpus, "check", "all")["findings"]
    }

    checked = 0
    for res in run["results"]:
        loc = res["locations"][0]["physicalLocation"]
        region = loc["region"]
        assert "startLine" in region, res
        if "startColumn" not in region:
            continue
        col = region["startColumn"]
        key = (loc["artifactLocation"]["uri"], region["startLine"], res["ruleId"])
        assert key in zero_based, f"SARIF reported a finding the JSON payload does not: {key}"
        assert col == zero_based[key] + 1, (
            f"{res['ruleId']}: SARIF startColumn is 1-based and col_start is 0-based, "
            f"so {zero_based[key]} must serialise as {zero_based[key] + 1}, got {col}"
        )
        # And the character it names must be the start of something, never the
        # whitespace before it — the symptom an off-by-one actually produces.
        line = source[region["startLine"] - 1]
        assert col <= len(line), f"{res['ruleId']} column {col} is past the line end"
        assert not line[col - 1].isspace(), (
            f"{res['ruleId']} points at whitespace in {line!r} at 1-based column {col}"
        )
        checked += 1
    assert checked, "no SARIF result carried a column, so the assertion never ran"


def test_sarif_declares_the_unit_its_columns_are_counted_in(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A column without a declared unit is a number a consumer has to guess.

    SARIF defaults to UTF-16 code units. Zenzic counts Python string indices,
    which are code points, and the two diverge on any line with a non-BMP
    character. Emitting a column while leaving the unit implicit would be a
    plausible-looking underline in the wrong place — the failure mode this format
    specialises in.
    """
    monkeypatch.chdir(corpus)
    result = runner.invoke(app, ["check", "all", "--format", "sarif"], catch_exceptions=False)
    assert json.loads(result.stdout)["runs"][0]["columnKind"] == "unicodeCodePoints"


# ── cross-format agreement ────────────────────────────────────────────────────


def test_text_json_and_sarif_report_the_same_findings(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One command, three formats, one set of findings.

    Nothing required the output formats to agree with each other. Documentation
    parity is a rule; format parity was not, and no check could have noticed the
    aggregate JSON reporting link findings with no location while the text output
    printed file, line and column for the same finding.

    A test rather than a rule, for the reason a rule would itself give: a standing
    instruction with no mechanical check is one the next change can override. This
    runs in under a second and fails naming the format that diverged.
    """
    monkeypatch.chdir(corpus)

    def text_triples() -> set[tuple[str, int, str]]:
        out = runner.invoke(app, ["check", "all", "--no-header"], catch_exceptions=False).stdout
        pattern = re.compile(r"^(?P<path>\S+?):(?P<line>\d+)(?::\d+)?\s+\S+\s+\[(?P<code>Z\d{3})\]")
        found = set()
        for raw in out.splitlines():
            m = pattern.match(raw.strip())
            if m:
                found.add((m.group("path"), int(m.group("line")), m.group("code")))
        return found

    def json_triples() -> set[tuple[str, int, str]]:
        return {
            (f["rel_path"], f["line_no"], f["code"])
            for f in _json(corpus, "check", "all")["findings"]
        }

    def sarif_triples() -> set[tuple[str, int, str]]:
        out = runner.invoke(
            app, ["check", "all", "--format", "sarif"], catch_exceptions=False
        ).stdout
        run = json.loads(out)["runs"][0]
        return {
            (
                r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
                r["locations"][0]["physicalLocation"]["region"]["startLine"],
                r["ruleId"],
            )
            for r in run["results"]
        }

    text, js, sarif = text_triples(), json_triples(), sarif_triples()
    assert text, "the corpus produced no text findings, so this proves nothing"

    assert js == sarif, (
        "JSON and SARIF disagree:\n"
        f"  only in JSON:  {sorted(js - sarif)}\n"
        f"  only in SARIF: {sorted(sarif - js)}"
    )
    # Text is compared last and by code multiset rather than by triple: it clamps
    # a file-level finding to line 1 for display, so the location can legitimately
    # differ while the finding set must not.
    assert sorted(c for _, _, c in text) == sorted(c for _, _, c in js), (
        "the text output and the machine formats report different findings:\n"
        f"  text: {sorted(c for _, _, c in text)}\n"
        f"  json: {sorted(c for _, _, c in js)}"
    )
