# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The machine-readable outputs, on the case a consumer actually meets.

Both output contracts have a real consumer: `zenzic-action`'s wrapper parses the
JSON payload, and GitHub ingests the SARIF and turns it into pull-request
annotations. Neither had been exercised against a **stale route manifest**,
which is the state that produces the worst annotation Zenzic can emit — `Z101`,
"broken link", on a link that is correct.

If `Z115` explained that only in the terminal, a user would get the wrong
annotation in their pull request with the explanation nowhere near it, which is
worse than either alone. These pin that it reaches both formats, that the SARIF
still validates against the OASIS schema with a code that did not exist last
week in it, and that the JSON payload's shape is what the wrapper reads.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest


_SCHEMA = Path(__file__).resolve().parent / "fixtures" / "sarif-2.1.0-schema.json"

#: The payload keys `zenzic-action`'s wrapper reads. Adding a key is backward
#: compatible for a consumer that reads by name; removing one, or changing what
#: a value means, is not. Pinned so an addition is a decision rather than a
#: surprise.
_WRAPPER_KEYS = {
    "findings",
    "security_breaches",
    "security_incidents",
    "suppression_cap",
    "suppression_count",
    "suppression_debt_pts",
    "debt_status",
}


@pytest.fixture
def stale_manifest_project(tmp_path: Path) -> Path:
    """A `prebuilt` project whose manifest has fallen one page behind."""
    docs = tmp_path / "docs"
    docs.mkdir()
    body = " ".join(["word"] * 60)
    (docs / "index.md").write_text(
        f"# Home\n\n{body}\n\nSee the [guide](new.md).\n", encoding="utf-8"
    )
    (docs / "new.md").write_text(f"# Just added\n\n{body}\n", encoding="utf-8")
    (tmp_path / ".zenzic-vsm.json").write_text(
        '{"index.md": {"url": "/", "status": "REACHABLE"}}', encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _emit(project: Path, fmt: str) -> str:
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all", "--format", fmt],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )
    start = out.stdout.find("{")
    assert start >= 0, f"no payload:\n{out.stdout}\n{out.stderr}"
    return out.stdout[start:]


def test_the_explanation_reaches_sarif_beside_the_symptom(stale_manifest_project: Path) -> None:
    """The case that matters most: a wrong annotation with its cause attached."""
    sarif = json.loads(_emit(stale_manifest_project, "sarif"))
    results = {r["ruleId"]: r["level"] for r in sarif["runs"][0]["results"]}

    assert results.get("Z101") == "error", results
    assert results.get("Z115") == "warning", (
        "Z115 explains the Z101 in the terminal and not in the pull request, "
        f"which is worse than either alone. Results: {results}"
    )


def test_a_code_that_did_not_exist_last_week_still_validates(
    stale_manifest_project: Path,
) -> None:
    """GitHub rejects a SARIF file that does not match the schema, so a new code
    reaching it is a schema question, not only a rendering one."""
    sarif = json.loads(_emit(stale_manifest_project, "sarif"))

    jsonschema.validate(instance=sarif, schema=json.loads(_SCHEMA.read_text(encoding="utf-8")))

    declared = {rule["id"] for rule in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "Z115" in declared, (
        "a result whose ruleId is in no declared rule leaves a consumer with a "
        f"code it cannot describe. Declared: {sorted(declared)}"
    )


def test_the_json_payload_is_the_shape_the_wrapper_reads(stale_manifest_project: Path) -> None:
    payload = json.loads(_emit(stale_manifest_project, "json"))

    assert _WRAPPER_KEYS <= set(payload), (
        f"the wrapper reads keys this payload does not carry: {_WRAPPER_KEYS - set(payload)}"
    )
    assert {f["code"] for f in payload["findings"]} >= {"Z101", "Z115"}


def test_the_engine_field_was_added_additively(stale_manifest_project: Path) -> None:
    """The guard that was here fired, and this is the decision it asked for.

    It used to assert that no `engine` key existed, with the message *"decide
    whether it is additive before shipping it"*. `engine` shipped in v0.31.0,
    and it is additive: a **new** top-level key, and no existing key changed
    meaning to make room for it. A consumer reading by name is unaffected; one
    that had been inferring the adapter from the findings can now stop.

    Asserted on the emitted payload rather than on the source text, which is
    what the earlier form could not do.
    """
    project = stale_manifest_project
    payload = json.loads(_emit(project, "json"))

    engine = payload.get("engine")
    assert isinstance(engine, dict), f"`engine` must be an object, got {engine!r}"
    assert set(engine) >= {"declared", "resolved", "substituted"}, engine
    assert isinstance(engine["substituted"], bool), engine

    # The additive half: the keys that were there before are still there, with
    # the same names. A key repurposed to carry the engine would be the change
    # the original guard existed to prevent.
    for key in (
        "findings",
        "security_breaches",
        "security_incidents",
        "suppression_count",
        "suppression_cap",
        "suppression_debt_pts",
        "debt_status",
    ):
        assert key in payload, f"{key} disappeared from the payload"


def test_the_metadata_engine_on_the_sarif_path_never_runs_a_rule(
    stale_manifest_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The property that keeps `--format sarif` cheap and side-effect-free.

    The engine built on that path exists only to read `RuleMetadata` for the
    SARIF `rules` array — `containers=None` is deliberate there, and `run()` is
    never called on it. It is recorded in seven comments across `_check.py` and
    enforced by nothing, so an edit that started executing rules to enrich the
    output would be silent.

    The scan's *own* engine does run rules, and it is the same class, so a
    class-level patch cannot tell them apart. The instances built with
    `containers=None` are tagged as they are constructed, and only those are
    forbidden — which is the claim, stated exactly.
    """
    from typer.testing import CliRunner

    from zenzic.core import scanner
    from zenzic.core.rules import AdaptiveRuleEngine
    from zenzic.main import app

    _build = scanner._build_rule_engine
    tagged: set[int] = set()

    def _tagging_build(config: object, *, containers: object = None, **kw: object) -> object:
        engine = _build(config, containers=containers, **kw)  # type: ignore[arg-type]
        if containers is None and engine is not None:
            tagged.add(id(engine))
        return engine

    monkeypatch.setattr(scanner, "_build_rule_engine", _tagging_build)
    monkeypatch.setattr("zenzic.cli._check._build_rule_engine", _tagging_build, raising=False)

    violations: list[str] = []
    for name in ("run", "run_vsm"):
        original = getattr(AdaptiveRuleEngine, name)

        def _guard(self: object, *a: object, _n: str = name, _o: object = original, **k: object):
            if id(self) in tagged:
                violations.append(_n)  # CONTROL-POINT
            return _o(self, *a, **k)  # type: ignore[operator]

        monkeypatch.setattr(AdaptiveRuleEngine, name, _guard)

    monkeypatch.chdir(stale_manifest_project)
    result = CliRunner().invoke(app, ["check", "all", "--format", "sarif"])

    assert result.exit_code in (0, 1), result.output
    assert "Z115" in result.output, "the run produced no SARIF to reason about"
    assert tagged, (
        "no engine was built with containers=None, so this test exercised nothing — "
        "the SARIF path stopped building a metadata engine, or stopped going through "
        "`_build_rule_engine`"
    )
    assert not violations, (
        f"the metadata engine executed {sorted(set(violations))}; it is built to be read, "
        "not run, and `containers=None` means it would run them without their containers"
    )
