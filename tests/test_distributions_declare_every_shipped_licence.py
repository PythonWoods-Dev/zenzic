# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The sdist and the wheel declare, in their own metadata, every licence of what they ship.

`pyproject.toml` declared `license = "Apache-2.0"`, and the sdist built from it
ships the Roboto fonts (OFL-1.1), the compiled Tailwind bundle (MIT) and the
OASIS SARIF schema (the OASIS Notices). Under PEP 639 `License-Expression`
describes the archive that carries it, so the sdist's metadata named one licence
of four.

This test builds both distributions with `uv build` and reads what an installer
or an auditor reads: `PKG-INFO` in the sdist, `METADATA` in the wheel. It checks
that the expression is valid SPDX, that every licence `reuse` declares for a file
inside the sdist is in it, that each licence has its text among the declared
`License-File`s, and that each declared file is in the archive.

The two archives carry one expression. hatchling writes `PKG-INFO` and `METADATA`
from the same core metadata (its only per-target metadata setting is
`core-metadata-version`), and the core metadata specification requires a wheel
built from an sdist to repeat every field the sdist does not mark `Dynamic`. The
expression is therefore the sdist's, which also covers the wheel; the wheel
contains only `src/zenzic` and `examples/`, both Apache-2.0.
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

EXPECTED = "Apache-2.0 AND MIT AND OFL-1.1 AND LicenseRef-OASIS-Notice"


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


def test_every_licence_reuse_declares_inside_the_sdist_is_in_the_expression(
    built: dict[str, Archive],
) -> None:
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
    expression = _licences(built["sdist"].metadata["License-Expression"])
    missing = {lic: rel for lic, rel in declared.items() if lic not in expression}
    assert missing == {}, "a licence of a shipped file, with one file that carries it"
    assert set(declared) == expression, "the expression names a licence no shipped file has"


@pytest.mark.parametrize("archive", ["sdist", "wheel"])
def test_each_licence_has_its_text_among_the_licence_files(
    built: dict[str, Archive], archive: str
) -> None:
    meta = built[archive].metadata
    files = set(meta.get_all("License-File") or [])
    assert {"LICENSE", "NOTICE"} <= files
    for licence in _licences(meta["License-Expression"]):
        assert f"LICENSES/{licence}.txt" in files, licence


def test_each_declared_licence_file_is_in_its_archive(built: dict[str, Archive]) -> None:
    sdist, wheel = built["sdist"], built["wheel"]
    for rel in sdist.metadata.get_all("License-File") or []:
        assert rel in sdist.files, rel
    (dist_info,) = {n.split("/", 1)[0] for n in wheel.files if ".dist-info/" in n}
    for rel in wheel.metadata.get_all("License-File") or []:
        assert f"{dist_info}/licenses/{rel}" in wheel.files, rel
