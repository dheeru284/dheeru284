from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_embedding_provider_dep,
    get_llm_provider_dep,
    get_settings_dep,
)
from app.core.config import Settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.schemas.system import (
    EmbeddingProviderInfo,
    Liveness,
    LLMProviderInfo,
    ProvidersInfo,
    Readiness,
)
from app.services.readiness import check_readiness, readiness_http_status

router = APIRouter(tags=["system"])

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
LLMDep = Annotated[LLMProvider, Depends(get_llm_provider_dep)]
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider_dep)]


@router.get("/health", response_model=Liveness)
def health(settings: SettingsDep) -> Liveness:
    return Liveness(status="ok", version=settings.app_version)


@router.get("/health/ready", response_model=Readiness, responses={503: {"model": Readiness}})
def ready(
    db: Annotated[Session, Depends(get_db)],
    settings: SettingsDep,
    llm: LLMDep,
    embeddings: EmbeddingDep,
) -> JSONResponse:
    result = check_readiness(db, settings, llm, embeddings)
    return JSONResponse(status_code=readiness_http_status(result), content=result.model_dump())


@router.get("/system/providers", response_model=ProvidersInfo)
def providers(llm: LLMDep, embeddings: EmbeddingDep) -> ProvidersInfo:
    # Phase 1a restricts this to ADMIN once auth exists (API_DESIGN.md §3.1).
    return ProvidersInfo(
        llm=LLMProviderInfo(name=llm.name, model=llm.model, is_mock=llm.is_mock),
        embedding=EmbeddingProviderInfo(
            name=embeddings.name,
            model=embeddings.model,
            dimensions=embeddings.dimensions,
            is_mock=embeddings.is_mock,
        ),
    )
