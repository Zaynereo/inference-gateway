"""Prometheus metrics definitions."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "inference_requests_total",
    "Total inference HTTP requests",
    ["status", "error_type"],
)

REQUEST_LATENCY = Histogram(
    "inference_request_duration_seconds",
    "End-to-end inference request latency",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

BATCH_SIZE = Histogram(
    "inference_batch_size",
    "Items per upstream batch",
    buckets=(1, 2, 4, 8, 16, 32),
)

QUEUE_DEPTH = Gauge("inference_queue_depth", "Current depth of the bounded request queue")

BATCHES_TOTAL = Counter(
    "inference_batches_total",
    "Upstream batch executions",
    ["outcome"],
)

RETRIES_TOTAL = Counter("inference_retries_total", "Retry attempts for upstream calls")

RATE_LIMIT_REJECTS = Counter("inference_rate_limit_rejections_total", "Rejected due to per-key rate limit")

QUEUE_REJECTS = Counter("inference_queue_rejections_total", "Rejected due to saturated queue")
