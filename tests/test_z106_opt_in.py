# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Z106 (CIRCULAR_LINK) is opt-in, because cycles are documentation's normal shape.

The rule flagged every node participating in any cycle in the page graph. In a
documentation set that is not a defect signal -- it is the ordinary topology. An
index links to its records and each record links back to the index; two articles
cross-reference each other's arguments; a reference section interlinks densely.
All three are good practice and all three are cycles.

Measured on this repository with the exemption removed: **704 findings across
238 of ~300 pages**, from 17 strongly connected components -- eleven of them
mutual pairs, and one spanning 44 interlinked developer-reference pages. Sampled
instances were the `adr-vault/index.md` <-> `records/adr-09x.md` pattern, which
every documentation set with an index has by construction.

The response had been `.zenzic.toml`'s `"docs/**" = ["Z106"]`, added in ef6d2b0
("resolve Z401 missing indexes and **Z106 noise**") with no explanatory comment
beside it, unlike every neighbouring policy. A per-directory exemption silencing
a rule for an entire corpus is the symptom; the rule's premise is the defect.

So the code is now gated like every other opinionated check (`Z518`, `Z519`,
`Z521`...): off unless a project declares it wants an acyclic hierarchy.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.models.config import ZenzicConfig


def _cyclic_corpus(tmp_path: Path) -> Path:
    """An index and a record that link to each other -- the universal pattern."""
    docs = tmp_path / "docs"
    docs.mkdir()
    body = " ".join(["word"] * 60)
    (docs / "index.md").write_text(f"# Index\n\n[Record](record.md). {body}\n", encoding="utf-8")
    (docs / "record.md").write_text(f"# Record\n\n[Index](index.md). {body}\n", encoding="utf-8")
    return docs


def test_the_flag_exists_and_defaults_to_off() -> None:
    config = ZenzicConfig()
    assert hasattr(config.policies, "enable_circular_link_check"), (
        "Z106 needs an explicit opt-in flag, like every other opinionated check"
    )
    assert config.policies.enable_circular_link_check is False


def test_reciprocal_links_are_not_reported_by_default(tmp_path: Path) -> None:
    """An index and its record linking to each other must be silent."""
    from zenzic.core.exclusion import LayeredExclusionManager
    from zenzic.core.scanner import scan_docs_references

    docs = _cyclic_corpus(tmp_path)
    (tmp_path / ".zenzic.toml").touch()
    config, _ = ZenzicConfig.load(tmp_path)
    mgr = LayeredExclusionManager(config, repo_root=tmp_path)
    reports, _ = scan_docs_references(docs, mgr, repo_root=tmp_path, config=config)
    codes = [f.rule_id for r in reports for f in r.rule_findings]
    assert "Z106" not in codes, f"Z106 fired without being enabled: {codes}"


def test_reciprocal_links_are_reported_when_enabled(tmp_path: Path) -> None:
    """The positive control: the capability still exists for projects that want it."""
    from zenzic.core.exclusion import LayeredExclusionManager
    from zenzic.core.scanner import scan_docs_references

    docs = _cyclic_corpus(tmp_path)
    (tmp_path / ".zenzic.toml").write_text(
        "[policies]\nenable_circular_link_check = true\n", encoding="utf-8"
    )
    config, _ = ZenzicConfig.load(tmp_path)
    mgr = LayeredExclusionManager(config, repo_root=tmp_path)
    reports, _ = scan_docs_references(docs, mgr, repo_root=tmp_path, config=config)
    codes = [f.rule_id for r in reports for f in r.rule_findings]
    assert "Z106" in codes, f"enabling the check produced no Z106: {codes}"
