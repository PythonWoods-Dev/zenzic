# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`[build_context] base_url` has to do something, and the same thing to both codes.

The field was declared, written into every generated config, documented as
*"the adapter uses this value instead of attempting static extraction from the
build tool's config file"* -- and read by nothing. A user serving docs under
`/docs/` set it and got silence: no error, no warning, no effect.

Two findings land on the same link, and this is the trap the wiring has to avoid.
A page linking to `/docs/ref/page/` on a site based at `/docs/` reports **both**
`Z105` (absolute path) and `Z101` (broken link, because the VSM is keyed `/ref/page/`).
Measured before the fix. `absolute_path_allowlist = ["/docs/"]` already cleared
`Z105` alone -- so wiring `base_url` to the allowlist and stopping there would
have silenced the cosmetic half and left every such link reported broken, which
looks like a working feature and is not one.

So both consumers read **one** authority: `adapter.get_absolute_url_prefixes()`.
`Z105` allowlists what it returns and `Z101` re-bases against the same list; they
cannot disagree about where the site starts.

`prebuilt` is the exception and it is loud rather than silent. Its routes come
from `.zenzic-vsm.json`, which already carries whatever prefix the real build
produced, so a `base_url` on top would double-prefix or contradict the manifest.
Setting both raises `ZenzicConfigError`, and `zenzic init` does not offer the
setting at all when it writes a prebuilt config -- a template that offers what
the chosen engine rejects is the defect this repository closed in
`suppression_cap_scope` the same day.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.core.adapters import get_adapter
from zenzic.main import app
from zenzic.models.config import ZenzicConfig


runner = CliRunner()

_FILLER = " ".join(["word"] * 55)


def _corpus(tmp_path: Path, config_text: str) -> Path:
    docs = tmp_path / "docs" / "ref"
    docs.mkdir(parents=True)
    (tmp_path / "docs" / "index.md").write_text(
        f"# Home\n\nAbsolute: [Ref](/docs/ref/page/). {_FILLER}\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "ref" / "page.md").write_text(
        f"# Page\n\n[Home](../index.md). {_FILLER}\n", encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text(config_text, encoding="utf-8")
    return tmp_path


def _engine_config_file(tmp_path: Path, engine: str) -> None:
    """Each adapter refuses to build without its own config file."""
    if engine == "mkdocs":
        (tmp_path / "mkdocs.yml").write_text("site_name: T\n", encoding="utf-8")
    elif engine == "zensical":
        (tmp_path / "zensical.toml").write_text('[site]\nname = "T"\n', encoding="utf-8")


def _codes(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    import json

    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["check", "all", "--format", "sarif"])
    assert result.exit_code in (0, 1, 2, 3), f"crashed (exit {result.exit_code})"
    return {r["ruleId"] for r in json.loads(result.stdout)["runs"][0]["results"]}


def test_without_base_url_the_prefixed_link_is_reported_both_ways(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control: unset, the link is an absolute path *and* a broken one."""
    repo = _corpus(tmp_path, 'docs_dir = "docs"\n')
    codes = _codes(repo, monkeypatch)
    assert {"Z101", "Z105"} <= codes, (
        f"the fixture no longer produces the findings the fix removes: {sorted(codes)}"
    )


def test_base_url_clears_both_findings_not_just_the_cosmetic_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set, the link is neither absolute-by-mistake nor broken. Both, or neither."""
    repo = _corpus(tmp_path, 'docs_dir = "docs"\n\n[build_context]\nbase_url = "/docs/"\n')
    codes = _codes(repo, monkeypatch)
    assert "Z105" not in codes, "Z105 still fires on a link inside the declared base"
    assert "Z101" not in codes, (
        "Z101 still fires: the prefix was allowlisted but never re-based, which is "
        "the half-fix this module exists to prevent"
    )


@pytest.mark.parametrize("engine", ["mkdocs", "zensical", "standalone"])
def test_the_adapter_reports_the_declared_base_as_project_owned(
    tmp_path: Path, engine: str
) -> None:
    """One authority: both codes read `get_absolute_url_prefixes`."""
    (tmp_path / "docs").mkdir()
    _engine_config_file(tmp_path, engine)
    config = ZenzicConfig.model_validate(
        {"docs_dir": "docs", "build_context": {"engine": engine, "base_url": "/docs/"}}
    )
    adapter = get_adapter(config.build_context, tmp_path / "docs", tmp_path)
    assert "/docs/" in adapter.get_absolute_url_prefixes(), (
        f"{engine} does not report its declared base as project-owned"
    )


@pytest.mark.parametrize("engine", ["mkdocs", "zensical", "standalone"])
def test_no_base_url_declares_no_prefix(tmp_path: Path, engine: str) -> None:
    """Both directions: unset must not invent a prefix."""
    (tmp_path / "docs").mkdir()
    _engine_config_file(tmp_path, engine)
    config = ZenzicConfig.model_validate({"docs_dir": "docs", "build_context": {"engine": engine}})
    adapter = get_adapter(config.build_context, tmp_path / "docs", tmp_path)
    assert "/docs/" not in adapter.get_absolute_url_prefixes()


def test_prebuilt_refuses_base_url_instead_of_ignoring_it(tmp_path: Path) -> None:
    """The manifest already carries the prefix; a second one is a contradiction."""
    from zenzic.core.exceptions import ZenzicConfigError

    (tmp_path / "docs").mkdir()
    (tmp_path / ".zenzic-vsm.json").write_text(
        '{"index.md": {"url": "/docs/", "status": "REACHABLE"}}', encoding="utf-8"
    )
    config = ZenzicConfig.model_validate(
        {"docs_dir": "docs", "build_context": {"engine": "prebuilt", "base_url": "/docs/"}}
    )
    with pytest.raises(ZenzicConfigError, match="base_url"):
        get_adapter(config.build_context, tmp_path / "docs", tmp_path)
