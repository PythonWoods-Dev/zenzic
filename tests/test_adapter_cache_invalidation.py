# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Cache-safety tests for ``get_adapter()``'s process-lifetime adapter cache.

``_adapter_cache`` is keyed on ``(engine, docs_root, repo_root)`` — none of which
change when the *contents* of an engine config file change. Before this guard,
every long-running consumer had to remember to call ``clear_adapter_cache()`` at
the right moment: the LSP did, ``zenzic-mcp`` did not, and served a stale adapter
after a real ``mkdocs.yml`` edit until that was found and fixed.

The cache now fingerprints each adapter's own ``watched_config_files`` (mtime and
size) and rebuilds when the fingerprint changes, so a third consumer cannot
inherit the same bug by omission.
"""

from __future__ import annotations

import os
from pathlib import Path

from zenzic.core.adapters._factory import clear_adapter_cache, get_adapter
from zenzic.models.config import BuildContext


def _make_repo(tmp_path: Path, *, use_directory_urls: bool) -> tuple[Path, Path]:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        f"site_name: Fixture\nuse_directory_urls: {str(use_directory_urls).lower()}\n",
        encoding="utf-8",
    )
    return tmp_path, docs


def _touch_newer(path: Path) -> None:
    """Force a distinctly newer mtime, independent of filesystem granularity."""
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns + 10_000_000_000, stat.st_mtime_ns + 10_000_000_000))


def test_editing_a_watched_config_file_invalidates_the_cached_adapter(tmp_path: Path) -> None:
    """A real edit to mkdocs.yml must be reflected on the next get_adapter()."""
    clear_adapter_cache()
    repo_root, docs_root = _make_repo(tmp_path, use_directory_urls=True)

    first = get_adapter(BuildContext(engine="mkdocs"), docs_root, repo_root)
    assert first.use_directory_urls is True

    (repo_root / "mkdocs.yml").write_text(
        "site_name: Fixture\nuse_directory_urls: false\n", encoding="utf-8"
    )
    _touch_newer(repo_root / "mkdocs.yml")

    second = get_adapter(BuildContext(engine="mkdocs"), docs_root, repo_root)
    assert second.use_directory_urls is False, (
        "get_adapter() served a stale adapter after its own watched config file "
        "changed on disk — the caller had to know to call clear_adapter_cache()"
    )


def test_unchanged_config_still_returns_the_cached_instance(tmp_path: Path) -> None:
    """The guard must not defeat the cache: no edit means the same object back.

    Rebuilding on every call would silently turn a hot cache into a no-op, which
    is a performance regression the cache exists to prevent.
    """
    clear_adapter_cache()
    repo_root, docs_root = _make_repo(tmp_path, use_directory_urls=True)

    first = get_adapter(BuildContext(engine="mkdocs"), docs_root, repo_root)
    second = get_adapter(BuildContext(engine="mkdocs"), docs_root, repo_root)
    assert first is second


def test_deleting_a_watched_config_file_invalidates(tmp_path: Path) -> None:
    """Absence is a distinct state from presence, not an unreadable-so-reuse case."""
    clear_adapter_cache()
    repo_root, docs_root = _make_repo(tmp_path, use_directory_urls=True)

    first = get_adapter(BuildContext(engine="mkdocs"), docs_root, repo_root)
    (repo_root / "mkdocs.yml").unlink()

    second = get_adapter(BuildContext(engine="mkdocs"), docs_root, repo_root)
    assert second is not first


def test_adapter_with_no_watched_files_is_still_cached(tmp_path: Path) -> None:
    """StandaloneAdapter declares no watched config files; an empty fingerprint
    must compare equal to itself rather than being treated as always-stale.
    """
    clear_adapter_cache()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")

    first = get_adapter(BuildContext(engine="standalone"), docs, tmp_path)
    second = get_adapter(BuildContext(engine="standalone"), docs, tmp_path)
    assert first is second
