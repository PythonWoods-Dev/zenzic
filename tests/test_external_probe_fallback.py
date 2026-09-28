# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The external-link probe retries with GET on any HEAD failure, not only on 405.

The VS Code Marketplace answers HEAD with 404 and GET with 200; the probe
reported a listing that exists as broken (measured 2026-09-17).
"""

from __future__ import annotations

import asyncio

import httpx

from zenzic.core.validator import _ping_url


def _probe(head_status: int, get_status: int) -> tuple[str | None, list[str]]:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(head_status if request.method == "HEAD" else get_status)

    async def run() -> str | None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _ping_url(client, "https://example.test/listing", {}, 0.0)

    return asyncio.run(run()), seen


def test_head_404_get_200_is_alive() -> None:
    result, seen = _probe(404, 200)
    assert result is None and seen == ["HEAD", "GET"]


def test_head_404_get_404_is_reported_with_the_get_status() -> None:
    result, seen = _probe(404, 404)
    assert result is not None and "404" in result and seen == ["HEAD", "GET"]


def test_head_405_still_falls_back() -> None:
    result, seen = _probe(405, 200)
    assert result is None and seen == ["HEAD", "GET"]


def test_head_403_is_alive_without_a_second_request() -> None:
    result, seen = _probe(403, 500)
    assert result is None and seen == ["HEAD"]


def test_head_500_get_500_is_reported() -> None:
    result, seen = _probe(500, 500)
    assert result is not None and seen == ["HEAD", "GET"]
