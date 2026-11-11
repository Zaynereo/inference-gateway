"""Pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


def _reset_settings(**env: str) -> None:
    for key, value in env.items():
        os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
def app_factory():
    def _make(**env: str):
        _reset_settings(**env)
        return create_app()

    yield _make
    get_settings.cache_clear()


@pytest.fixture
async def client(app_factory) -> AsyncIterator[AsyncClient]:
    application = app_factory(
        MAX_QUEUE_SIZE="8",
        MAX_BATCH_SIZE="4",
        BATCH_WAIT_MS="80",
        STUB_LATENCY_MS="15",
        MAX_RETRIES="2",
        RETRY_BASE_DELAY_MS="10",
        UPSTREAM_TIMEOUT_SECONDS="2",
        API_KEYS_JSON='{"test-key": {"limit_per_minute": 1000}, "slow-key": {"limit_per_minute": 2}}',
    )
    async with LifespanManager(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": "test-key"}
