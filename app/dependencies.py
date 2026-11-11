"""Shared FastAPI dependencies and application state."""

from __future__ import annotations

from fastapi import Request

from app.batcher import InferenceGateway
from app.rate_limit import RateLimiter


def get_gateway(request: Request) -> InferenceGateway:
    return request.app.state.gateway


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter
