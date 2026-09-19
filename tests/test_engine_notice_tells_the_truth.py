# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The engine-substitution notice must describe the run it is printed in.

Measured on this repository on 2026-09-19: `zenzic check all` printed

    NOTICE: engine 'mkdocs' found no mkdocs.yml, so this run used 'standalone'
    instead. Findings below are StandaloneAdapter's, not 'mkdocs''s.

to stderr while the telemetry line on stdout read `mkdocs • 338 files`, the
adapter resolved from the same configuration was `MkDocsAdapter`, its
`has_engine_config()` was True and its nav held 237 entries — and `mkdocs.yml`
was in the repository root the whole time. `just verify` printed it at two
stages. The product was wrong about its own configuration.

Two independent defects produced it, and each gets its own test here:

1. `check all` does not pass `repo_root` into `scan_docs_references()`, so the
   security-only pass falls back to `_root = docs_root` and builds its adapter
   with the documentation directory as the repository root. `mkdocs.yml` is not
   inside `docs/`, so that adapter reports no configuration.

2. The notice's guard reads `context.engine not in ("standalone", "auto")`, but
   `get_adapter()` overwrites `context.engine` with the discovered engine ~80
   lines earlier. The `"auto"` arm was therefore unreachable: a project that
   declared nothing was told its *declared* engine had been replaced.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from zenzic.core.adapters._factory import clear_adapter_cache


@pytest.fixture(autouse=True)
def _clean_adapter_cache() -> object:
    clear_adapter_cache()
    yield
    clear_adapter_cache()


def _project(tmp_path: Path, *, engine: str | None, mkdocs_yml: bool) -> Path:
    """A project with an **excluded** directory, which is what it takes.

    The adapter that reports no configuration is built by the security-only
    pass, and that pass runs only over files user scoping removed from the
    corpus. A project with nothing excluded never reaches the call site and
    never sees the notice -- which is why a minimal fixture reproduced nothing
    and this repository reproduced it on every run.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    body = " ".join(["word"] * 60)
    (docs / "index.md").write_text(f"# Home\n\n{body}\n", encoding="utf-8")
    (docs / "private").mkdir()
    (docs / "private" / "notes.md").write_text(f"# Notes\n\n{body}\n", encoding="utf-8")
    if mkdocs_yml:
        (tmp_path / "mkdocs.yml").write_text(
            "site_name: Probe\nnav:\n  - Home: index.md\n", encoding="utf-8"
        )
    cfg = 'docs_dir = "docs"\nexcluded_dirs = ["private"]\n'
    if engine is not None:
        cfg += f'\n[build_context]\nengine = "{engine}"\n'
    (tmp_path / ".zenzic.toml").write_text(cfg, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _run(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all", "--no-header"],
        cwd=project,
        capture_output=True,
        text=True,
        env={"NO_COLOR": "1", "PATH": "/usr/bin:/bin", "HOME": str(project)},
    )


def test_a_declared_engine_whose_config_is_present_is_not_announced_as_replaced(
    tmp_path: Path,
) -> None:
    """`mkdocs.yml` is in the root and the engine is declared. Nothing was replaced."""
    out = _run(_project(tmp_path, engine="mkdocs", mkdocs_yml=True))

    assert "found no mkdocs.yml" not in out.stderr, (
        f"the run announced a substitution that did not happen:\n{out.stderr}"
    )


def test_an_undeclared_engine_is_never_announced_as_replaced(tmp_path: Path) -> None:
    """`auto` is not a declaration, so there is nothing to have been replaced.

    The guard excludes `"auto"` by name, and `get_adapter()` overwrites the
    field with the discovered engine before the guard reads it — so the
    exclusion never applied to any real run.
    """
    out = _run(_project(tmp_path, engine=None, mkdocs_yml=True))

    assert "found no" not in out.stderr, (
        f"a project that declared no engine was told its engine was replaced:\n{out.stderr}"
    )


def test_a_declared_engine_with_no_configuration_is_still_announced(tmp_path: Path) -> None:
    """The control: the notice must still fire where it is true.

    Without this, the two tests above pass by deleting the notice entirely.
    """
    out = _run(_project(tmp_path, engine="mkdocs", mkdocs_yml=False))

    assert "found no mkdocs.yml" in out.stderr, (
        f"a declared engine with no configuration was replaced in silence:\n{out.stderr}"
    )


def test_the_declaration_survives_the_auto_resolution(tmp_path: Path) -> None:
    """The second defect, isolated from the first.

    `get_adapter()` overwrites `context.engine` when it is `"auto"`, and one
    `BuildContext` is shared across every call in a run. So a local captured at
    the top of the function reads the *discovered* engine from the second call
    onward, and the guard's `"auto"` arm stays unreachable. The declaration has
    to be recorded on the context, once.

    This drives the second call the way a caller with no `repo_root` does: with
    the documentation directory in its place. That caller still exists
    (`scan_docs_references(repo_root=None)`), so the guard has to hold without
    relying on the first defect being fixed.
    """
    from zenzic.core.adapters import get_adapter
    from zenzic.models.config import BuildContext

    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: Probe\n", encoding="utf-8")

    context = BuildContext()  # engine defaults to "auto" -- nothing was declared
    assert context.engine == "auto"

    first = get_adapter(context, docs, tmp_path)
    assert type(first).__name__ == "MkDocsAdapter"
    assert str(context.engine) == "mkdocs"  # the mutation the notice used to read

    import io

    printed = io.StringIO()

    class _Capture:
        def __init__(self, *a: object, **k: object) -> None: ...
        def print(self, *args: object, **kwargs: object) -> None:
            printed.write(" ".join(str(a) for a in args))

    # The notice is written through a `rich` Console constructed at the emission
    # site, so the console class is what has to be intercepted.
    import rich.console

    rich_original = rich.console.Console
    setattr(rich.console, "Console", _Capture)  # noqa: B010 - restored in `finally`
    try:
        get_adapter(context, docs, docs)  # the repo_root-less caller's shape
    finally:
        setattr(rich.console, "Console", rich_original)  # noqa: B010

    assert "found no" not in printed.getvalue(), (
        "a project that declared nothing was told its declared engine was replaced: "
        f"{printed.getvalue()!r}"
    )
