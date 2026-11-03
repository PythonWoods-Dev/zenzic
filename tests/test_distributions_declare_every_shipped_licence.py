# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The sdist and the wheel declare the project's licence, and ship the text of every licence of what they carry.

`pyproject.toml` declares `license = "Apache-2.0"`, the licence of Zenzic's own
code: under PEP 639 `License-Expression` "describes a Project's license(s)", and
the PEP leaves the licences of individual files out of its scope. The sdist also
ships files under other licences: the Roboto fonts (OFL-1.1), the compiled
Tailwind bundle (MIT) and the OASIS SARIF schema (the OASIS Notices). What makes
shipping them lawful is that each keeps its own licence, declared in REUSE.toml
and named in NOTICE, and that its text travels with the archive: `license-files`
is the field PEP 639 gives for "license text, author/attribution information, or
other legal notices that need to be distributed with the package".

This test builds both distributions with `uv build` and reads what an installer
or an auditor reads: `PKG-INFO` in the sdist, `METADATA` in the wheel. It checks
that the expression is the project's, valid SPDX; that every licence `reuse`
declares for a file inside the sdist has its text among the declared
`License-File`s; and that each declared file is in the archive.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from email.message import Message
from email.parser import Parser
from pathlib import Path

import pytest
from packaging.licenses import canonicalize_license_expression
from reuse.project import Project


ROOT = Path(__file__).resolve().parent.parent

EXPECTED = "Apache-2.0"


@dataclass(frozen=True)
class Archive:
    files: frozenset[str]
    metadata: Message


def _licences(expression: str) -> set[str]:
    tokens = expression.replace("(", " ").replace(")", " ").split()
    return set(tokens) - {"AND", "OR", "WITH"}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Archive]:
    uv = shutil.which("uv")
    assert uv is not None, "uv builds the distributions this test reads"
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [uv, "build", "--out-dir", str(out), str(ROOT)],
        check=True,
        capture_output=True,
        timeout=110,
    )
    (sdist,) = out.glob("*.tar.gz")
    (wheel,) = out.glob("*.whl")
    with tarfile.open(sdist) as tar:
        members = frozenset(m.name.split("/", 1)[1] for m in tar.getmembers() if m.isfile())
        (pkg_info,) = (
            m for m in tar.getmembers() if m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")
        )
        stream = tar.extractfile(pkg_info)
        assert stream is not None
        sdist_meta = Parser().parsestr(stream.read().decode("utf-8"))
    with zipfile.ZipFile(wheel) as whl:
        names = frozenset(whl.namelist())
        (metadata,) = (n for n in names if n.endswith(".dist-info/METADATA"))
        wheel_meta = Parser().parsestr(whl.read(metadata).decode("utf-8"))
    return {"sdist": Archive(members, sdist_meta), "wheel": Archive(names, wheel_meta)}


@pytest.mark.parametrize("archive", ["sdist", "wheel"])
def test_the_expression_is_the_expected_valid_spdx(built: dict[str, Archive], archive: str) -> None:
    expression = built[archive].metadata["License-Expression"]
    assert expression == EXPECTED
    assert canonicalize_license_expression(expression) == expression


def _declared_in_sdist(built: dict[str, Archive]) -> dict[str, str]:
    """Every licence reuse declares for a file inside the sdist, with one file that carries it."""
    project = Project.from_directory(ROOT)
    declared: dict[str, str] = {}
    for rel in sorted(built["sdist"].files):
        path = ROOT / rel
        if not path.is_file():
            continue  # PKG-INFO, written by the backend
        for info in project.reuse_info_of(path):
            for spdx in info.spdx_expressions:
                for licence in spdx.licenses:
                    declared.setdefault(licence, rel)
    return declared


def test_the_sdist_ships_files_under_other_licences_than_the_project(
    built: dict[str, Archive],
) -> None:
    """The premise of the next test: without third-party files it would pass on nothing."""
    assert {"MIT", "OFL-1.1", "LicenseRef-OASIS-Notice"} <= set(_declared_in_sdist(built))


@pytest.mark.parametrize("archive", ["sdist", "wheel"])
def test_every_licence_of_a_shipped_file_has_its_text_among_the_licence_files(
    built: dict[str, Archive], archive: str
) -> None:
    files = set(built[archive].metadata.get_all("License-File") or [])
    assert {"LICENSE", "NOTICE"} <= files
    missing = {
        licence: rel
        for licence, rel in _declared_in_sdist(built).items()
        if f"LICENSES/{licence}.txt" not in files
    }
    assert missing == {}, (
        "a licence of a shipped file, with one file that carries it, whose text is not shipped"
    )


def test_each_declared_licence_file_is_in_its_archive(built: dict[str, Archive]) -> None:
    sdist, wheel = built["sdist"], built["wheel"]
    for rel in sdist.metadata.get_all("License-File") or []:
        assert rel in sdist.files, rel
    (dist_info,) = {n.split("/", 1)[0] for n in wheel.files if ".dist-info/" in n}
    for rel in wheel.metadata.get_all("License-File") or []:
        assert f"{dist_info}/licenses/{rel}" in wheel.files, rel
