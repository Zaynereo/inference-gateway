"""Bounded queue and micro-batching pipeline to the stub upstream."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.metrics import BATCHES_TOTAL, BATCH_SIZE, QUEUE_DEPTH, QUEUE_REJECTS, REQUEST_LATENCY, RETRIES_TOTAL
from app.schemas import InferenceRequest, InferenceResponse
from app.stub_model import StubInput, StubModelClient, StubModelError, StubModelTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class PendingItem:
    request_id: str
    api_key: str
    body: InferenceRequest
    future: asyncio.Future[InferenceResponse] = field(repr=False)
    submitted_at: float = field(default_factory=time.perf_counter)
    force_fail: bool = False
    simulate_timeout: bool = False


class InferenceGateway:
    def __init__(self, settings: Settings, stub: StubModelClient) -> None:
        self._settings = settings
        self._stub = stub
        self._queue: asyncio.Queue[PendingItem | None] = asyncio.Queue(maxsize=settings.max_queue_size)
        self._worker_task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    def is_ready(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()

    async def start(self) -> None:
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(self._worker_loop(), name="batcher-worker")
        self._ready.set()
        logger.info("inference gateway worker started")

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        await self._queue.put(None)
        try:
            await asyncio.wait_for(self._worker_task, timeout=5.0)
        except asyncio.TimeoutError:
            self._worker_task.cancel()
        self._worker_task = None
        logger.info("inference gateway worker stopped")

    async def submit(
        self,
        request_id: str,
        api_key: str,
        body: InferenceRequest,
        *,
        force_fail: bool = False,
        simulate_timeout: bool = False,
    ) -> InferenceResponse:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[InferenceResponse] = loop.create_future()
        item = PendingItem(
            request_id=request_id,
            api_key=api_key,
            body=body,
            future=fut,
            force_fail=force_fail,
            simulate_timeout=simulate_timeout,
        )
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            QUEUE_REJECTS.inc()
            QUEUE_DEPTH.set(self._queue.qsize())
            raise QueueSaturatedError("Inference queue is full; try again later")

        QUEUE_DEPTH.set(self._queue.qsize())
        return await fut

    async def _worker_loop(self) -> None:
        while True:
            batch: list[PendingItem] = []
            first = await self._queue.get()
            if first is None:
                self._queue.task_done()
                break
            batch.append(first)
            deadline = time.perf_counter() + (self._settings.batch_wait_ms / 1000.0)

            while len(batch) < self._settings.max_batch_size:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    nxt = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if nxt is None:
                    self._queue.task_done()
                    await self._flush_batch(batch)
                    return
                batch.append(nxt)

            await self._flush_batch(batch)

    async def _flush_batch(self, batch: list[PendingItem]) -> None:
        if not batch:
            return
        batch_id = str(uuid.uuid4())
        BATCH_SIZE.observe(len(batch))
        QUEUE_DEPTH.set(self._queue.qsize())

        force_fail = any(i.force_fail for i in batch)
        simulate_timeout = any(i.simulate_timeout for i in batch)

        items = [
            StubInput(request_id=i.request_id, features=i.body.features) for i in batch
        ]

        attempt = 0
        max_attempts = self._settings.max_retries + 1
        last_err: Exception | None = None

        while attempt < max_attempts:
            attempt += 1
            try:
                coro = self._stub.infer_batch(
                    batch_id,
                    items,
                    force_fail=force_fail and attempt < max_attempts,
                    simulate_timeout=simulate_timeout,
                )
                outputs = await asyncio.wait_for(coro, timeout=self._settings.upstream_timeout_seconds)
                by_id = {o.request_id: o for o in outputs}
                BATCHES_TOTAL.labels(outcome="success").inc()
                for pending in batch:
                    out = by_id.get(pending.request_id)
                    if out is None:
                        self._resolve_error(pending, "Missing stub output for request")
                        continue
                    resp = InferenceResponse(
                        request_id=pending.request_id,
                        model_id=pending.body.model_id,
                        predictions={"score": out.score, "label": out.label, "stub_backend": True},
                        batch_id=batch_id,
                        stub=True,
                    )
                    if not pending.future.done():
                        pending.future.set_result(resp)
                    REQUEST_LATENCY.observe(time.perf_counter() - pending.submitted_at)
                break
            except (StubModelError, StubModelTimeoutError, asyncio.TimeoutError) as exc:
                last_err = exc
                BATCHES_TOTAL.labels(outcome="error").inc()
                if attempt < max_attempts:
                    RETRIES_TOTAL.inc()
                    delay = (self._settings.retry_base_delay_ms / 1000.0) * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                for pending in batch:
                    self._resolve_error(pending, f"Upstream failed after retries: {exc!s}")
            except Exception as exc:  # pragma: no cover - safety net
                last_err = exc
                BATCHES_TOTAL.labels(outcome="error").inc()
                for pending in batch:
                    self._resolve_error(pending, "Internal batch processing error")
                break

        for _ in batch:
            self._queue.task_done()

        if last_err and attempt >= max_attempts:
            logger.error("batch %s failed: %s", batch_id, last_err)

    def _resolve_error(self, pending: PendingItem, message: str) -> None:
        if not pending.future.done():
            pending.future.set_exception(GatewayProcessingError(message))
        REQUEST_LATENCY.observe(time.perf_counter() - pending.submitted_at)


class QueueSaturatedError(Exception):
    pass


class GatewayProcessingError(Exception):
    pass
