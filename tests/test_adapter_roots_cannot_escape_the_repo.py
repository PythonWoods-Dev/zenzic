# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""No adapter can hand the engine a root outside the repository and have it read.

``_validate_docs_root`` (``cli/_shared.py``) documents itself as the guard against
``docs_dir = "../../etc"``, but it only ever sees the *config-derived* root —
``(repo_root / config.docs_dir)``. An engine config that points somewhere else
(``mkdocs.yml``'s own ``docs_dir``, a monorepo ``!include``, ``zensical.toml``, a
prebuilt VSM route) is resolved by the adapter, never passes through that
function, and would sail past it.

The real boundary is one layer down and is load-bearing: every read in the engine
goes through ``discovery.walk_files``, which resolves each file and skips anything
that is not under the exclusion manager's ``_repo_root``. Adapters report roots;
they never construct an exclusion manager, so they cannot move that boundary.

These tests pin that arrangement, because it is the thing actually keeping the
engine inside the repository. They use the credential scanner as the detector on
purpose: it is the non-suppressible tier, so "was this file read?" is answered by
exit 2 rather than by trusting a log line.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    """A repo, and a sibling directory outside it holding a live credential."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    (repo / "docs").mkdir(parents=True)
    outside.mkdir()
    (repo / "docs" / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
    (outside / "leak.md").write_text(
        f'# Outside\n\n{_PROSE}\n\n    aws_key = "{_SECRET}"\n', encoding="utf-8"
    )
    return repo, outside


def _run(repo: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.chdir(repo)
    return CliRunner().invoke(app, ["check", "all", "--quiet"], catch_exceptions=False).exit_code


def test_the_detector_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control. Without this, every assertion below passes vacuously."""
    repo, _ = _workspace(tmp_path)
    (repo / "mkdocs.yml").write_text("site_name: Control\n", encoding="utf-8")
    (repo / "docs" / "index.md").write_text(
        f'# Home\n\n{_PROSE}\n\n    aws_key = "{_SECRET}"\n', encoding="utf-8"
    )
    assert _run(repo, monkeypatch) == 2, "the credential scanner did not fire inside the repo"


class TestEveryShippedAdapter:
    def test_mkdocs_absolute_docs_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, outside = _workspace(tmp_path)
        (repo / "mkdocs.yml").write_text(f"site_name: A\ndocs_dir: {outside}\n", encoding="utf-8")
        assert _run(repo, monkeypatch) != 2

    def test_mkdocs_monorepo_include_pointing_outside(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The include walker was widened deliberately; it must not widen the boundary."""
        repo, outside = _workspace(tmp_path)
        (outside / "docs").mkdir()
        (outside / "leak.md").rename(outside / "docs" / "leak.md")
        (outside / "mkdocs.yml").write_text("site_name: Sub\n", encoding="utf-8")
        (repo / "mkdocs.yml").write_text(
            "site_name: B\nplugins:\n  - monorepo\n"
            f"nav:\n  - Sub: '!include {outside}/mkdocs.yml'\n",
            encoding="utf-8",
        )
        assert _run(repo, monkeypatch) != 2

    def test_zensical_docs_dir_outside(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, outside = _workspace(tmp_path)
        (repo / "zensical.toml").write_text(
            f'[project]\nname = "C"\ndocs_dir = "{outside}"\n', encoding="utf-8"
        )
        assert _run(repo, monkeypatch) != 2

    def test_standalone_relative_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, _ = _workspace(tmp_path)
        (repo / ".zenzic.toml").write_text('docs_dir = "../outside"\n', encoding="utf-8")
        assert _run(repo, monkeypatch) != 2

    def test_prebuilt_vsm_route_outside(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, outside = _workspace(tmp_path)
        (repo / "mkdocs.yml").write_text("site_name: E\n", encoding="utf-8")
        (repo / ".zenzic-vsm.json").write_text(
            json.dumps({"version": 1, "routes": {"/leak/": {"source": str(outside / "leak.md")}}}),
            encoding="utf-8",
        )
        assert _run(repo, monkeypatch) != 2


def test_discovery_is_the_only_module_that_walks_the_filesystem() -> None:
    """Tier-0: every filesystem walk goes through ``discovery``.

    The boundary check that keeps the engine inside the repository lives in
    ``discovery``. A walk added anywhere else does not merely miss an exclusion
    — it leaves the repository, silently, with nothing else failing. That is the
    class of defect ``doctor`` had: three ``rglob`` calls on configured
    subpaths, inheriting no boundary, so ``adr_vault_path = "../outside"`` read
    a vault outside the repo and reported clean.

    The allowlist is deliberately **empty**. An entry here would keep a hole
    open by declaration; ``doctor`` was migrated to ``iter_files_within``
    instead, which is what makes the invariant true rather than merely stated.

    Scope, stated so it is not mistaken for an oversight: this matches
    *recursive* traversal — ``os.walk``, ``rglob``, ``scandir`` — because those
    descend into a tree whose root came from configuration and can therefore
    arrive anywhere on the machine. A non-recursive ``iterdir()`` on an
    already-validated root yields only that directory's own children and cannot
    leave it, so it is a listing rather than a walk. ``_shared.py`` uses one to
    count root-level config files; routing it through a recursive helper would
    be both slower and wrong.
    """
    import re

    allowed: set[str] = set()

    src = Path(__file__).resolve().parent.parent / "src" / "zenzic"
    offenders = []
    for path in sorted(src.rglob("*.py")):
        rel = path.relative_to(src).as_posix()
        if path.name == "discovery.py" or rel in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\bos\.walk\(|\.rglob\(|\bos\.scandir\(", text):
            offenders.append(f"{rel}:{text[: match.start()].count(chr(10)) + 1}")
    assert not offenders, (
        "filesystem walks outside zenzic.core.discovery bypass the repository-root "
        f"boundary check: {offenders}. Use walk_files (corpus, needs an exclusion "
        "manager) or iter_files_within (configured subpath) instead."
    )


class TestDoctorPathsStayInsideTheRepository:
    """``doctor`` walks a configured subpath, so its boundary is the config validator.

    The validator already refuses an absolute path and anything reaching ``.claude/``
    or ``.human/``, and its own docstring says doctor "operates on public repository
    content only" — but it did not refuse ``..``, so ``adr_vault_path = "../outside"``
    loaded cleanly and doctor read a vault outside the repository.
    """

    @staticmethod
    def _load(tmp_path: Path, value: str):
        from zenzic.models.config import ZenzicConfig

        return ZenzicConfig(**{"doctor": {"adr_vault_path": value}})

    @pytest.mark.parametrize(
        "value", ["../outside", "../../etc", "docs/../../outside", "./../outside"]
    )
    def test_a_traversing_vault_path_is_refused(self, tmp_path: Path, value: str) -> None:
        with pytest.raises(Exception) as excinfo:
            self._load(tmp_path, value)
        assert "outside the repository" in str(excinfo.value) or "escape" in str(excinfo.value)

    @pytest.mark.parametrize(
        "value", ["docs/developers/explanation/adr-vault", "adr", "docs/adr/records"]
    )
    def test_an_ordinary_relative_path_still_loads(self, tmp_path: Path, value: str) -> None:
        assert self._load(tmp_path, value) is not None
