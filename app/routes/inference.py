"""Inference API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.auth import require_api_key
from app.batcher import GatewayProcessingError, QueueSaturatedError
from app.dependencies import get_gateway, get_rate_limiter
from app.logging_config import request_id_var
from app.metrics import REQUESTS_TOTAL
from app.rate_limit import RateLimiter
from app.schemas import ErrorResponse, InferenceRequest, InferenceResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inference"])


@router.post(
    "/v1/infer",
    response_model=InferenceResponse,
    responses={
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def infer(
    request: Request,
    body: InferenceRequest,
    api_key: str = Depends(require_api_key),
    gateway=Depends(get_gateway),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    x_stub_force_fail: str | None = Header(default=None, alias="X-Stub-Force-Fail"),
    x_stub_simulate_timeout: str | None = Header(default=None, alias="X-Stub-Simulate-Timeout"),
) -> InferenceResponse:
    request_id = getattr(request.state, "request_id", request_id_var.get())

    if not await rate_limiter.allow(api_key):
        REQUESTS_TOTAL.labels(status="429", error_type="rate_limit").inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Per-key rate limit exceeded",
        )

    force_fail = (x_stub_force_fail or "").lower() in {"1", "true", "yes"}
    simulate_timeout = (x_stub_simulate_timeout or "").lower() in {"1", "true", "yes"}

    try:
        result = await gateway.submit(
            request_id,
            api_key,
            body,
            force_fail=force_fail,
            simulate_timeout=simulate_timeout,
        )
    except QueueSaturatedError:
        REQUESTS_TOTAL.labels(status="503", error_type="queue_full").inc()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue saturated")
    except GatewayProcessingError as exc:
        REQUESTS_TOTAL.labels(status="504", error_type="upstream").inc()
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))

    REQUESTS_TOTAL.labels(status="200", error_type="none").inc()
    logger.info("inference ok model_id=%s batch_id=%s", body.model_id, result.batch_id)
    return result
