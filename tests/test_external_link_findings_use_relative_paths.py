# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""An external-link finding must name the file the way every other finding does.

`LinkValidator` labelled each occurrence with ``str(file_path)`` -- the absolute
path on the machine that ran the check. Every other finding prints a
repository-relative path, so this one output form leaked the local directory
layout into CI logs, SARIF, and anything a user pasted into an issue, and made
findings non-comparable between two machines checking the same commit.

It also made the output unquotable: the documentation page describing it had to
substitute an ``<abs-path>`` placeholder, because no real path is portable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from zenzic.core.validator import LinkValidator


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# T\n", encoding="utf-8")
    return tmp_path


def _captured_entries(
    monkeypatch: pytest.MonkeyPatch, validator: LinkValidator
) -> list[tuple[str, str, int]]:
    """Run validate_async without touching the network, capturing the labels.

    The real call pings every URL. Asserting on a DNS failure would make this
    test depend on the resolver's behaviour and on being offline in a particular
    way, so the network boundary is replaced and the labels inspected directly --
    the labels are what this test is about.
    """
    seen: list[tuple[str, str, int]] = []

    async def fake_check(entries, config, repo_root, *, progress_callback=None):  # noqa: ANN001, ANN202
        seen.extend(entries)
        return [
            f"{label}:{lineno}: external link '{url}' timed out (>10 s)"
            for url, label, lineno in entries
        ]

    monkeypatch.setattr("zenzic.core.validator._check_external_links", fake_check)
    asyncio.run(validator.validate_async())
    return seen


def test_the_label_is_relative_to_the_repository_root(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zenzic.models.config import ZenzicConfig

    v = LinkValidator(ZenzicConfig(), repo)
    v.register("https://example.invalid/x", repo / "docs" / "index.md", 7)
    entries = _captured_entries(monkeypatch, v)

    assert len(entries) == 1, entries
    _url, label, lineno = entries[0]
    assert lineno == 7
    assert label == "docs/index.md", (
        f"the finding label is {label!r}. Every other finding prints a path "
        "relative to the repository root; an absolute path leaks the machine's "
        "directory layout and differs between two machines checking one commit."
    )
    assert not Path(label).is_absolute(), f"absolute path in user-facing output: {label!r}"
    assert str(repo) not in label, f"the temporary root leaked into the label: {label!r}"


def test_a_file_outside_the_repository_root_still_produces_a_label(
    repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relativising must not raise on a path the root does not contain.

    ``Path.relative_to`` raises ValueError rather than returning the input, so an
    unguarded call turns a cosmetic path problem into a crash on any corpus whose
    content roots sit outside the repository -- an MkDocs monorepo, for instance.
    """
    from zenzic.models.config import ZenzicConfig

    outside = tmp_path_factory.mktemp("elsewhere") / "stray.md"
    outside.write_text("# T\n", encoding="utf-8")

    v = LinkValidator(ZenzicConfig(), repo)
    v.register("https://example.invalid/y", outside, 3)
    entries = _captured_entries(monkeypatch, v)

    assert len(entries) == 1, entries
    _url, label, _lineno = entries[0]
    assert label, "a file outside the root produced an empty label"
    assert "stray.md" in label, f"the file is unidentifiable from the label: {label!r}"


def test_posix_separators_so_the_label_is_comparable_across_platforms(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Windows run must produce the same label as a Linux run.

    Backslashes would make the same finding on the same commit compare unequal
    between two machines, which is half of what this fix is for.
    """
    from zenzic.models.config import ZenzicConfig

    nested = repo / "docs" / "guide" / "deep"
    nested.mkdir(parents=True)
    (nested / "page.md").write_text("# T\n", encoding="utf-8")

    v = LinkValidator(ZenzicConfig(), repo)
    v.register("https://example.invalid/z", nested / "page.md", 1)
    entries = _captured_entries(monkeypatch, v)

    _url, label, _lineno = entries[0]
    assert "\\" not in label, f"platform-specific separator in the label: {label!r}"
    assert label == "docs/guide/deep/page.md", label


class TestTheSameConstructionElsewhere:
    """The sweep, not just the instance that was reported.

    Sweeping every fixture against every output format found two more places
    building a user-facing path the same way. One of them is in the same JSON
    payload as a field that already does it correctly.
    """

    def test_the_snippets_field_is_relative_like_its_neighbours(self, tmp_path: Path) -> None:
        """``snippets[].file`` was absolute while ``references[]`` beside it was not.

        The same expression already computed the relative form to decide whether
        the finding was suppressed, then emitted the absolute one as the value.
        """
        import json
        import os
        import shutil
        import subprocess

        zenzic = shutil.which("zenzic")
        if zenzic is None:
            pytest.skip("needs the installed zenzic console script")

        (tmp_path / "docs").mkdir()
        (tmp_path / ".zenzic.toml").write_text(
            'docs_dir = "docs"\nfail_under = 0\n\n[build_context]\nengine = "standalone"\n',
            encoding="utf-8",
        )
        (tmp_path / "docs" / "index.md").write_text(
            "# T\n\nPadding prose so the word-count rule stays quiet and only the "
            "snippet under discussion decides what this page reports.\n\n"
            "```python\nprint('unclosed'\n```\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        proc = subprocess.run(  # noqa: S603
            [zenzic, "check", "all", "--no-header", "--format", "json"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=env,
        )
        payload = json.loads(proc.stdout)
        assert payload["snippets"], (
            "the fixture produced no snippet finding, so this assertion proves "
            f"nothing: {proc.stdout[:400]!r}"
        )
        for entry in payload["snippets"]:
            assert not Path(entry["file"]).is_absolute(), (
                f"snippets[].file is absolute ({entry['file']!r}) while references[] "
                "in the same payload is relative -- one document, two conventions"
            )
        assert str(tmp_path) not in proc.stdout, "the project root leaked into the JSON"

    def test_there_is_one_relativising_construction_not_two(self) -> None:
        """``_shared._rel`` duplicated ``repo_relative_label`` character for character.

        Two copies of the same four lines agree today and drift the day one of
        them grows a case. A guarantee made in two places is made in neither.
        """
        from zenzic.cli import _shared
        from zenzic.core.validator import repo_relative_label

        src = Path(_shared.__file__).read_text(encoding="utf-8")
        assert "repo_relative_label" in src, (
            "_shared.py no longer delegates to the shared relativising helper, so "
            "there are two independent implementations again"
        )
        root = Path("/tmp/root")
        assert repo_relative_label(root / "docs" / "a.md", root) == "docs/a.md"
        assert repo_relative_label(Path("/elsewhere/b.md"), root) == "/elsewhere/b.md"
