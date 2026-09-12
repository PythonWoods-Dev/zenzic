# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every JSON the CLI emits validates against the published schema, both ways.

`test_schema_validation.py` already validated `check all --format json`. It did
so against **one** example, and that is the hole this file exists to close: four
of the seven arrays in that payload were empty there, so their *item* schemas
were never exercised. An array declared `{"type": "array", "items": {...}}`
validates trivially when it is `[]`, no matter what the item schema says — a
field could be added to `snippets[]`, or removed from it, and the suite would
stay green.

Two further gaps came out of the same look:

* The six `zenzic check <subcommand>` commands emit `{"findings", "summary"}`,
  which matched **no branch** of the schema's `oneOf`. A consumer validating
  against the published contract would have rejected the tool's own output.
  Declared as `perCheckReport` in v0.31.0.
* Nothing validated any per-check command at all, in any format.

BOTH DIRECTIONS, because they fail differently and only one of them is caught
by `jsonschema` on its own:

* **Emitted but not declared** — `jsonschema.validate` catches it, via
  `additionalProperties: false`. Asserted explicitly anyway, so the protection
  does not silently depend on that keyword surviving a schema edit.
* **Declared but never emitted** — `jsonschema` cannot catch this by
  construction: an optional property that nothing produces is valid forever,
  and a *required* one is only caught if some payload reaches that branch. This
  is the direction that lets a schema describe a field the code stopped
  emitting, which is the same class as a document describing a flag that was
  removed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "zenzic-output.schema.json"

#: One example per array that the aggregate payload can populate, so the union
#: of their outputs exercises every item schema. Chosen by running each and
#: reading which arrays came back non-empty -- not by matching names to codes.
CORPUS = (
    "z101-broken-links",  # links[], references[]
    "z402-orphan-page",  # orphans[]
    "z405-unused-assets",  # unused_assets[]
    "z503-snippet-error",  # snippets[]
    "z406-nav-contract",  # nav_contract[]
    "z120-unknown-html-attr",  # the example the original test used
)

#: A security fixture, for the `score` fields that only appear when there is a
#: security finding. Kept out of CORPUS because `check all` here exits on a
#: security breach before the aggregate payload is comparable.
SECURITY_EXAMPLE = "z201-credentials"

#: Declared fields no gallery fixture can reach, each with the reason. This set
#: is the honest half of the assertion: an exemption that is written down is
#: reviewable, and one that is a prefix match is not. Every entry here was first
#: reported BY the assertion, then examined, rather than anticipated.
EXEMPT: frozenset[str] = frozenset(
    {
        # `capExceededReport` — emitted only when the suppression cap is
        # exceeded, which is a governance state rather than a finding, so no
        # findings fixture produces it. Reaching it needs a project built to
        # blow the cap; that fixture does not exist, and this is the statement
        # of that gap rather than a claim of coverage.
        "error",
        "severity",
        "message",
        "remediation",
        "playbook",
        "hotspots",
        "hotspots[].count",
        "hotspots[].path",
        "statistics",
        "statistics.active_suppressions",
        "statistics.configured_global_cap",
        "statistics.excess_debt",
        "statistics.inline_ignores",
        "statistics.per_file_ignores",
        # `score_trend` is emitted as `null` until `.zenzic-history.jsonl`
        # exists, which requires two prior `score --save` runs. The key itself
        # IS emitted and therefore not exempt; only its sub-fields are.
        "score_trend.baseline_score",
        "score_trend.current_score",
        "score_trend.delta",
    }
)

#: Every JSON-emitting invocation. `check all` plus the six subcommands, and
#: `score`, which is a different declared shape.
INVOCATIONS = (
    ("check", "all"),
    ("check", "links"),
    ("check", "orphans"),
    ("check", "snippets"),
    ("check", "references"),
    ("check", "assets"),
    ("check", "placeholders"),
)


def _schema() -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return parsed


#: The console script from the same environment as the interpreter running the
#: tests. NOT `sys.executable -m zenzic`: there is no `zenzic/__main__.py`, so
#: that form fails with "cannot be directly executed" -- and the first version
#: of this file used it. Every invocation returned nothing, `emitted` came back
#: empty, and the unemitted-field assertion then reported EVERY declared field
#: as missing. A harness that could not run produced the maximum number of
#: findings, all of them false. Hence `_runner_works` below.
ZENZIC_BIN = Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")


def _run(example: str, argv: tuple[str, ...], *extra: str) -> subprocess.CompletedProcess[str]:
    cwd = REPO_ROOT / "examples" / example
    if not cwd.is_dir():
        pytest.skip(f"example {example} is absent")
    if not ZENZIC_BIN.exists():
        pytest.fail(f"no zenzic console script at {ZENZIC_BIN}; this suite cannot run")
    return subprocess.run(  # noqa: S603
        [str(ZENZIC_BIN), *argv, ".", *extra],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )


def _emit(example: str, argv: tuple[str, ...]) -> dict[str, Any] | None:
    """Run one invocation in one example and return its parsed JSON.

    A subprocess rather than `CliRunner`: the JSON goes to real stdout, and a
    payload that only parses because a test harness captured it differently is
    not the payload a consumer receives.

    `None` means the command emitted no JSON object, which is a legitimate
    outcome -- Silent-on-Success (ADR-090) means a check with nothing to report
    prints nothing. It does NOT mean the command failed to launch; a launch
    failure raises, because the two must never read the same.
    """
    proc = _run(example, argv, "--format", "json")
    if "No module named" in proc.stderr or "cannot be directly executed" in proc.stderr:
        pytest.fail(f"the runner itself failed for {argv}: {proc.stderr[:200]}")
    start = proc.stdout.find("{")
    if start < 0:
        return None
    try:
        parsed = json.loads(proc.stdout[start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    result: dict[str, Any] = parsed
    return result


def test_the_runner_actually_runs() -> None:
    """Positive control for this file, and the reason it exists.

    Every assertion below reads a set built by `_emit`. If `_emit` returns
    nothing for structural reasons, those sets are empty and the assertions
    either pass vacuously or fail with every field listed at once. Neither
    outcome is about the schema. This fails first and says so.
    """
    payload = _emit(CORPUS[0], ("check", "all"))
    assert payload is not None, (
        f"`{ZENZIC_BIN.name} check all --format json` produced no JSON object in "
        f"examples/{CORPUS[0]}. Nothing else in this file means anything until "
        f"that works."
    )
    assert payload.get("findings"), "the control example reported no findings at all"


def _paths(node: object, prefix: str = "") -> set[str]:
    """Every field path present in a payload, arrays flattened into their items."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{prefix}.{key}" if prefix else key
            found.add(here)
            found |= _paths(value, here)
    elif isinstance(node, list):
        for item in node:
            found |= _paths(item, f"{prefix}[]")
    return found


def _declared(
    schema: dict[str, Any],
    defs: dict[str, Any],
    prefix: str = "",
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    """Every field path the schema declares, following `$ref` and `oneOf`."""
    out: set[str] = set()
    ref = schema.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        if name in seen:
            return out
        target = defs.get(name)
        if isinstance(target, dict):
            out |= _declared(target, defs, prefix, seen | {name})
        return out
    for branch in schema.get("oneOf", []) or []:
        if isinstance(branch, dict):
            out |= _declared(branch, defs, prefix, seen)
    props = schema.get("properties")
    if isinstance(props, dict):
        for key, sub in props.items():
            here = f"{prefix}.{key}" if prefix else key
            out.add(here)
            if isinstance(sub, dict):
                out |= _declared(sub, defs, here, seen)
    items = schema.get("items")
    if isinstance(items, dict):
        out |= _declared(items, defs, f"{prefix}[]", seen)
    return out


@pytest.mark.parametrize("example", CORPUS)
@pytest.mark.parametrize("argv", INVOCATIONS, ids=lambda a: "-".join(a))
def test_every_json_payload_validates_against_the_published_schema(
    example: str, argv: tuple[str, ...]
) -> None:
    """Direction one: nothing is emitted that the schema does not declare."""
    payload = _emit(example, argv)
    if payload is None:
        pytest.skip(f"{' '.join(argv)} produced no JSON object in {example}")
    jsonschema.validate(instance=payload, schema=_schema())


def _score_payload(example: str = CORPUS[0]) -> dict[str, Any]:
    proc = _run(example, ("score",), "--json")
    start = proc.stdout.find("{")
    assert start >= 0, f"score --json emitted no JSON object: {proc.stdout[:300]!r}"
    parsed = json.loads(proc.stdout[start:])
    assert isinstance(parsed, dict)
    payload: dict[str, Any] = parsed
    return payload


def test_score_json_validates() -> None:
    jsonschema.validate(instance=_score_payload(), schema=_schema())


def test_every_item_schema_is_actually_exercised_by_the_corpus() -> None:
    """The hole in the original test, asserted rather than hoped for.

    `check all`'s payload has seven arrays and the single example it was
    validated against populated three. This requires the corpus as a whole to
    produce at least one item in each, so every `items` schema is reached by a
    real payload.
    """
    arrays = (
        "links",
        "orphans",
        "snippets",
        "unused_assets",
        "nav_contract",
        "references",
        "findings",
    )
    populated: dict[str, str] = {}
    for example in CORPUS:
        payload = _emit(example, ("check", "all"))
        if payload is None:
            continue
        for name in arrays:
            value = payload.get(name)
            if isinstance(value, list) and value and name not in populated:
                populated[name] = example
    missing = [a for a in arrays if a not in populated]
    assert not missing, (
        f"no example in the corpus populates {missing}, so their item schemas are "
        f"never validated -- an array that is always [] validates against any item "
        f"schema at all. Add an example that produces one, or remove the array. "
        f"Exercised by: {populated}"
    )


def test_no_declared_field_goes_unemitted() -> None:
    """Direction two: the schema declares nothing the CLI never produces.

    `jsonschema` cannot see this. An optional property nothing emits is valid
    forever, and a required one is only caught when a payload reaches its
    branch. So a schema can keep describing a field the code stopped emitting,
    and every validation stays green -- the same class as a page documenting a
    removed flag.
    """
    schema = _schema()
    defs: dict[str, Any] = schema.get("$defs", {})
    declared = _declared(schema, defs)

    emitted: set[str] = set()
    for example in CORPUS:
        for argv in INVOCATIONS:
            payload = _emit(example, argv)
            if payload is not None:
                emitted |= _paths(payload)
    emitted |= _paths(_score_payload())
    # A security example, because `security_override` and `security_findings`
    # are emitted by `score` only when there is a security finding to report.
    # Added after this assertion listed them: they were reachable all along and
    # the corpus simply had no security fixture in it.
    emitted |= _paths(_score_payload(SECURITY_EXAMPLE))
    assert emitted, "no invocation emitted anything; see test_the_runner_actually_runs"

    unemitted = sorted(d for d in declared if d not in emitted and d not in EXEMPT)
    assert not unemitted, (
        "the schema declares field(s) no command emits anywhere in the corpus:\n  "
        + "\n  ".join(unemitted)
        + "\nEither the CLI stopped emitting them (fix the CLI), or the schema "
        "describes something that no longer exists (fix the schema)."
    )


def test_the_legacy_field_warning_names_both_sections_as_rendered(tmp_path: Path) -> None:
    """The deprecation warning must reach the user with its section names intact.

    It did not. `config.py` emits `'[project_metadata].obsolete_names'` and
    `'[governance].brand_obsolescence'`, through a logger handled by Rich, which
    reads a bracketed word as a markup tag and renders nothing for it. Users saw
    `The '.obsolete_names' field is deprecated. Please move it to
    '.brand_obsolescence'.` -- naming neither section, in the one message whose
    entire purpose is to say where to move a field.

    Asserted against RENDERED output rather than the source string, because the
    source string was always correct. That is the whole defect: reading the code
    confirms nothing here.
    """
    project = tmp_path / "legacy"
    (project / "docs").mkdir(parents=True)
    (project / ".zenzic.toml").write_text(
        'docs_dir = "docs"\nfail_under = 0\n\n'
        '[build_context]\nengine = "standalone"\n\n'
        '[project_metadata]\nobsolete_names = ["OldBrandName"]\n',
        encoding="utf-8",
    )
    (project / "docs" / "index.md").write_text(
        "# Page\n\nThis page mentions OldBrandName in prose, and carries enough words "
        "that the short-content rule stays quiet while the warning is what is being "
        "measured here.\n",
        encoding="utf-8",
    )
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC_BIN), "check", "all", ".", "--format", "json"],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1", "COLUMNS": "200"},
    )
    rendered = proc.stdout + proc.stderr
    assert "deprecated" in rendered.lower(), (
        f"the legacy field produced no deprecation warning at all: {rendered[:300]!r}"
    )
    for section in ("[project_metadata]", "[governance]"):
        assert section in rendered, (
            f"the warning reached the user without {section}. Rich swallowed it as a "
            f"markup tag: escape the opening bracket. Rendered: {rendered[:400]!r}"
        )
