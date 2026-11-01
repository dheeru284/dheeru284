from __future__ import annotations

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.schemas.system import CheckResult, Readiness


def check_readiness(
    session: Session,
    settings: Settings,
    llm: LLMProvider,
    embeddings: EmbeddingProvider,
) -> Readiness:
    # AI providers are hard requirements only in production; in development the API
    # stays usable for non-AI work while Ollama is down (API_DESIGN.md §3.1).
    ai_required = settings.env == "production"
    checks: dict[str, CheckResult] = {}

    try:
        session.execute(text("SELECT 1"))
        checks["database"] = CheckResult(ok=True, required=True, detail="connected")
        version = session.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        checks["pgvector"] = CheckResult(
            ok=version is not None,
            required=True,
            detail=f"vector {version}" if version else "extension not installed (run migrations)",
        )
    except Exception as exc:  # report, never crash the probe
        session.rollback()
        checks["database"] = CheckResult(ok=False, required=True, detail=f"error: {exc}")
        checks["pgvector"] = CheckResult(ok=False, required=True, detail="database unavailable")

    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        checks["redis"] = CheckResult(ok=True, required=True, detail="connected")
    except redis.RedisError as exc:
        checks["redis"] = CheckResult(ok=False, required=True, detail=f"error: {exc}")

    llm_health = llm.health()
    checks["llm_provider"] = CheckResult(
        ok=llm_health.ok, required=ai_required, detail=f"{llm.name}: {llm_health.detail}"
    )
    emb_health = embeddings.health()
    checks["embedding_provider"] = CheckResult(
        ok=emb_health.ok, required=ai_required, detail=f"{embeddings.name}: {emb_health.detail}"
    )

    all_ok = all(c.ok for c in checks.values())
    return Readiness(status="ok" if all_ok else "degraded", checks=checks)


def readiness_http_status(result: Readiness) -> int:
    required_failed = any(c.required and not c.ok for c in result.checks.values())
    return 503 if required_failed else 200
