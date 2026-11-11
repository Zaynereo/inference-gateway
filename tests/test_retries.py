"""Timeout, retry, and error cleanup tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_force_fail_retries_then_succeeds(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/v1/infer",
        json={"features": {"retry": True}},
        headers={**auth_headers, "X-Stub-Force-Fail": "true"},
    )
    assert resp.status_code == 200
    assert resp.json()["stub"] is True


@pytest.mark.asyncio
async def test_simulated_upstream_timeout_returns_504(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/v1/infer",
        json={"features": {"t": 1}},
        headers={**auth_headers, "X-Stub-Simulate-Timeout": "true"},
    )
    assert resp.status_code == 504


@pytest.mark.asyncio
async def test_request_id_header_propagated(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/v1/infer",
        json={"features": {}},
        headers={**auth_headers, "X-Request-ID": "client-req-abc"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "client-req-abc"
    assert resp.json()["request_id"] == "client-req-abc"
