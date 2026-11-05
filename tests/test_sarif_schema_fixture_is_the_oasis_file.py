# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The SARIF schema the suite validates against is the OASIS file, unmodified.

`tests/fixtures/sarif-2.1.0-schema.json` was SchemaStore's copy
(`src/schemas/json/sarif-2.1.0.json` at 734c0e50), which rewrites the OASIS
schema: a draft-07 `$schema`, a `$id` on GitHub, keys reordered. The OASIS
Notices that govern the schema forbid modifying the document itself except as
needed to develop an OASIS Technical Committee deliverable or to translate it,
so a modified copy is not one this project may ship.

The fixture is now the schema the OASIS SARIF v2.1.0 "Latest stage" page names
(the OASIS Standard incorporating Approved Errata 01, 28 August 2023), byte for
byte. Its notice, the Notices section of that 2023 deliverable, is
`LICENSES/LicenseRef-OASIS-Notice.txt`. This test pins the file's SHA-256, so an
edit, a reformat or a swap for another copy fails here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sarif-2.1.0-schema.json"
NOTICE = Path(__file__).resolve().parent.parent / "LICENSES" / "LicenseRef-OASIS-Notice.txt"

#: https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json,
#: fetched 2026-11-02.
OASIS_URL = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
)
OASIS_SHA256 = "c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e"


def test_the_fixture_is_byte_identical_to_the_oasis_schema() -> None:
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == OASIS_SHA256


def test_the_fixture_names_itself_as_the_oasis_file() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["id"] == OASIS_URL


def test_the_oasis_notice_ships_beside_it() -> None:
    text = NOTICE.read_text(encoding="utf-8")
    assert text.startswith("Copyright © OASIS Open 2023. All Rights Reserved.")
