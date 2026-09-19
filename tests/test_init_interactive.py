# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`zenzic init --interactive`: the engine offered with its detection stated, the
opt-in codes asked one at a time from the registry, the data-gated codes never
asked, and the non-interactive path unchanged.

The derivation is the point: a flag-gated code added to the registry must appear
in the prompt without `init` being touched, and the test plants one to prove it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from zenzic.core.codes import CODE_DEFINITIONS
from zenzic.main import app


try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10, the floor: the PEP 680 backport
    import tomli as tomllib


FLAG_KEYS = sorted(
    key for d in CODE_DEFINITIONS.values() if d.activation == "flag" and (key := d.activation_key)
)
DATA_CODES = sorted(c for c, d in CODE_DEFINITIONS.items() if d.activation == "data")


def _init(tmp_path: Path, *args: str, answers: str = "") -> tuple[int, str, dict[str, Any]]:
    result = CliRunner().invoke(app, ["init", *args, str(tmp_path)], input=answers)
    toml = tmp_path / ".zenzic.toml"
    data = tomllib.loads(toml.read_text(encoding="utf-8")) if toml.is_file() else {}
    return result.exit_code, result.output, data


def test_non_interactive_output_is_unchanged_by_the_flag_when_every_answer_is_the_default(
    tmp_path: Path,
) -> None:
    """Defaults answered interactively must produce the file the plain command writes."""
    plain = tmp_path / "plain"
    inter = tmp_path / "inter"
    plain.mkdir()
    inter.mkdir()
    code, _out, _ = _init(plain)
    assert code == 0
    # engine (Enter = detected default) + one answer per flag-gated code (Enter = no)
    answers = "\n" + "\n" * len(FLAG_KEYS)
    code, out, _ = _init(inter, "--interactive", answers=answers)
    assert code == 0, out
    assert (plain / ".zenzic.toml").read_text() == (inter / ".zenzic.toml").read_text()


def test_every_flag_gated_code_is_asked_once_and_no_data_gated_code_is(tmp_path: Path) -> None:
    answers = "\n" + "\n" * len(FLAG_KEYS)
    code, out, _ = _init(tmp_path, "--interactive", answers=answers)
    assert code == 0, out
    for key in FLAG_KEYS:
        assert out.count(f"[{key}]") == 1, f"{key} must be asked exactly once"
    for c in DATA_CODES:
        assert f"Enable {c}" not in out, f"{c} is data-gated and must not be a question"
    assert f"{len(DATA_CODES)} data-gated" in out, "the exclusion is stated with its reason"


def test_yes_enables_exactly_the_chosen_codes(tmp_path: Path) -> None:
    # engine default, then yes to the first flag code only
    answers = "\n" + "y\n" + "\n" * (len(FLAG_KEYS) - 1)
    code, out, data = _init(tmp_path, "--interactive", answers=answers)
    assert code == 0, out
    policies = data["policies"]
    assert policies[FLAG_KEYS[0]] is True
    for key in FLAG_KEYS[1:]:
        assert policies[key] is False


def test_engine_is_offered_from_the_registry_with_the_detection_stated(tmp_path: Path) -> None:
    (tmp_path / "mkdocs.yml").write_text("site_name: probe\n", encoding="utf-8")
    answers = "\n" + "\n" * len(FLAG_KEYS)
    code, out, data = _init(tmp_path, "--interactive", answers=answers)
    assert code == 0, out
    assert "mkdocs.yml" in out and "mkdocs" in out, "the detection and its reason are stated"
    assert data["build_context"]["engine"] == "mkdocs"
    # choosing another engine at the prompt overrides the detection
    other = tmp_path / "other"
    other.mkdir()
    (other / "mkdocs.yml").write_text("site_name: probe\n", encoding="utf-8")
    answers = "standalone\n" + "\n" * len(FLAG_KEYS)
    code, out, data = _init(other, "--interactive", answers=answers)
    assert code == 0, out
    assert data["build_context"]["engine"] == "standalone"


def test_no_engine_file_states_that_nothing_was_detected(tmp_path: Path) -> None:
    """The wording changed on 2026-09-19 and the reason is the point.

    It read "no engine file found", which is true and incomplete: detection now
    also looks for a generator's own config, so the absence it reports is the
    absence of *anything* to detect from. `astro.config.ts` sitting unread in a
    root while the product said "auto-detected" is what made this matter.
    """
    answers = "\n" + "\n" * len(FLAG_KEYS)
    _code, out, data = _init(tmp_path, "--interactive", answers=answers)
    assert "nothing found to detect from" in out.lower()
    assert data["build_context"]["engine"] == "standalone"


def test_a_generator_config_in_the_root_is_detected_and_named(tmp_path: Path) -> None:
    """`astro.config.ts` is as strong a signal as `mkdocs.yml`, and was ignored."""
    (tmp_path / "astro.config.ts").write_text("export default {}\n", encoding="utf-8")
    (tmp_path / "src" / "content" / "docs").mkdir(parents=True)
    (tmp_path / "src" / "content" / "docs" / "i.mdx").write_text("# T\n", encoding="utf-8")
    answers = "\n" + "\n" * len(FLAG_KEYS)
    _code, out, data = _init(tmp_path, "--interactive", answers=answers)
    assert "astro.config.ts found" in out.lower()
    assert "astro" in out.lower()
    # The source directory comes from the generator, not from the default.
    assert data["docs_dir"] == "src/content/docs"


def test_a_generator_docs_dir_is_not_written_when_it_does_not_exist(tmp_path: Path) -> None:
    """The other direction: a generated config must not name a missing directory."""
    (tmp_path / "astro.config.ts").write_text("export default {}\n", encoding="utf-8")
    answers = "\n" + "\n" * len(FLAG_KEYS)
    _code, out, data = _init(tmp_path, "--interactive", answers=answers)
    assert "docs_dir" not in data


def test_a_flag_gated_code_added_to_the_registry_appears_without_touching_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The proof the batch asks for: the prompt derives, it does not enumerate."""
    sample = CODE_DEFINITIONS["Z106"]
    planted = sample._replace(activation="flag", activation_key="enable_planted_check")
    monkeypatch.setitem(CODE_DEFINITIONS, "Z998", planted)
    keys = sorted(
        key
        for d in CODE_DEFINITIONS.values()
        if d.activation == "flag" and (key := d.activation_key)
    )
    assert "enable_planted_check" in keys
    answers = "\n" + "\n" * len(keys)
    code, out, _ = _init(tmp_path, "--interactive", answers=answers)
    assert code == 0, out
    assert out.count("[enable_planted_check]") == 1
    assert re.search(r"Z998", out)


def test_the_plain_command_asks_nothing_about_codes(tmp_path: Path) -> None:
    code, out, _ = _init(tmp_path)
    assert code == 0
    for key in FLAG_KEYS:
        assert f"[{key}]" not in out


def test_pyproject_present_and_no_answer_available_writes_zenzic_toml(tmp_path: Path) -> None:
    """Measured before the fix: stdin at EOF with a pyproject.toml present
    printed `Aborted.` and wrote nothing, exit 1 -- in the unattended setting
    the plain command is documented to serve. The question's own default is
    the answer there."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "probe"\n', encoding="utf-8")
    code, out, data = _init(tmp_path, answers="")
    assert code == 0, out
    assert (tmp_path / ".zenzic.toml").is_file()
    assert "no answer available" in out
    assert "[tool.zenzic]" not in (tmp_path / "pyproject.toml").read_text()


def test_pyproject_variant_carries_the_chosen_flag_where_the_loader_reads_it(
    tmp_path: Path,
) -> None:
    """The pyproject section is a pointer, so the one decision it carries must
    land in the table the loader reads -- `[tool.zenzic.policies]`, not under
    `[tool.zenzic]`, where a key is ignored with a warning."""
    from zenzic.models.config import load_config_with_diagnostics

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "probe"\n', encoding="utf-8")
    answers = "\n" + "y\n" + "\n" * (len(FLAG_KEYS) - 1)
    code, out, _ = _init(tmp_path, "--interactive", "--pyproject", answers=answers)
    assert code == 0, out
    parsed = tomllib.loads((tmp_path / "pyproject.toml").read_text(encoding="utf-8"))
    assert parsed["tool"]["zenzic"]["policies"][FLAG_KEYS[0]] is True
    cfg, findings = load_config_with_diagnostics(tmp_path, tmp_path / "pyproject.toml")
    assert cfg is not None and not findings, findings
    assert getattr(cfg.policies, FLAG_KEYS[0]) is True
