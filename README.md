# inference-gateway

A small **Python/FastAPI** inference gateway built as an employer-relevant portfolio sample for teams working on **large-scale LIVE and recommendation-style inference plumbing** (e.g. roles like [TikTok LIVE AI Infrastructure](https://lifeattiktok.com/search/7632259156078627125) and [recommendation infrastructure](https://lifeattiktok.com/search/7667934266018023733)). **This is an independent demo project** — it is **not affiliated with TikTok** and does not imply current hiring.

The service sits in front of a **clearly labeled local stub model** (no GPU, no paid cloud APIs). It demonstrates patterns production gateways often need: **micro-batching**, **bounded queues / backpressure**, **API-key auth with per-key rate limits**, **timeouts with bounded retries**, **structured logs + request IDs**, and **Prometheus metrics**.

> **Not production-ready.** Intended for learning, interviews, and local experimentation only.

## Quick start

### Local (Python)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export API_KEYS_JSON='{"demo-key-1": {"limit_per_minute": 120}}'
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Docker Compose

```bash
docker compose up --build
```

### Demo inference call

```bash
curl -sS -X POST http://127.0.0.1:8080/v1/infer \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key-1' \
  -H 'X-Request-ID: demo-req-1' \
  -d '{"model_id":"stub-live-ranker-v0","features":{"room_id":"live-42","viewer_count":900}}' | jq
```

### Health & metrics

```bash
curl -sS http://127.0.0.1:8080/health/live
curl -sS http://127.0.0.1:8080/health/ready
curl -sS http://127.0.0.1:8080/metrics | head
```

## Architecture

```text
Client ──► FastAPI (/v1/infer)
            ├─ API-key auth + per-key rate limit
            ├─ Bounded asyncio queue (503 when full)
            ├─ Micro-batcher (max size + wait window)
            ├─ Stub upstream (deterministic SHA-based scores)
            └─ Prometheus /metrics + structured JSON logs
```

| Component | Role |
|-----------|------|
| `app/routes/inference.py` | HTTP surface, status mapping |
| `app/batcher.py` | Queue + batching worker, retries |
| `app/stub_model.py` | **Stub** inference (sleep + deterministic hash) |
| `app/auth.py` / `app/rate_limit.py` | API keys & fixed-window limits |
| `app/metrics.py` | Prometheus counters/histograms |

## Configuration

Environment variables (defaults in `app/config.py`):

| Variable | Meaning |
|----------|---------|
| `API_KEYS_JSON` | JSON map of key → `{ "limit_per_minute": N }` |
| `MAX_QUEUE_SIZE` | Backpressure threshold |
| `MAX_BATCH_SIZE` / `BATCH_WAIT_MS` | Micro-batch bounds |
| `UPSTREAM_TIMEOUT_SECONDS` | Per-attempt stub call timeout |
| `MAX_RETRIES` / `RETRY_BASE_DELAY_MS` | Bounded exponential backoff |
| `STUB_LATENCY_MS` | Artificial stub delay |

**Never commit real secrets.** Demo keys are placeholders only.

## Design decisions (modest scope)

1. **Single-process asyncio** — Simple to reason about for a portfolio; a real fleet would shard batchers or use a dedicated queue service.
2. **In-memory rate limits** — Adequate for a laptop demo; production would use Redis or a sidecar.
3. **Hash-based stub outputs** — Deterministic tests without ML dependencies.
4. **Batch-level retries** — On transient stub failure, the whole micro-batch is retried (bounded). Items are not left hanging without a future result.

## Limitations

- No TLS termination, model versioning, A/B routing, or autoscaling.
- No persistent audit store; logs go to stdout only.
- Rate limits reset per process (not shared across replicas).
- Stub does not validate feature schemas beyond JSON shape.

## Failure experiments (local)

| Experiment | How | Expected |
|------------|-----|----------|
| Auth failure | Omit `X-API-Key` | `401` |
| Rate limit | Use `demo-key-2` in compose defaults; spam requests | `429` |
| Queue saturation | Lower `MAX_QUEUE_SIZE`, raise `STUB_LATENCY_MS`, concurrent `curl` | `503` |
| Forced upstream error | Header `X-Stub-Force-Fail: true` (succeeds after retries) | `200` after backoff |
| Upstream timeout | `X-Stub-Simulate-Timeout: true` | `504` after retries exhausted |
| Observe batching | Run several concurrent POSTs within `BATCH_WAIT_MS` | Same `batch_id` in responses |

## Tests

```bash
pytest -q
```

Covers auth, batching, queue saturation, timeout/retry behavior, health, and metrics exposition.

## AI assistance disclosure

Portions of this repository were produced with **AI-assisted development tools** (interactive coding assistants). A human author directed the scope, reviewed the architecture for honesty and safety constraints, and validated tests and container builds. **No generative model is claimed as a co-author of record for employer submissions without your own review.** Treat this README and code as a starting point — adapt, harden, and replace the stub before any real deployment.

## License

MIT — see [LICENSE](LICENSE).
