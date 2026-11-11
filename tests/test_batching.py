"""Batching behavior tests."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_concurrent_requests_share_batch_id(client: AsyncClient, auth_headers: dict) -> None:
    payload = {"features": {"room_id": "live-99"}, "model_id": "stub-live-ranker-v0"}

    async def one() -> str:
        resp = await client.post("/v1/infer", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        return resp.json()["batch_id"]

    batch_ids = await asyncio.gather(*[one() for _ in range(4)])
    assert len(set(batch_ids)) == 1, "expected a single micro-batch within wait window"


@pytest.mark.asyncio
async def test_deterministic_stub_scores(client: AsyncClient, auth_headers: dict) -> None:
    payload = {"features": {"creator_id": "c42", "viewer_count": 1200}}
    same_id = {"features": {"creator_id": "c42", "viewer_count": 1200}}
    a = await client.post("/v1/infer", json=same_id, headers={**auth_headers, "X-Request-ID": "fixed-id-1"})
    b = await client.post("/v1/infer", json=same_id, headers={**auth_headers, "X-Request-ID": "fixed-id-1"})
    assert a.json()["predictions"]["score"] == b.json()["predictions"]["score"]
