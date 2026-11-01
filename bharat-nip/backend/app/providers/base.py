from __future__ import annotations

from pydantic import BaseModel


class ProviderHealth(BaseModel):
    ok: bool
    detail: str


class ProviderError(Exception):
    """A provider call failed (network, HTTP error, malformed response)."""
