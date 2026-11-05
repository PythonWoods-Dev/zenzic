# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""MkDocs' ``not_in_nav`` marks a page as deliberately absent from the nav.

Upstream semantics, verified against MkDocs 1.6.1's own source and by running
``mkdocs build`` (see ADR/rule-card text): ``not_in_nav`` is a gitignore-style
``PathSpec``.  A matching page is still built and served; it is only excluded
from the nav-omission diagnostic (``validation.nav.omitted_files``).  It is NOT
excluded from the site — that is ``exclude_docs``/``draft_docs``.

So a declared page must not be reported as ``Z402`` (ORPHAN_PAGE), while an
undeclared orphan must still be.  Both directions are asserted here: a test that
only checked the first would pass against an adapter that classified everything
as reachable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zenzic.core.adapters._mkdocs import MkDocsAdapter
from zenzic.models.config import BuildContext


def _adapter(tmp_path: Path, doc_config: dict[str, Any]) -> MkDocsAdapter:
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    return MkDocsAdapter(
        BuildContext(engine="mkdocs"),
        docs_root,
        doc_config,
        config_file_found=True,
        repo_root=tmp_path,
    )


def test_declared_page_is_not_an_orphan(tmp_path: Path) -> None:
    ad = _adapter(tmp_path, {"nav": [{"Home": "index.md"}], "not_in_nav": "declared.md\n"})
    assert ad.get_route_info(Path("declared.md")).status == "REACHABLE"


def test_undeclared_orphan_still_reported(tmp_path: Path) -> None:
    """Positive control: the instrument must still find an undeclared orphan.

    A test that only asserted the declared page goes quiet would pass against an
    adapter that called everything reachable.
    """
    ad = _adapter(tmp_path, {"nav": [{"Home": "index.md"}], "not_in_nav": "declared.md\n"})
    assert ad.get_route_info(Path("undeclared.md")).status == "ORPHAN_BUT_EXISTING"


def test_gitignore_semantics_directory_pattern(tmp_path: Path) -> None:
    """``records/*`` is a PathSpec, not an fnmatch of the whole path."""
    ad = _adapter(tmp_path, {"nav": [{"Home": "index.md"}], "not_in_nav": "records/*\n"})
    assert ad.get_route_info(Path("records/adr-001.md")).status == "REACHABLE"
    assert ad.get_route_info(Path("other/adr-001.md")).status == "ORPHAN_BUT_EXISTING"


def test_absent_key_changes_nothing(tmp_path: Path) -> None:
    ad = _adapter(tmp_path, {"nav": [{"Home": "index.md"}]})
    assert ad.get_route_info(Path("declared.md")).status == "ORPHAN_BUT_EXISTING"


def test_list_form_is_not_honoured(tmp_path: Path) -> None:
    """A YAML list is not a valid ``not_in_nav`` value, so it declares nothing.

    Measured against MkDocs 1.6.1 rather than assumed: ``config_options.PathSpec``
    raises *"Expected a multiline string, but a <class 'list'> was given"* and
    ``mkdocs build`` aborts with a configuration error.  Honouring the list form
    here would invent a semantic upstream rejects and attribute it to the key,
    so the page stays an orphan and the user keeps the finding that tells them
    their config is wrong.
    """
    ad = _adapter(tmp_path, {"nav": [{"Home": "index.md"}], "not_in_nav": ["declared.md"]})
    assert ad.get_route_info(Path("declared.md")).status == "ORPHAN_BUT_EXISTING"


def test_nav_membership_still_wins(tmp_path: Path) -> None:
    """A page both in nav and declared is REACHABLE for the ordinary reason."""
    ad = _adapter(tmp_path, {"nav": [{"Home": "index.md"}], "not_in_nav": "index.md\n"})
    assert ad.get_route_info(Path("index.md")).status == "REACHABLE"
