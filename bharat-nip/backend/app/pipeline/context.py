from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ingest.extract import TesseractOCR
from app.ingest.fetcher import SafeFetcher
from app.providers.llm.base import LLMProvider
from app.providers.search.base import SearchProvider


@dataclass
class PipelineContext:
    """Everything a pipeline run needs. Built from settings in workers; tests build it
    with mock providers. Providers are injected, never looked up inside services."""

    session: Session
    settings: Settings
    llm: LLMProvider
    critic_llm: LLMProvider
    search_providers: list[SearchProvider]
    fetcher: SafeFetcher
    ocr: TesseractOCR
