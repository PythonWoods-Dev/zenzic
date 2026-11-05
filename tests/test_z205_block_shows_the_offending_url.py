# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The forbidden-scheme block must show the URL, not the attribute's name.

A `Z205` row was corrected earlier this cycle to print `Link:` with the offending
URL *in full*, on the argument that masking hides the thing the reader has to
edit. The label changed and the value did not: `match_text` was set to the
attribute **name**, so the block read `Link:  href`.

The credential path shares this plumbing and must keep behaving differently: a
`Z201` value is masked on purpose, because that output lands in CI logs. Both
directions are asserted here, because changing one and breaking the other is the
plausible failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


CONFIG = 'docs_dir = "docs"\nfail_under = 0\n\n[build_context]\nengine = "standalone"\n'
PROSE = (
    "Padding prose so the word-count rule stays quiet and only the finding under "
    "discussion decides what this page reports today."
)
ZENZIC = shutil.which("zenzic")
pytestmark = pytest.mark.skipif(ZENZIC is None, reason="needs the installed zenzic console script")


def _run(tmp_path: Path, body: str) -> tuple[str, int]:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / ".zenzic.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "docs" / "index.mdx").write_text(f"# T\n\n{body}\n\n{PROSE}\n", encoding="utf-8")
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["COLUMNS"] = "220"
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "references", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return proc.stdout + proc.stderr, proc.returncode


class TestTheUrlIsShown:
    def test_html_anchor(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, '<a href="javascript:alert(1)">x</a>')
        assert rc == 2, out
        assert "javascript:alert(1)" in out, (
            f"the block does not show the offending URL, so the reader cannot see what "
            f"to edit:\n{out}"
        )

    def test_jsx_component(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, '<Link to="javascript:alert(1)">x</Link>')
        assert rc == 2, out
        assert "javascript:alert(1)" in out, f"component form does not show the URL:\n{out}"

    def test_the_attribute_name_alone_is_not_the_value(self, tmp_path: Path) -> None:
        """Guard against the regression this file exists for.

        `Link:  href` is what the block printed before: a row whose value is the
        name of the attribute it came from.
        """
        out, _ = _run(tmp_path, '<a href="javascript:alert(1)">x</a>')
        for line in out.splitlines():
            if "Link:" in line:
                assert line.split("Link:", 1)[1].strip() not in ("href", "src", "to"), (
                    f"the block printed the attribute name as the value: {line!r}"
                )


class TestTheCredentialStaysMasked:
    """The control. A Z201 value must not become visible through this change."""

    def test_credential_is_masked(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, 'aws_key = "AKIAIOSFODNN7EXAMPLE"')
        assert rc == 2, out
        assert "AKIAIOSFODNN7EXAMPLE" not in out, (
            f"the raw credential was printed; that output lands in CI logs:\n{out}"
        )
        assert "AKIA" in out, f"the finding was not reported at all:\n{out}"
