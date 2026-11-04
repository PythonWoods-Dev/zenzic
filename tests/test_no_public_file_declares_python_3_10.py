# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""No public file declares or documents Python 3.10 as supported.

Python 3.10 reached its end of life on 2026-10-01 (PEP 619) and Zenzic requires 3.11. A line that still says
otherwise -- the metadata, a tool's target, the CI matrix, a page that names the floor -- would promise users an
interpreter the package no longer installs on. History is exempt: the changelogs record what was true then, and a
comment that explains a past behaviour of 3.10 declares nothing.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

#: The forms that declare or document the supported interpreters.
DECLARATIONS = [
    re.compile(r'requires-python\s*=\s*">=\s*3\.10"'),
    re.compile(r'python_version\s*=\s*"3\.10"'),
    re.compile(r'target-version\s*=\s*"py310"'),
    re.compile(r"Programming Language :: Python :: 3\.10\b"),
    re.compile(r'python-version:\s*\[[^\]]*"3\.10"'),
    re.compile(r'PYTHONS\s*=\s*\[[^\]]*"3\.10"'),
    re.compile(r'py_[ab]="3\.10"'),
    re.compile(r"uv python install 3\.10\b"),
    re.compile(r"(?i)python\s*3\.10\s*\+"),
    re.compile(r"(?i)python\s*(?:≥|>=)\s*3\.10\b"),
    re.compile(r"\*\*Python\*\*\s*\|\s*≥\s*3\.10\b"),
    re.compile(r"(?i)python 3\.10 or (?:higher|later|newer)"),
    re.compile(r"(?i)on python 3\.10 and 3\.14"),
    re.compile(r"`windows-latest` on 3\.10\b"),
]

#: History, which records what was true when it was written.
EXEMPT = ("CHANGELOG.md", "changelogs/", "tests/test_no_public_file_declares_python_3_10.py")


def declarations(root: Path = ROOT) -> list[str]:
    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    found = []
    for name in tracked:
        if not name or name.startswith(EXEMPT):
            continue
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(form.search(line) for form in DECLARATIONS):
                found.append(f"{name}:{number}: {line.strip()[:100]}")
    return found


def test_no_public_file_declares_or_documents_python_3_10() -> None:
    assert declarations() == []


def test_the_search_finds_a_declaration_that_is_there(tmp_path: Path) -> None:
    """The positive control: the same search finds a 3.10 floor written into a tracked file."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)  # noqa: S607
    (tmp_path / "pyproject.toml").write_text('requires-python = ">=3.10"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("Python 3.10+ was the floor.\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)  # noqa: S607
    assert declarations(tmp_path) == ['pyproject.toml:1: requires-python = ">=3.10"']
