# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A generator that publishes from two directories can be reached from configuration.

`docs_dir` names one directory. `BaseAdapter.get_extra_content_roots()` exists
for the rest, and only `MkDocsAdapter` implements it — `standalone` and
`prebuilt` return nothing. So until 2026-09-19 a Docusaurus site's `blog/`,
its second content plugin, was analysed by nothing and no configuration a user
could write would reach it.

Measured on a `create-docusaurus` classic scaffold before the key existed:
`zenzic check all` read **9 of the repository's 15 Markdown sources**, and 4 of
the 6 it missed were `blog/`.

`content_roots` closes it without the engine learning anything about
Docusaurus (ADR-075): the user declares the tree, the adapter still declares
whatever it derives, and `resolve_content_roots()` is the one place the two are
combined.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zenzic.core.adapters import resolve_content_roots
from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.models.config import ZenzicConfig


def _two_tree_project(tmp_path: Path, *, declare_blog: bool) -> Path:
    body = " ".join(["word"] * 60)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "intro.md").write_text(f"# Intro\n\n{body}\n", encoding="utf-8")
    blog = tmp_path / "blog"
    blog.mkdir()
    # A defect only a scan that reads this tree can see.
    (blog / "post.md").write_text(
        f"# Post\n\n{body}\n\nSee [the missing page](./nowhere.md).\n", encoding="utf-8"
    )
    cfg = 'docs_dir = "docs"\n'
    if declare_blog:
        cfg += 'content_roots = ["blog"]\n'
    (tmp_path / ".zenzic.toml").write_text(cfg, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _codes(project: Path) -> set[str]:
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all", "--format", "json"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )
    start = out.stdout.find("{")
    assert start >= 0, f"no JSON payload:\n{out.stdout}\n{out.stderr}"
    payload = json.loads(out.stdout[start:])
    return {f["code"] for f in payload.get("findings", [])}


def test_a_second_tree_is_unreachable_without_declaring_it(tmp_path: Path) -> None:
    """The control. Without the key the blog is not read, so its defect is silent."""
    assert "Z101" not in _codes(_two_tree_project(tmp_path, declare_blog=False))


def test_declaring_the_second_tree_reaches_it(tmp_path: Path) -> None:
    """And the link tier reaches it too, which is a second fix.

    Reaching the tree was not enough: a mounted source is read from one path
    and published at another, and the resolution context was built from the
    path on disk. Every link target then landed outside `docs_root`, matched no
    route, and was dropped without a finding -- so a file that reports `Z101`
    under `docs/` reported nothing at all when mounted, while its content-tier
    findings appeared normally. That held for locale roots too, the only
    mounted tree that existed before this key.
    """
    assert "Z101" in _codes(_two_tree_project(tmp_path, declare_blog=True))


def test_a_declared_root_is_resolved_against_the_repository_root(tmp_path: Path) -> None:
    config = ZenzicConfig(content_roots=[Path("blog")])
    (tmp_path / "blog").mkdir()

    roots = resolve_content_roots(StandaloneAdapter(), config, tmp_path)

    assert roots == [(tmp_path / "blog").resolve()]


def test_an_absolute_declared_root_is_taken_as_given(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    config = ZenzicConfig(content_roots=[elsewhere])

    assert resolve_content_roots(StandaloneAdapter(), config, tmp_path) == [elsewhere.resolve()]


def test_the_adapter_half_and_the_user_half_are_both_kept(tmp_path: Path) -> None:
    """Neither source replaces the other, and duplicates collapse."""

    class _Deriving(StandaloneAdapter):
        def get_extra_content_roots(self, repo_root: Path) -> list[Path]:
            return [repo_root / "derived", repo_root / "shared"]

    config = ZenzicConfig(content_roots=[Path("declared"), Path("shared")])

    roots = resolve_content_roots(_Deriving(), config, tmp_path)

    assert roots == [
        (tmp_path / "derived").resolve(),
        (tmp_path / "shared").resolve(),
        (tmp_path / "declared").resolve(),
    ]


@pytest.mark.parametrize("escape", ["../outside", "/etc"])
def test_a_root_outside_the_repository_is_reported_but_never_read(
    tmp_path: Path, escape: str
) -> None:
    """Declaring a root does not move the boundary.

    Roots are *reported* here; every read goes through `discovery.walk_files`,
    which resolves each file against the exclusion manager's repository root.
    The detector is the credential tier on purpose: it is non-suppressible, so
    "was this file read?" is answered by the exit code rather than by trusting
    a log line — the same arrangement `test_adapter_roots_cannot_escape_the_repo`
    pins for adapter-declared roots.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.md").write_text(
        "# Leak\n\n```\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n```\n",
        encoding="utf-8",
    )
    project = tmp_path / "repo"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\n" + " ".join(["word"] * 60) + "\n", encoding="utf-8")
    (project / ".zenzic.toml").write_text(
        f'docs_dir = "docs"\ncontent_roots = ["{escape}"]\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=project, check=True)  # noqa: S607

    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", "check", "all"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )

    assert out.returncode != 2, (
        f"a declared root outside the repository was read (exit 2 is the credential "
        f"tier):\n{out.stdout[-1500:]}"
    )
