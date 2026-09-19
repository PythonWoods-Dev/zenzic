# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every rule card's failing example produces the code the card documents.

`test_rule_card_example_validity.py` reads card fences for syntax — a TOML key
that exists, a CLI command that parses. It is blind to the failure that matters
more: a card whose example stopped producing its own finding still parses. A
reader copies the example, runs Zenzic, sees nothing, and concludes the rule
does not work.

So this runs each card's failing example and requires the card's code in the
output — the mechanism `test_gallery_code_coverage.py` already applies to the
gallery fixtures.

HOW AN EXAMPLE IS RECOGNISED. Only labelled examples are run:

* ``Failing Pattern (Triggers Zxxx)``, ``Bad (Triggers Zxxx)`` and
  ``Before (non-compliant ...)`` — the next fence must emit the code;
* ``Failing Pattern (emits `Zxxx` ...)`` — the next fence must emit that code;
* ``<!-- Before ... -->`` then ``<!-- After ... -->`` inside one fence — the part
  between the two comments must emit the code.

THE PROJECT AN EXAMPLE RUNS IN. The card's gallery fixture already produces the
code, so its configuration (``.zenzic.toml``, any engine file, any link cache) is
copied and the example replaces the fixture's content. A code that runs only
behind a flag gets that flag from the registry's ``activation_key`` — exactly
what a reader following the card would set.

WHAT IT CANNOT REACH, stated rather than discovered later:

1. **It cannot judge a demonstration.** An example that emits its code for an
   incidental reason passes.
2. **It does not run the passing half.** A passing example is often passing only
   inside the site it describes — ``../how-to/install.md`` exists in this
   documentation and not in a one-page project — so "emits nothing" would test
   the harness rather than the card.
3. **An unlabelled example is invisible to it.** A card showing a failing
   example without one of the labels above is not checked.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # PEP 680 backport

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = REPO_ROOT / "docs" / "rules"
EXAMPLES = REPO_ROOT / "examples"
ZENZIC = Path(sys.executable).parent / ("zenzic.exe" if os.name == "nt" else "zenzic")

_FENCE = re.compile(r"^(?P<indent>\s*)(?P<delim>`{3,}|~{3,})(?P<info>.*)$")
_TRIGGERS = re.compile(r"(?:Failing Pattern|Bad) \((?:Triggers|emits) `?(?P<code>Z\d{3})`?")
_BEFORE_LABEL = re.compile(r"\*\*Before \(non-compliant")
_TITLE = re.compile(r'title="(?P<path>[^"]+)"')
_FILE_COMMENT = re.compile(r"^<!--\s*File:\s*(?P<path>\S+)\s*-->")
_INLINE_BEFORE = re.compile(r"^<!--\s*Before\b")
_INLINE_AFTER = re.compile(r"^<!--\s*After\b")

#: Cards whose labelled failing example cannot be run by this harness, each with
#: the reason. Asserted in both directions below: an entry must name a card that
#: really has a failing example, so the list cannot outlive what it excuses.
CANNOT_BE_RUN: dict[str, str] = {
    "Z102": (
        "a cross-page anchor: the fragment is missing from a target page the example names "
        "and does not show, so one page on its own reports the missing page (Z101) instead"
    ),
    "Z103": "needs a site navigation and an existing page absent from it; one page has neither",
    "Z106": "a cycle needs two pages, and the example shows both inside one block",
    "Z109": (
        "an unreachable external host is observed only under --strict with a real network "
        "request, which a test run must not depend on"
    ),
    "Z405": "describes a file on disk that nothing links to; there is no page content to run",
    # Added 2026-09-16 (V031_CARDS_DOCS_AUDIT) when these four cards gained an example
    # derived from their fixture. Each is a graph-shaped code: the harness writes one
    # page, and one page has no graph. What each emits alone was measured, not assumed.
    "Z402": (
        "an orphan needs a site to be orphaned from; the fixture is three pages and the "
        "example page alone reports Z101 instead"
    ),
    "Z410": (
        "an unreachable node needs a graph to be unreachable in; the fixture is two pages "
        "and the example page alone emits nothing"
    ),
    "Z411": (
        "a dead end needs somewhere to lead from; the fixture is four pages and the example "
        "page alone reports Z101 and Z620 instead"
    ),
    "Z412": (
        "traceability needs its target namespace present; the fixture is three pages and the "
        "example page alone reports Z202 instead"
    ),
    # Measured 2026-09-16 (V031_CARDS_DOCS_AUDIT), both ways. Unmasked, the example
    # emits Z201 and the Secret Guard pre-commit hook refuses the commit -- correctly:
    # Z201 is non-suppressible, and the hook's exclude list is a deliberate two-path
    # allowance for the fixture that must carry a real string to BE a fixture. Masked to
    # the convention seven other public pages use (AKIA************MPLE), the page is
    # guard-clean and emits nothing. The two requirements are mutually exclusive.
    "Z201": (
        "a card that demonstrates a credential must contain one, and a public page "
        "containing one is what the product exists to block; masked to the house "
        "convention it is guard-clean and emits nothing -- a masked credential is not "
        "a credential, the same shape as Z403's escaped image"
    ),
}


@dataclass(frozen=True)
class CardExample:
    card: str
    code: str
    body: str
    path: str


def _examples_in(card: Path) -> list[CardExample]:
    lines = card.read_text(encoding="utf-8").splitlines()
    found: list[CardExample] = []
    pending: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        label = _TRIGGERS.search(line)
        if label:
            pending = label.group("code")
        elif _BEFORE_LABEL.search(line):
            pending = card.stem
        opened = _FENCE.match(line)
        if not opened:
            i += 1
            continue
        indent = len(opened.group("indent"))
        delim = opened.group("delim")
        body: list[str] = []
        j = i + 1
        while j < len(lines):
            closing = _FENCE.match(lines[j])
            if (
                closing
                and closing.group("delim")[0] == delim[0]
                and len(closing.group("delim")) >= len(delim)
                and not closing.group("info").strip()
            ):
                break
            body.append(lines[j][indent:] if lines[j][:indent].isspace() else lines[j].lstrip())
            j += 1
        title = _TITLE.search(opened.group("info"))
        path = title.group("path") if title else ""
        if body and _FILE_COMMENT.match(body[0]):
            path = _FILE_COMMENT.match(body[0]).group("path")  # type: ignore[union-attr]
        if pending:
            found.append(CardExample(card.stem, pending, "\n".join(body) + "\n", path))
            pending = None
        elif any(_INLINE_BEFORE.match(b) for b in body) and any(
            _INLINE_AFTER.match(b) for b in body
        ):
            start = next(k for k, b in enumerate(body) if _INLINE_BEFORE.match(b))
            end = next(k for k, b in enumerate(body) if _INLINE_AFTER.match(b))
            segment = "\n".join(body[start + 1 : end]).strip() + "\n"
            found.append(CardExample(card.stem, card.stem, segment, path))
        i = j + 1
    return found


def _all_examples() -> list[CardExample]:
    out: list[CardExample] = []
    for card in sorted(RULES_DIR.glob("Z*.md")):
        out.extend(_examples_in(card))
    return out


def _fixture_for(code: str) -> Path | None:
    for d in sorted(EXAMPLES.iterdir()):
        if d.is_dir() and d.name.split("-")[0].upper() == code and (d / ".zenzic.toml").exists():
            return d
    return None


_CONFIG_FILES = (".zenzic.toml", ".zenzic.local.toml")


def _card_configuration(card: str) -> dict[str, dict[str, Any]]:
    """The TOML a reader following the card's own Configuration section would write.

    Only fences for Zenzic's own files are read — ``pyproject.toml`` restates the same
    keys under another table, and engine files are the fixture's business.
    """
    text = (RULES_DIR / f"{card}.md").read_text(encoding="utf-8")
    section = (
        text.split("\n## Configuration", 1)[1].split("\n## ", 1)[0]
        if "\n## Configuration" in text
        else ""
    )
    found: dict[str, dict[str, Any]] = {}
    for block in re.finditer(r"(?ms)^```toml(?P<info>[^\n]*)\n(?P<body>.*?)^```", section):
        title = _TITLE.search(block.group("info"))
        name = title.group("path") if title else ".zenzic.toml"
        if name in _CONFIG_FILES and name not in found:
            found[name] = tomllib.loads(block.group("body"))
    return found


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _toml_key(key: str) -> str:
    return key if re.match(r"^[A-Za-z0-9_-]+$", key) else json.dumps(key)


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"no TOML form for {value!r}")


def _dump_toml(data: dict[str, Any], prefix: tuple[str, ...] = ()) -> str:
    scalars = [
        f"{_toml_key(k)} = {_toml_value(v)}" for k, v in data.items() if not isinstance(v, dict)
    ]
    out = "\n".join(scalars) + ("\n" if scalars else "")
    for key, value in data.items():
        if isinstance(value, dict):
            path = (*prefix, key)
            out += "\n[" + ".".join(_toml_key(p) for p in path) + "]\n" + _dump_toml(value, path)
    return out


def _build_project(example: CardExample, root: Path) -> None:
    fixture = _fixture_for(example.card)
    configs: dict[str, dict[str, Any]] = {".zenzic.toml": {"docs_dir": "docs"}}
    if fixture is not None:
        for item in fixture.iterdir():
            if item.name in {"docs", "README.md", *_CONFIG_FILES}:
                continue
            target = root / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        for name in _CONFIG_FILES:
            if (fixture / name).exists():
                configs[name] = tomllib.loads((fixture / name).read_text(encoding="utf-8"))
    for name, overlay in _card_configuration(example.card).items():
        configs[name] = _merge(configs.get(name, {}), overlay)
    body = example.body
    if example.path in _CONFIG_FILES:
        # The failing example IS configuration — a stale allowlist entry, say.
        configs[example.path] = _merge(configs.get(example.path, {}), tomllib.loads(body))
        body = "# Page\n\nA page for the configuration above to apply to.\n"
    definition = CODE_DEFINITIONS[example.card]
    if definition.activation == "flag" and definition.activation_key:
        configs[".zenzic.toml"] = _merge(
            configs[".zenzic.toml"], {"policies": {definition.activation_key: True}}
        )
    for name, data in configs.items():
        (root / name).write_text(_dump_toml(data), encoding="utf-8")
    docs_dir = configs[".zenzic.toml"].get("docs_dir", "docs")
    rel = (
        example.path
        if example.path and example.path not in _CONFIG_FILES
        else f"{docs_dir}/index.md"
    )
    page = root / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(body, encoding="utf-8")


def _emitted(root: Path) -> set[str]:
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "all", ".", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )
    start = proc.stdout.find("{")
    assert start >= 0, f"no JSON at all: {proc.stdout[:300]!r} {proc.stderr[:200]!r}"
    payload = json.loads(proc.stdout[start:])
    return {f["code"] for f in payload.get("findings", [])}


EXAMPLES_FOUND = _all_examples()


def test_the_parser_finds_examples_it_must_find() -> None:
    """A parser that finds nothing would make every test below pass vacuously."""
    cards = {e.card for e in EXAMPLES_FOUND}
    for known in ("Z101", "Z503", "Z610", "Z521"):
        assert known in cards, f"no labelled failing example found on {known}.md"


def test_the_exemption_list_names_only_real_examples() -> None:
    cards = {e.card for e in EXAMPLES_FOUND}
    stale = sorted(set(CANNOT_BE_RUN) - cards)
    assert not stale, f"CANNOT_BE_RUN names cards with no labelled failing example: {stale}"


@pytest.mark.parametrize(
    "example",
    [e for e in EXAMPLES_FOUND if e.card not in CANNOT_BE_RUN],
    ids=lambda e: e.card,
)
def test_each_card_failing_example_emits_its_code(example: CardExample, tmp_path: Path) -> None:
    if not ZENZIC.exists():
        pytest.fail(f"no zenzic console script at {ZENZIC}")
    _build_project(example, tmp_path)
    emitted = _emitted(tmp_path)
    assert example.code in emitted, (
        f"docs/rules/{example.card}.md labels an example as producing {example.code}, "
        f"and run on its own it emits {sorted(emitted) or 'nothing'}. A reader who copies "
        f"it sees no finding and concludes the rule does not work."
    )
