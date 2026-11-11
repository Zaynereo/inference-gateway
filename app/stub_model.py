"""Local stub inference backend (no GPU, no paid APIs)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


class StubModelError(Exception):
    """Retryable stub failure."""


class StubModelTimeoutError(StubModelError):
    pass


@dataclass(frozen=True)
class StubInput:
    request_id: str
    features: dict[str, Any]


@dataclass(frozen=True)
class StubOutput:
    request_id: str
    score: float
    label: str


class StubModelClient:
    """Deterministic stub that simulates batched LIVE ranking inference."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._rng = random.Random(42)

    async def infer_batch(
        self,
        batch_id: str,
        items: list[StubInput],
        *,
        force_fail: bool = False,
        simulate_timeout: bool = False,
    ) -> list[StubOutput]:
        latency_s = self._settings.stub_latency_ms / 1000.0
        if simulate_timeout:
            await asyncio.sleep(self._settings.upstream_timeout_seconds + 0.5)
            raise StubModelTimeoutError(f"stub timeout for batch {batch_id}")

        await asyncio.sleep(latency_s)

        if force_fail:
            raise StubModelError(f"stub forced failure for batch {batch_id}")

        if self._settings.stub_fail_probability > 0:
            if self._rng.random() < self._settings.stub_fail_probability:
                raise StubModelError(f"stub random failure for batch {batch_id}")

        outputs: list[StubOutput] = []
        for item in items:
            digest = hashlib.sha256(
                f"{item.request_id}:{sorted(item.features.items())}".encode()
            ).hexdigest()
            score = int(digest[:8], 16) / 0xFFFFFFFF
            label = "engage" if score >= 0.5 else "skip"
            outputs.append(StubOutput(request_id=item.request_id, score=round(score, 6), label=label))

        logger.info("stub batch complete batch_id=%s size=%s", batch_id, len(items))
        return outputs
