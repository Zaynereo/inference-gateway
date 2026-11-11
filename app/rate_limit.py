"""In-memory per API key rate limiting (fixed window per minute)."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from app.config import Settings
from app.metrics import RATE_LIMIT_REJECTS


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def _limit_for_key(self, api_key: str) -> int:
        meta = self._settings.parsed_api_keys().get(api_key, {})
        return int(meta.get("limit_per_minute", 60))

    async def allow(self, api_key: str) -> bool:
        now = int(time.time())
        window_id = now // 60
        async with self._lock:
            w_id, count = self._windows[api_key]
            if w_id != window_id:
                self._windows[api_key] = (window_id, 1)
                return True
            limit = self._limit_for_key(api_key)
            if count >= limit:
                RATE_LIMIT_REJECTS.inc()
                return False
            self._windows[api_key] = (w_id, count + 1)
            return True
