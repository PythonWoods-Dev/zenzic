# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A link to a non-ASCII host reaches anyio already encoded, with IDNA 2008.

Before 4.14.2, anyio encodes a host name with IDNA 2003 when it opens a TLS
connection (GHSA-82r6-8w77-94w6), and the external-link check reaches that code
through ``httpx.AsyncClient``. It never sees a non-ASCII name: httpx encodes the
host with the ``idna`` package before httpcore calls ``anyio.connect_tcp``. This
test is the guard should httpx stop doing so (decided 2026-10-13). ``straße.de``
is the case that tells the two encodings apart: IDNA 2008 gives
``xn--strae-oqa.de``, IDNA 2003 gives ``strasse.de``.

No network: ``anyio.connect_tcp`` records the host it receives and refuses the
connection, so the link is reported as unreachable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import anyio
import pytest

from zenzic.core.validator import _check_external_links
from zenzic.models.config import ZenzicConfig


HOST = "straße.de"
IDNA_2008 = "xn--strae-oqa.de"
IDNA_2003 = "strasse.de"

_PROXY_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def _hosts_reaching_anyio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    for variable in _PROXY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    seen: list[str] = []

    async def refuse(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs["remote_host"] if "remote_host" in kwargs else args[0])
        raise OSError("connection refused by the test")

    monkeypatch.setattr(anyio, "connect_tcp", refuse)
    errors = asyncio.run(
        _check_external_links([(f"https://{HOST}/", "docs/index.md", 1)], ZenzicConfig(), tmp_path)
    )
    assert errors, "the refused connection must surface as a finding"
    return seen


def test_anyio_receives_the_idna_2008_encoding_of_the_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = _hosts_reaching_anyio(monkeypatch, tmp_path)
    assert seen, "the check never reached anyio.connect_tcp"
    assert set(seen) == {IDNA_2008}
    assert all(host.isascii() for host in seen)
    assert IDNA_2003 not in seen
