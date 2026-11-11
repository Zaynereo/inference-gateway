"""Health and Prometheus metrics tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient) -> None:
    live = await client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["stub"] == "local-deterministic"


@pytest.mark.asyncio
async def test_metrics_exposed(client: AsyncClient, auth_headers: dict) -> None:
    await client.post("/v1/infer", json={"features": {"m": 1}}, headers=auth_headers)
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "inference_requests_total" in body
    assert "inference_queue_depth" in body
    assert "inference_batch_size" in body
