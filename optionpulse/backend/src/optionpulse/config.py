"""Runtime settings, read from ``OPTIONPULSE_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    provider: str = "mock"
    mock_seed: int = 7
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.environ.get("OPTIONPULSE_PROVIDER", "mock").lower()
        if provider != "mock":
            # Broker providers arrive in Phase 3; refuse rather than silently fall back.
            raise ValueError(f"OPTIONPULSE_PROVIDER={provider!r} is not available yet; only 'mock' is supported")
        return cls(
            provider=provider,
            mock_seed=int(os.environ.get("OPTIONPULSE_MOCK_SEED", "7")),
            cors_origins=_csv(os.environ.get("OPTIONPULSE_CORS_ORIGINS", ""))
            or cls().cors_origins,
        )
