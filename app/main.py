"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.batcher import InferenceGateway
from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware import RequestIdMiddleware
from app.rate_limit import RateLimiter
from app.routes import health, inference, metrics_route
from app.stub_model import StubModelClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    stub = StubModelClient(settings)
    gateway = InferenceGateway(settings, stub)
    rate_limiter = RateLimiter(settings)
    app.state.gateway = gateway
    app.state.rate_limiter = rate_limiter
    app.state.settings = settings
    await gateway.start()
    yield
    await gateway.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Portfolio inference gateway with bounded batching, queue backpressure, "
            "API-key auth, and Prometheus metrics. Uses a **local stub model only**."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(inference.router)
    app.include_router(metrics_route.router)
    return app


app = create_app()
