# Inference Gateway — Interview Notes (Habib Noor portfolio)

**Scope:** FastAPI gateway in front of a **local stub** model. Independent demo; not affiliated with TikTok.

## Architecture (actual)

- **Ingress:** `POST /v1/infer` with JSON `features` + optional `model_id`.
- **Auth:** `X-API-Key` or `Authorization: Bearer` matched against `API_KEYS_JSON`.
- **Rate limit:** Per-key fixed 60s window counter in memory (`app/rate_limit.py`).
- **Backpressure:** `asyncio.Queue(maxsize=MAX_QUEUE_SIZE)`; full queue → HTTP 503.
- **Batching:** Single worker coroutine gathers items until `MAX_BATCH_SIZE` or `BATCH_WAIT_MS` (`app/batcher.py`).
- **Upstream:** `StubModelClient` — sleep + SHA256 deterministic score/label (`app/stub_model.py`).
- **Resilience:** `asyncio.wait_for` timeout; retry whole batch with exponential backoff; futures always settled.
- **Observability:** JSON logs with `request_id`; Prometheus on `/metrics`; `/health/live` and `/health/ready`.

## Key code paths

1. `app/main.py` — lifespan starts `InferenceGateway` worker.
2. `app/routes/inference.py` — auth → rate limit → `gateway.submit()`.
3. `app/batcher.py` — `_worker_loop` / `_flush_batch` / metrics.
4. `app/middleware.py` — `X-Request-ID` propagation.

## Tradeoffs

| Choice | Pro | Con |
|--------|-----|-----|
| In-proc queue + batcher | Easy to test | Not horizontally scalable as-is |
| Batch-level retry | Simple correctness | Retries duplicate work for whole batch |
| Stub hash scores | Deterministic CI | Not representative ML latency distributions |
| Fixed-window rate limit | O(1) | Burst at window edges |

## Known gaps

- No OpenTelemetry traces (metrics only).
- No graceful drain on SIGTERM beyond worker stop.
- No dynamic batching based on SLA or model type.
- Readiness does not deep-check stub beyond worker alive.

## Interview Q&A (25+)

1. **What problem does this solve?** Colocating HTTP concerns (auth, limits, observability) away from model runtimes.
2. **Why batching?** Amortize fixed per-call overhead; common in LIVE ranking at high QPS.
3. **How is batch size bounded?** `MAX_BATCH_SIZE` hard cap plus `BATCH_WAIT_MS` deadline.
4. **What triggers 503?** `QueueFull` on bounded asyncio queue.
5. **How do you avoid unbounded memory?** Fixed queue size; no unbounded client buffering in gateway.
6. **Auth design?** Header-based API keys from env JSON — no keys in logs.
7. **Rate limit algorithm?** Fixed window per minute per key (in-memory).
8. **Why not token bucket here?** Simplicity for portfolio; mention bucket as upgrade path.
9. **Timeout scope?** Wraps entire stub batch call per attempt.
10. **Retry policy?** `MAX_RETRIES` with exponential backoff from `RETRY_BASE_DELAY_MS`.
11. **Idempotency?** Not implemented; clients would need idempotency keys for production.
12. **How are request IDs handled?** Middleware accepts or generates UUID; echoed in response header.
13. **Structured logging format?** Single-line JSON to stdout with `request_id` field.
14. **Prometheus metrics?** Request totals, latency histogram, batch size, queue depth, retries, rejections.
15. **Liveness vs readiness?** Live = process up; ready = batch worker task running.
16. **Stub labeled how?** Response `stub: true` and `predictions.stub_backend: true`.
17. **Determinism in tests?** Hash of request_id + features → score/label.
18. **Concurrency model?** asyncio event loop; one batch worker (could shard workers later).
19. **Failure mode: slow stub?** Queue fills → backpressure; latency histogram grows.
20. **Failure mode: stub errors?** Batch retry; final failure → 504 to all items in batch.
21. **Docker healthcheck?** HTTP GET `/health/ready` from inside container.
22. **Config management?** `pydantic-settings` with env aliases.
23. **Security gap?** No mTLS or OAuth; demo keys only.
24. **How to scale horizontally?** External queue (Kafka/SQS), sticky batching or centralized batcher service.
25. **GPU path?** Replace `StubModelClient` with gRPC/HTTP to Triton/TorchServe; keep queue/batch layer.
26. **Why FastAPI?** Async-native, OpenAPI docs, familiar to infra/ML platform teams.
27. **CI guarantees?** `pytest` + `docker build` on push/PR — no fabricated benchmarks.
28. **Difference vs API gateway (Kong)?** This layer is inference-aware (batching, model stub, ML metrics).
29. **Backpressure alternatives?** HTTP 429, max connections, admission control at load balancer.
30. **What would you add for TikTok-style LIVE?** Separate hot/cold paths, regional routing, feature cache — out of scope here.
