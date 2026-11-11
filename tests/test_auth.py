"""Authentication and rate limit tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client: AsyncClient) -> None:
    resp = await client.post("/v1/infer", json={"features": {"user_id": "u1"}})
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/infer",
        json={"features": {"user_id": "u1"}},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_bearer_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/infer",
        json={"features": {"segment": "live"}},
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stub"] is True
    assert body["predictions"]["stub_backend"] is True


@pytest.mark.asyncio
async def test_per_key_rate_limit(client: AsyncClient) -> None:
    headers = {"X-API-Key": "slow-key"}
    statuses = []
    for _ in range(5):
        resp = await client.post("/v1/infer", json={"features": {"i": 1}}, headers=headers)
        statuses.append(resp.status_code)
    assert 429 in statuses
    assert statuses.count(200) <= 2
