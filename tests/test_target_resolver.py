# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from zenzic.cli._target_resolver import _apply_target, _resolve_target
from zenzic.models.config import ZenzicConfig


def test_resolve_target_strips_fragments_and_queries(tmp_path: Path) -> None:
    """_resolve_target must strip #fragments and ?queries before Path.exists() checks."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    # Create a dummy md file
    target_file = docs_dir / "page.md"
    target_file.touch()

    config = ZenzicConfig(docs_dir=Path("docs"))

    # Test with fragment
    raw_fragment = "docs/page.md#gh-light-mode-only"
    resolved_fragment = _resolve_target(repo_root, config, raw_fragment)
    assert resolved_fragment == target_file.resolve()

    # Test with query string
    raw_query = "docs/page.md?version=1.0"
    resolved_query = _resolve_target(repo_root, config, raw_query)
    assert resolved_query == target_file.resolve()

    # Test with both
    raw_both = "docs/page.md?version=1.0#gh-light-mode-only"
    resolved_both = _resolve_target(repo_root, config, raw_both)
    assert resolved_both == target_file.resolve()


def test_apply_target_preserves_full_docs_root_for_file_outside_docs_dir(
    tmp_path: Path,
) -> None:
    """A single-file target outside docs_dir must NOT collapse docs_root to
    that file's own parent directory.

    Regression for: ``zenzic check all <file>`` on a root-level file (e.g.
    CHANGELOG.md, README.md — anything outside the configured docs_dir)
    rebuilt the VSM scoped to just that file's parent directory instead of
    the real site, producing false Z103/Z410-style "unreachable"/"orphan"
    findings for links to the rest of the site that are perfectly valid in
    the real, full-site scan. The LSP's ``_resolve_docs_root()``
    (``src/zenzic/lsp/server.py``) always resolves docs_root once from
    ``config.docs_dir`` for the whole workspace and never re-scopes it per
    requested file — ``_apply_target`` must do the same: preserve the
    configured docs_root and rely on the caller's existing post-hoc
    ``single_file`` filter (already used by ``check_all``) to narrow the
    *displayed* findings, rather than narrowing the VSM itself.
    """
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")

    # A root-level file OUTSIDE docs_dir — the case that was broken.
    changelog = repo_root / "CHANGELOG.md"
    changelog.write_text("# Changelog\n", encoding="utf-8")

    config = ZenzicConfig(docs_dir=Path("docs"))

    patched_config, single_file, docs_root, _hint = _apply_target(
        repo_root, config, "CHANGELOG.md"
    )

    assert single_file == changelog.resolve(), (
        "single_file must resolve to the requested target for the caller's "
        "post-hoc filter to work"
    )
    assert docs_root == (repo_root / "docs").resolve(), (
        f"docs_root must stay the configured full docs_dir ({(repo_root / 'docs').resolve()}), "
        f"not collapse to the target's own parent directory, got {docs_root}"
    )
    assert patched_config.docs_dir == config.docs_dir, (
        "config.docs_dir must be left untouched — the VSM must still be built "
        "from the full, real docs_dir, matching what the LSP does for the "
        "same 'check one file in the context of the whole site' case"
    )


def test_apply_target_still_scopes_file_inside_docs_dir(tmp_path: Path) -> None:
    """Regression guard: a file INSIDE docs_dir must keep working exactly as
    before — this fix must not touch the already-correct in-docs_dir case."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)
    page = docs_dir / "page.md"
    page.write_text("# Page\n", encoding="utf-8")

    config = ZenzicConfig(docs_dir=Path("docs"))

    patched_config, single_file, docs_root, _hint = _apply_target(
        repo_root, config, "docs/page.md"
    )

    assert single_file == page.resolve()
    assert docs_root == docs_dir.resolve()
    assert patched_config.docs_dir == config.docs_dir
