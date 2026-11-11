"""Application configuration from environment variables."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "inference-gateway"
    log_level: str = "INFO"

    # API keys: JSON object {"key-id": {"limit_per_minute": 60}, ...}
    api_keys_json: str = Field(
        default='{"demo-key-1": {"limit_per_minute": 120}, "demo-key-2": {"limit_per_minute": 10}}',
        alias="API_KEYS_JSON",
    )

    max_queue_size: int = Field(default=32, alias="MAX_QUEUE_SIZE")
    max_batch_size: int = Field(default=8, alias="MAX_BATCH_SIZE")
    batch_wait_ms: int = Field(default=50, alias="BATCH_WAIT_MS")

    upstream_timeout_seconds: float = Field(default=5.0, alias="UPSTREAM_TIMEOUT_SECONDS")
    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    retry_base_delay_ms: int = Field(default=25, alias="RETRY_BASE_DELAY_MS")

    stub_latency_ms: int = Field(default=20, alias="STUB_LATENCY_MS")
    stub_fail_probability: float = Field(default=0.0, alias="STUB_FAIL_PROBABILITY")

    @field_validator("stub_fail_probability")
    @classmethod
    def clamp_fail_probability(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    def parsed_api_keys(self) -> dict[str, dict[str, Any]]:
        data = json.loads(self.api_keys_json)
        if not isinstance(data, dict):
            raise ValueError("API_KEYS_JSON must be a JSON object")
        return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
