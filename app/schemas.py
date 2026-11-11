"""Request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    """Single inference item accepted by the gateway."""

    model_id: str = Field(default="stub-live-ranker-v0", description="Logical model name (stub only).")
    features: dict[str, Any] = Field(default_factory=dict, description="Opaque feature payload.")
    request_note: str | None = Field(
        default=None,
        description="Optional client note; not sent to model weights.",
    )


class InferenceResponse(BaseModel):
    request_id: str
    model_id: str
    predictions: dict[str, Any]
    batch_id: str
    stub: bool = True


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
