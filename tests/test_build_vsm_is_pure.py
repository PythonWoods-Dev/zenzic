# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`build_vsm()` says it performs no I/O. This is the check that keeps that true.

It claimed "No disk reads occur here" from the day it was written while taking
`extra_content_roots` and calling `build_content_mounts()` on them, which calls
`Path.resolve()` twice per root — filesystem metadata syscalls, and dependent on
the process working directory for a relative path. The claim held only for a
project with no external content roots, which is to say it held wherever nobody
had looked. Mounts are computed by the caller now, where the I/O belongs.

A docstring is not a control. This is: every filesystem-touching `Path` method
is wrapped for the duration of the call and records itself, so a future edit
that reintroduces a `resolve()`, an `exists()` or a `read_text()` anywhere under
`build_vsm` fails here rather than in six months on someone else's monorepo.

Recording rather than raising is deliberate. An exception escaping a patched
`Path.exists()` reaches pytest's own traceback machinery, which calls
`Path.exists()` — the run dies with an INTERNALERROR and no traceback at all.
Verified, not assumed.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.models.vsm import build_vsm


#: Every `Path` member that reaches the operating system. `resolve` and
#: `absolute` are on the list because they read as path arithmetic and are not:
#: both issue syscalls, and both depend on the process working directory.
_FILESYSTEM_MEMBERS = (
    "resolve",
    "absolute",
    "exists",
    "is_file",
    "is_dir",
    "is_symlink",
    "stat",
    "lstat",
    "iterdir",
    "glob",
    "rglob",
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "readlink",
    "samefile",
)


@contextlib.contextmanager
def _recording_filesystem_calls() -> Iterator[list[str]]:
    seen: list[str] = []
    originals = {n: getattr(Path, n) for n in _FILESYSTEM_MEMBERS if hasattr(Path, n)}

    def _wrap(name: str, original: Any) -> Any:
        def _recorded(self: Path, *a: object, **k: object) -> Any:
            seen.append(name)
            return original(self, *a, **k)

        return _recorded

    for name, original in originals.items():
        setattr(Path, name, _wrap(name, original))
    try:
        yield seen
    finally:
        for name, original in originals.items():
            setattr(Path, name, original)


def test_build_vsm_touches_no_filesystem() -> None:
    docs = Path("/project/docs")
    md = {
        docs / "index.md": "# Home\n\nSee [the guide](guide.md).\n",
        docs / "guide.md": "# Guide\n",
    }

    with _recording_filesystem_calls() as seen:
        vsm = build_vsm(StandaloneAdapter(), docs, md)

    assert seen == [], f"build_vsm() reached the filesystem: {sorted(set(seen))}"
    assert sorted(vsm) == ["/", "/guide/"]


def test_build_vsm_touches_no_filesystem_with_mounts() -> None:
    """The path that used to break the claim: external content roots.

    The mount pairs arrive already resolved, so nothing here needs to ask the
    filesystem what they are.
    """
    docs = Path("/project/docs")
    blog = Path("/project/blog")
    md = {docs / "index.md": "# Home\n", blog / "post.md": "# Post\n"}

    with _recording_filesystem_calls() as seen:
        vsm = build_vsm(StandaloneAdapter(), docs, md, extra_mounts=[(blog, "blog")])

    assert seen == [], f"build_vsm() reached the filesystem: {sorted(set(seen))}"
    assert "/blog/post/" in vsm


def test_the_recorder_itself_catches_a_filesystem_call() -> None:
    """A zero-result sweep proves nothing until the instrument has been shown
    to find something."""
    with _recording_filesystem_calls() as seen:
        Path("/project").resolve()

    assert "resolve" in seen


def test_computing_the_mounts_is_what_touches_the_filesystem() -> None:
    """And the I/O still happens — in the caller, where it is declared.

    Without this, the two assertions above could be satisfied by a `build_vsm`
    that had silently stopped supporting external content roots at all.
    """
    from zenzic.core.discovery import build_content_mounts

    with _recording_filesystem_calls() as seen:
        mounts = build_content_mounts([Path("/project/blog")], repo_root=Path("/project"))

    assert "resolve" in seen
    assert mounts == [(Path("/project/blog"), "blog")]
