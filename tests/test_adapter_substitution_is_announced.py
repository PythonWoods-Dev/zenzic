# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A declared engine that finds no configuration is replaced, and says so.

`get_adapter` falls back to StandaloneAdapter whenever the resolved adapter
reports `has_engine_config() is False`. That is a substitution, not a default:
the run then reports what StandaloneAdapter reports. Measured on a 421-file
Starlight tree, `prebuilt` without its manifest gives 2,443 findings where the
manifest gives 235 -- and the count is byte-identical to declaring "standalone"
outright, which is the whole problem.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from zenzic.core.adapters._factory import clear_adapter_cache, get_adapter
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


def test_a_missing_manifest_is_announced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    adapter = _run(tmp_path, "prebuilt")
    err = capsys.readouterr().err
    assert type(adapter).__name__ == "StandaloneAdapter"
    assert "prebuilt" in err
    assert ".zenzic-vsm.json" in err
    assert "standalone" in err


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


def test_the_notice_goes_to_stderr_so_json_stays_parseable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """stdout carries the machine-read payload and must stay clean.

    The first implementation printed on stdout and made `--format json`
    unparseable; this asserts the stream rather than the wording.
    """
    _run(tmp_path, "prebuilt")
    captured = capsys.readouterr()
    assert "NOTICE" in captured.err
    assert captured.out == ""
