# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A declared engine that finds no configuration is refused, not replaced.

`get_adapter` used to fall back to StandaloneAdapter whenever the resolved
adapter reported `has_engine_config() is False`, and announce it on stderr.
That is a substitution, not a default: the run then reports what
StandaloneAdapter reports. Measured on a 421-file Starlight tree, `prebuilt`
without its manifest gives 2,443 findings where the manifest gives 235 -- and
the count is byte-identical to declaring "standalone" outright, which is the
whole problem. The notice was the only signal, and stderr reaches no CI
consumer.

Since 2026-09-21 the factory raises `Z111` instead, for every declared engine.
This file was `test_adapter_substitution_is_announced.py` until then, and two
of its four tests asserted the notice; the two that assert *silence* on a
correct configuration are unchanged, because that direction did not move.

The CLI and editor surfaces of the same rule are in
`test_a_declared_engine_needs_its_config.py`; this one is the factory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from zenzic.core.adapters._factory import clear_adapter_cache, get_adapter
from zenzic.core.exceptions import ZenzicConfigError
from zenzic.models.config import BuildContext


@pytest.fixture(autouse=True)
def _no_adapter_cache() -> None:
    clear_adapter_cache()


Engine = Literal["prebuilt", "vsm", "mkdocs", "zensical", "standalone", "auto"]


def _run(tmp_path: Path, engine: Engine) -> object:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.md").write_text("# T\n", encoding="utf-8")
    return get_adapter(BuildContext(engine=engine), docs, repo_root=tmp_path)


@pytest.mark.parametrize(
    ("engine", "artefact"),
    [
        ("prebuilt", ".zenzic-vsm.json"),
        ("vsm", ".zenzic-vsm.json"),
        ("mkdocs", "mkdocs.yml"),
    ],
)
def test_a_missing_artefact_is_refused(tmp_path: Path, engine: Engine, artefact: str) -> None:
    """Every declared engine, not the one that happened to be measured first."""
    with pytest.raises(ZenzicConfigError) as excinfo:
        _run(tmp_path, engine)

    assert excinfo.value.code == "Z111", (
        f"reported {excinfo.value.code!r}; `Z001` is the generic configuration error and "
        "`Z111` is the one whose reference page documents this"
    )
    message = str(excinfo.value)
    assert engine in message
    assert artefact in message
    assert "standalone" in message, "the message does not name the way out"


def test_a_present_manifest_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The other direction: a correct configuration must not be noisy."""
    (tmp_path / ".zenzic-vsm.json").write_text(
        json.dumps({"index.md": {"url": "/", "status": "REACHABLE"}}), encoding="utf-8"
    )
    adapter = _run(tmp_path, "prebuilt")
    captured = capsys.readouterr()
    assert type(adapter).__name__ == "PrebuiltVSMAdapter"
    assert "NOTICE" not in captured.err
    assert "NOTICE" not in captured.out


def test_declaring_standalone_is_not_a_substitution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Asking for standalone and getting it is not worth a notice."""
    _run(tmp_path, "standalone")
    assert "NOTICE" not in capsys.readouterr().err


def test_nothing_is_printed_on_the_way_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """stdout carries the machine-read payload and must stay clean.

    It asserted `NOTICE` on stderr and an empty stdout, because an earlier
    implementation printed the notice on stdout and made `--format json`
    unparseable. The notice is gone; the stdout half is the half that still
    matters, and the raise must not reintroduce a print of its own.
    """
    with pytest.raises(ZenzicConfigError):
        _run(tmp_path, "prebuilt")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "NOTICE" not in captured.err
