# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The generator knows its anchors; the engine predicts them, and predicts wrong.

`Z102` compares a link's fragment against anchors derived from the source with
`slug_heading`, which replicates Python-Markdown. A site rendered with anything
else — `github-slugger` for Astro and Starlight — produces different anchors, and
every divergence is a `Z102` on a link that works in the browser. Measured on
`withastro/docs` at `16fe0736`, the pinned corpus: 27 of them.

The engine cannot fix this by predicting better, because it cannot know which
renderer to predict: `get_enabled_extensions` is overridden by the `mkdocs`
adapter alone, and `prebuilt` is a statement about *our* ignorance of the
generator, not about the generator.

So the manifest carries them. `.zenzic-vsm.json` already states the URL each
source publishes at; an `anchors` array states the fragments that URL answers to.
Declared anchors replace the predicted set rather than extending it -- a generator
that declares is authoritative, and merging would let a wrong prediction keep
passing links the site does not serve.

**Why this is not `slug`.** That field is read into route metadata and dropped:
nothing downstream consults it (see `docs/reference/route-manifest.md`). `anchors`
is the opposite -- `Route.anchors` is what `Z102` tests against, at
`incremental.py:1745` and through the scanner's cache. The field has a consumer
before it has a producer, which is the order that keeps a contract honest.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _project(tmp_path: Path, manifest: dict[str, object]) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    # An anchor no slug predictor derives from the heading text: the generator
    # renamed it, which is exactly the case the manifest exists to state.
    (docs / "target.md").write_text("# Getting Started\n\nBody.\n", encoding="utf-8")
    (docs / "index.md").write_text(
        "# Home\n\nSee [the guide](target.md#start-here).\n", encoding="utf-8"
    )
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )
    (tmp_path / ".zenzic-vsm.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def _codes(root: Path) -> list[str]:
    """The codes a real run emits, read from the published JSON.

    The CLI rather than `scan_docs_references` directly: the anchor comparison
    happens in the cross-check pass over the resolved link graph, which a bare
    scanner call does not reach -- a hand-built harness returned zero findings
    for a link that the product reports. A test that hand-builds the layer
    beneath the one it names ends up asserting what it supplied itself.
    """
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)  # noqa: S607
    exe = Path(sys.executable).parent / "zenzic"
    proc = subprocess.run(
        [str(exe), "check", "all", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:  # pragma: no cover - diagnostic path
        raise AssertionError(
            f"no JSON payload\nstdout={proc.stdout}\nstderr={proc.stderr}"
        ) from None
    return [f["code"] for f in payload.get("findings", [])]


def test_a_declared_anchor_is_believed(tmp_path: Path) -> None:
    """The fragment is not derivable from the heading, and the manifest says it exists."""
    root = _project(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "target.md": {
                "url": "/target/",
                "status": "REACHABLE",
                "anchors": ["start-here"],
            },
        },
    )
    assert "Z102" not in _codes(root)


def test_an_undeclared_anchor_still_fails(tmp_path: Path) -> None:
    """Declaring anchors replaces the prediction: it does not mean 'accept anything'.

    The manifest declares a different fragment, so the link's `#start-here` is
    absent from the authoritative set and must still be reported. Without this
    direction the field would be a suppression mechanism wearing a schema's name.
    """
    root = _project(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "target.md": {
                "url": "/target/",
                "status": "REACHABLE",
                "anchors": ["somewhere-else"],
            },
        },
    )
    assert "Z102" in _codes(root)


def test_without_the_field_the_engine_still_predicts(tmp_path: Path) -> None:
    """Absent `anchors` is the current behaviour, unchanged: back-compatible."""
    root = _project(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "target.md": {"url": "/target/", "status": "REACHABLE"},
        },
    )
    assert "Z102" in _codes(root)


def test_the_editor_answers_the_same_as_the_cli(tmp_path: Path) -> None:
    """Mirror Law: a declared anchor is not a clean terminal and a squiggle.

    The incremental engine builds its own anchor cache, file by file, on a path
    the scanner never walks. Wiring only the scanner would have left the editor
    predicting while the terminal was clean -- a surface deciding something the
    layer tested beneath it never sees.
    """
    from zenzic.core.adapters import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.models.config import ZenzicConfig

    root = _project(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "target.md": {
                "url": "/target/",
                "status": "REACHABLE",
                "anchors": ["start-here"],
            },
        },
    )
    target = root / "docs" / "target.md"
    config, _ = ZenzicConfig.load(root)
    # The adapter comes from the configuration rather than being hand-picked:
    # the test asserts what the engine does with the project's real engine, and
    # choosing the adapter here would answer part of the question being asked.
    adapter = get_adapter(config.build_context, root / "docs", root)
    engine = IncrementalAnalysisEngine(config, None, adapter, root / "docs", root)
    engine.update_file_cache(target, target.read_text(encoding="utf-8"))

    assert engine.anchors_cache[target.resolve()] == {"start-here"}, (
        "the editor's cache must hold what the manifest declares, not what the "
        "heading text predicts"
    )


def _messages(root: Path) -> list[str]:
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)  # noqa: S607
    exe = Path(sys.executable).parent / "zenzic"
    proc = subprocess.run(
        [str(exe), "check", "all", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
    )
    return [f["message"] for f in json.loads(proc.stdout).get("findings", [])]


def test_a_predicted_anchor_says_it_is_predicting(tmp_path: Path) -> None:
    """An absent field must not produce the same silence as a correct one.

    Without this the user reads `anchor '#x' not found` and has no way to tell a
    real typo from the engine predicting the wrong renderer -- the two look
    identical, and one of them is the product's fault.
    """
    root = _project(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "target.md": {"url": "/target/", "status": "REACHABLE"},
        },
    )
    z102 = [m for m in _messages(root) if "#start-here" in m]
    assert z102, "the fixture must still produce the anchor finding"
    assert "anchors predicted from headings" in z102[0], z102[0]


def test_a_declared_page_carries_no_caveat(tmp_path: Path) -> None:
    """The note is about provenance, so it must be absent where anchors are declared.

    Both directions: a caveat that is always printed teaches nothing, and would
    be the same defect as printing none.
    """
    root = _project(
        tmp_path,
        {
            "index.md": {"url": "/", "status": "REACHABLE"},
            "target.md": {
                "url": "/target/",
                "status": "REACHABLE",
                "anchors": ["somewhere-else"],
            },
        },
    )
    z102 = [m for m in _messages(root) if "#start-here" in m]
    assert z102, "an undeclared fragment must still be reported"
    assert "anchors predicted" not in z102[0], z102[0]
