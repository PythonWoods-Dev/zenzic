# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A forbidden scheme is not a credential, and must not be reported as one.

The security-breach block is shared by every Tier-0 code. `Z204` already had its
own branch (`Term:`, with advice to remove the term or update the pattern list);
`Z201` and `Z205` shared the remaining one, so a `javascript:` link was printed
under `Credential:` with the advice *"Rotate this credential immediately and
purge it from the repository history."*

Nothing about that is right for a scheme: there is no credential, nothing to
rotate, and no history to purge — the fix is to change the link. It matters more
than a wording slip because the security-tier masking change makes `Z205` fire
for many users for the first time, so the wrong remedy arrives at the moment
they are least able to judge it.

Both codes are asserted here. A branch that labelled everything `Scheme:` would
satisfy a `Z205`-only test.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


CONFIG = """\
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
"""

PROSE = (
    "Padding prose so the word-count rule stays quiet and only the security "
    "finding under discussion decides what this page reports today."
)

ZENZIC = __import__("shutil").which("zenzic")


def _env() -> dict[str, str]:
    """Inherit the real environment, overriding only what these assertions need.

    Passing a hand-built ``env`` of just ``PATH`` looks tidier and breaks Python
    on Windows: without ``SystemRoot`` the interpreter cannot reach the CryptoAPI
    and dies at start-up with ``_Py_HashRandomization_Init: failed to get random
    numbers``. Every assertion here then compares its expected substring against
    that fatal message and reports something false but plausible -- "the scheme
    finding did not fire at all", "the credential label was lost" -- so the
    failure names the wrong defect. Inherit and override instead of enumerating.
    """
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["COLUMNS"] = "200"
    return env


def _run(tmp_path: Path, body: str) -> str:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".zenzic.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text(f"# T\n\n{body}\n\n{PROSE}\n", encoding="utf-8")
    assert ZENZIC, "the zenzic console script is not on PATH"
    proc = subprocess.run(  # noqa: S603
        [ZENZIC, "check", "all"],
        cwd=tmp_path,
        capture_output=True,
        # encoding/errors are explicit: on Windows `text=True` decodes with the
        # locale codec (cp1252), which cannot read the CLI's UTF-8 box-drawing
        # output. The decode fails, stdout comes back None, and every assertion
        # below dies on a TypeError that names nothing real.
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=_env(),
    )
    return proc.stdout + proc.stderr


class TestAForbiddenSchemeIsLabelledAsOne:
    def test_the_label_is_not_credential(self, tmp_path: Path) -> None:
        out = _run(tmp_path, "[click me](javascript:alert(1))")
        assert "forbidden scheme" in out, f"the scheme finding did not fire at all:\n{out}"
        assert "Credential:" not in out, "a forbidden scheme was labelled as a credential"

    def test_the_remedy_is_not_rotation(self, tmp_path: Path) -> None:
        out = _run(tmp_path, "[click me](javascript:alert(1))")
        assert "Rotate this credential" not in out, (
            "a forbidden scheme was given credential-rotation advice"
        )

    def test_the_offending_url_is_shown_in_full(self, tmp_path: Path) -> None:
        """A scheme is not a secret: masking it hides the thing to fix."""
        out = _run(tmp_path, "[click me](javascript:alert(1))")
        assert "javascript:alert(1)" in out, "the offending URL was obfuscated"


class TestARealCredentialKeepsItsLabelAndRemedy:
    """Positive control. Without it, a branch that renamed every label would
    pass the class above."""

    def test_credential_label_and_rotation_advice_survive(self, tmp_path: Path) -> None:
        out = _run(tmp_path, 'aws_key = "AKIAIOSFODNN7EXAMPLE"')
        assert "Credential:" in out, f"the credential label was lost:\n{out}"
        assert "Rotate this credential immediately" in out

    def test_the_credential_itself_is_still_masked(self, tmp_path: Path) -> None:
        out = _run(tmp_path, 'aws_key = "AKIAIOSFODNN7EXAMPLE"')
        assert "AKIAIOSFODNN7EXAMPLE" not in out, "the credential was printed in cleartext"
