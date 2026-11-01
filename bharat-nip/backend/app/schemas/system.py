from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Liveness(BaseModel):
    status: Literal["ok"]
    version: str


class CheckResult(BaseModel):
    ok: bool
    required: bool
    detail: str


class Readiness(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, CheckResult]


class LLMProviderInfo(BaseModel):
    name: str
    model: str
    is_mock: bool


class EmbeddingProviderInfo(BaseModel):
    name: str
    model: str
    dimensions: int
    is_mock: bool


class ProvidersInfo(BaseModel):
    llm: LLMProviderInfo
    embedding: EmbeddingProviderInfo
