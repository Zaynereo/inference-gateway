"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request):
    gateway = request.app.state.gateway
    if gateway.is_ready():
        return {"status": "ready", "stub": "local-deterministic"}
    return JSONResponse(status_code=503, content={"status": "not_ready"})
