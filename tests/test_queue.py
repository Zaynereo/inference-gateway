"""Queue saturation and backpressure tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
async def saturated_client() -> AsyncIterator[AsyncClient]:
    get_settings.cache_clear()
    import os

    os.environ.update(
        {
            "MAX_QUEUE_SIZE": "2",
            "MAX_BATCH_SIZE": "1",
            "BATCH_WAIT_MS": "10",
            "STUB_LATENCY_MS": "400",
            "UPSTREAM_TIMEOUT_SECONDS": "5",
            "API_KEYS_JSON": '{"test-key": {"limit_per_minute": 1000}}',
        }
    )
    get_settings.cache_clear()
    application = create_app()
    async with LifespanManager(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_queue_returns_503_when_saturated(saturated_client: AsyncClient) -> None:
    headers = {"X-API-Key": "test-key"}
    payload = {"features": {"q": 1}}

    async def infer():
        return await saturated_client.post("/v1/infer", json=payload, headers=headers)

    tasks = [asyncio.create_task(infer()) for _ in range(6)]
    results = await asyncio.gather(*tasks)
    codes = [r.status_code for r in results]
    assert 503 in codes
    assert 200 in codes
