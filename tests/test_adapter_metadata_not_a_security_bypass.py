# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Adapter-supplied metadata filenames must not gate the security tier.

``get_metadata_files()`` exists so an engine's own config file is not analysed
as documentation. ``ZensicalAdapter`` also folds in every string it finds under
``extra_css``, ``extra_javascript``, ``theme.logo`` and ``theme.favicon``, with
no extension filter — and ``LayeredExclusionManager`` matches that set by
**basename, anywhere in the tree**, as an L1a "immutable system guardrail".

``security_view()`` retained it. So ``extra_css = ["leak.md"]`` in a project's
own ``zensical.toml`` excluded every file named ``leak.md`` from the
credential scan — the same shape as the ``.gitignore`` bypass: a
project-editable value deciding what the never-suppressible tier may see.

The guardrail set is only legitimately immutable for the engine's own
internals. Anything the scanned project can write into it is user-controllable
by definition, so the whole set is stripped from the security view. Nothing is
lost: that view only ever walks ``DOC_SUFFIXES`` files, and a genuine engine
config (``mkdocs.yml``, ``zensical.toml``) is not one.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.adapters import get_adapter
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.models.config import ZenzicConfig


_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _zensical_project(tmp_path: Path, extra_css: str) -> tuple[Path, Path]:
    (tmp_path / "zensical.toml").write_text(
        f'[project]\nextra_css = ["{extra_css}"]\n', encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "zensical"\n', encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
    leak = docs / "leak.md"
    leak.write_text(f"# L\n\n{_PROSE}\n", encoding="utf-8")
    return docs, leak


def test_config_injected_filename_does_not_hide_a_file_from_the_security_view(
    tmp_path: Path,
) -> None:
    docs, leak = _zensical_project(tmp_path, "leak.md")
    config, _ = ZenzicConfig.load(tmp_path)
    adapter = get_adapter(config.build_context, docs, tmp_path)
    metadata = adapter.get_metadata_files()

    # The injection itself is real and is not what this test asserts away.
    assert "leak.md" in metadata, "fixture no longer reproduces the injection"

    manager = LayeredExclusionManager(
        config, repo_root=tmp_path, docs_root=docs, adapter_metadata_files=metadata
    )
    # The quality view may honour it -- that is the feature working as intended.
    assert manager.should_exclude_file(leak, docs) is True
    # The security view must not.
    assert manager.security_view().should_exclude_file(leak, docs) is False, (
        "a filename written into the project's own engine config excluded a file "
        "from the credential scan — the never-suppressible tier must not be "
        "reachable from a value the scanned project controls"
    )
