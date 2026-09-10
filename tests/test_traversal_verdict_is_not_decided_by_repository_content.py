# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Creating a file must not downgrade a path-traversal finding.

Three sites downgraded a traversal from ``Z203`` (exit 3, non-suppressible) to
``Z202`` (exit 1) when the resolved target happened to exist on disk. The
downgrade was added for a real reason -- a repository folder named ``dev/`` or
``usr/`` produced false positives -- but ``is_file()`` answers *"does this path
exist"*, and the disk is authored by whoever authors the link. A file in the
repository therefore acted as a suppression mechanism for a code documented as
non-suppressible, and ``--exit-zero`` covered the exit 1 that replaced exit 3.

The replacement discriminator is arithmetic, not filesystem state: a relative
link escapes when its *lexically* normalised target leaves ``docs_root``. For a
docs-root-relative URL naming an OS directory, the supported way to declare the
section legitimate is ``absolute_path_allowlist`` -- a declaration the author
makes deliberately, rather than a side effect of a file existing.

Every payload is paired with the false positive the downgrade existed to
prevent, because a classifier that answered "escape" unconditionally would pass
the payloads on its own.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


CONFIG = """\
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
"""

PADDING = (
    "Padding prose so the word-count rule stays quiet and only the link decides the exit code."
)


def _project(tmp_path: Path, link: str, *, extra: dict[str, str] | None = None) -> Path:
    root = tmp_path
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / ".zenzic.toml").write_text(CONFIG, encoding="utf-8")
    (root / "docs" / "index.md").write_text(f"# T\n\n[t]({link})\n\n{PADDING}\n", encoding="utf-8")
    for rel, body in (extra or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


#: The installed console script. `python -m zenzic` is not an entry point --
#: the package has no `__main__` -- and the exit code is the whole subject of
#: this file, so it is read from the same binary a user runs.
ZENZIC = shutil.which("zenzic")


def _exit_code(root: Path) -> int:
    assert ZENZIC, "the zenzic console script is not on PATH"
    return subprocess.run(  # noqa: S603
        [ZENZIC, "check", "all", "--quiet"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).returncode


class TestRelativeTraversal:
    def test_escape_is_exit_3(self, tmp_path: Path) -> None:
        assert _exit_code(_project(tmp_path, "../../../../etc/passwd")) == 3

    def test_planting_the_target_does_not_downgrade_it(self, tmp_path: Path) -> None:
        root = _project(
            tmp_path,
            "../../../../etc/passwd",
            extra={"docs/etc/passwd": "harmless\n"},
        )
        assert _exit_code(root) == 3, "a file in the repository downgraded the finding"


class TestAbsoluteTraversal:
    def test_system_root_url_is_exit_3(self, tmp_path: Path) -> None:
        assert _exit_code(_project(tmp_path, "/etc/passwd")) == 3

    def test_planting_the_target_does_not_downgrade_it(self, tmp_path: Path) -> None:
        root = _project(tmp_path, "/etc/passwd", extra={"docs/etc/passwd": "harmless\n"})
        assert _exit_code(root) == 3, "a file in the repository downgraded the finding"


class TestTheFalsePositiveTheDowngradeExistedToPrevent:
    """A documentation section whose name collides with an OS directory."""

    def test_a_real_docs_section_named_dev_is_declared_not_discovered(self, tmp_path: Path) -> None:
        root = _project(
            tmp_path,
            "/dev/setup/",
            extra={"docs/dev/setup.md": f"# Setup\n\n{PADDING}\n"},
        )
        # Root-level keys go above the first table: a key written after
        # `[build_context]` is swallowed into it by the TOML parser, silently.
        (root / ".zenzic.toml").write_text(
            'absolute_path_allowlist = ["/dev/"]\n' + CONFIG, encoding="utf-8"
        )
        assert _exit_code(root) == 0, (
            "an allowlisted documentation section must not be a traversal finding"
        )


class TestControl:
    def test_an_ordinary_relative_link_is_clean(self, tmp_path: Path) -> None:
        root = _project(tmp_path, "./guide.md", extra={"docs/guide.md": f"# G\n\n{PADDING}\n"})
        assert _exit_code(root) == 0
