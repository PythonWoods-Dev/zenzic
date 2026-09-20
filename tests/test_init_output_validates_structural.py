# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Everything `zenzic init` writes must validate against the schema it writes for.

A generated config is not documentation about the tool, it is input to the tool.
A commented-out line in it is an offer -- uncomment this to get that behaviour --
and an offer the schema rejects is a defect the user finds by following our own
instructions.

That is what `[governance] suppression_cap_scope` did. The template wrote
``# suppression_cap_scope = "all"  # Options: all, per-file`` while the field is
typed ``Literal["all"]``, so a user who uncommented it and took the second option
got ``literal_error: Input should be 'all'`` on the next run. Verified end to end
before the fix: `zenzic check all` refused to start. Nothing caught it, because
the only assertion anyone had made about `init` output was that the *default*
form loads -- and the default form has that line commented.

Three assertions, in increasing strictness:

1. The file `init` writes loads.
2. Every commented ``key = value`` line loads when uncommented, in its section.
3. Every value offered by a trailing ``# Options: a, b, c`` or ``# Supported: ...``
   comment loads for the key it is attached to. This is the one the defect above
   would have failed -- and the enumerating comment is a form this file has got
   wrong twice, the other being an engine list that omitted the engine it
   annotated, recorded in `templates.py`'s own header.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tomllib
from typer.testing import CliRunner

from zenzic.main import app
from zenzic.models.config import ZenzicConfig


runner = CliRunner()

_SECTION = re.compile(r"^\[([A-Za-z0-9_.]+)\]\s*$")
_SETTING = re.compile(r"^(?:#\s*)?([a-z_][a-z0-9_]*)\s*=\s*(.+?)\s*$")
_OPTIONS = re.compile(r"#\s*(?:Options|Supported):\s*(.+?)\s*$")


def _init_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Home\n\nBody text.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # `init` resolves its root from the working directory
    result = runner.invoke(app, ["init"])
    generated = tmp_path / ".zenzic.toml"
    assert generated.exists(), f"init wrote no config (exit {result.exit_code}):\n{result.output}"
    return generated.read_text(encoding="utf-8")


def _nest(section: str, key: str, value_toml: str) -> dict[str, object]:
    """Build the smallest document that places *key* where the template had it."""
    parsed = tomllib.loads(f"{key} = {value_toml}")
    payload: dict[str, object] = parsed
    for part in reversed([p for p in section.split(".") if p]):
        payload = {part: payload}
    return payload


def _offers(text: str) -> list[tuple[str, str, str, str]]:
    """Return (section, key, toml_value, why) for every setting the file offers.

    Both live and commented-out lines. The live ones matter as much: the engine
    line is written uncommented *with* its `# Supported:` list, and that list is
    where this file's other enumeration defect lived.
    """
    found: list[tuple[str, str, str, str]] = []
    section = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        matched_section = _SECTION.match(line)
        if matched_section:
            section = matched_section.group(1)
            continue
        setting = _SETTING.match(line)
        if not setting:
            continue
        commented = line.lstrip().startswith("#")
        key, rest = setting.group(1), setting.group(2)
        options = _OPTIONS.search(rest)
        value = rest[: options.start()].rstrip() if options else rest
        value = re.sub(r"\s+#.*$", "", value).strip()
        if not value:
            continue
        try:
            tomllib.loads(f"{key} = {value}")
        except tomllib.TOMLDecodeError:
            continue  # prose that happens to contain '=', not a setting
        found.append((section, key, value, "commented default" if commented else "written value"))
        if options:
            for alternative in options.group(1).split(","):
                alternative = alternative.strip()
                if not alternative:
                    continue
                found.append(
                    (section, key, f'"{alternative}"', "offered by an enumerating comment")
                )
    return found


def test_the_config_init_writes_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The floor: the default form is valid."""
    _init_output(tmp_path, monkeypatch)
    config, _ = ZenzicConfig.load(tmp_path)
    assert config is not None


def test_the_file_offers_settings_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a template that offered nothing would pass the next test free."""
    offers = _offers(_init_output(tmp_path, monkeypatch))
    assert len(offers) >= 20, (
        f"only {len(offers)} offered setting(s) parsed out of init's output -- the "
        "parser has stopped recognising the template's shape, so the assertion "
        "below is checking almost nothing."
    )
    assert any("offered by an" in why for *_rest, why in offers), (
        "no `# Options:`/`# Supported:` list was parsed, and that enumerating form is "
        "exactly what shipped a value the schema rejects -- twice: `suppression_cap_scope` "
        "offering `per-file`, and before it an engine list that omitted the engine it "
        "annotated (`templates.py`'s own header records the second)."
    )


def test_every_setting_init_offers_is_accepted_by_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uncommenting any line the template offers must not break the next run."""
    rejected: list[str] = []
    for section, key, value, why in _offers(_init_output(tmp_path, monkeypatch)):
        try:
            ZenzicConfig.model_validate(_nest(section, key, value))
        except Exception as exc:  # noqa: BLE001 -- the message is the report
            first = str(exc).splitlines()[-2].strip() if "\n" in str(exc) else str(exc)
            where = f"[{section}] " if section else ""
            rejected.append(f"{where}{key} = {value}  ({why}) -> {first[:90]}")
    assert not rejected, "`zenzic init` offers settings its own schema refuses:\n  " + "\n  ".join(
        rejected
    )


def test_init_accepts_every_engine_it_advertises() -> None:
    """`--engine` must accept what `--help` and the generated file both name.

    The gate held a literal — `{"mkdocs", "zensical", "standalone"}` — while this
    same command's help text and the `# Supported:` comment it writes were both
    derived from `list_adapter_engines()`. So `prebuilt` and `vsm` were advertised
    in two places and refused in the third, and a user who read the help and tried
    it got a flat rejection that reads like a broken tool rather than an
    unfinished feature. Both build: auto-detection already selects `prebuilt` on a
    repository carrying `.zenzic-vsm.json`.
    """
    import inspect

    from zenzic.cli import _standalone
    from zenzic.core.adapters import list_adapter_engines

    source = inspect.getsource(_standalone)
    assert "_INIT_VALID_ENGINES = set(list_adapter_engines())" in source, (
        "`--engine`'s accepted set must be derived from the adapter registry, not "
        "restated -- a literal here disagreed with the help text for an entire cycle."
    )
    assert {"prebuilt", "vsm"} <= set(list_adapter_engines()), (
        "the registry no longer offers the engines this regression was about; "
        "update the test rather than the assertion if that was deliberate."
    )
