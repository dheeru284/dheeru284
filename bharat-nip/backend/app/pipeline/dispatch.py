"""How pipeline work is started: on a Celery worker (default) or inline in the request
(BNIP_PIPELINE_EXECUTION=inline; also used by the end-to-end tests)."""

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ingest.extract import TesseractOCR
from app.ingest.fetcher import SafeFetcher
from app.pipeline import orchestrator
from app.pipeline.context import PipelineContext
from app.providers.registry import (
    get_critic_llm_provider,
    get_llm_provider,
    get_search_providers,
)


class PipelineDispatcher(Protocol):
    def submit(self, submission_id: uuid.UUID) -> None: ...

    def rerun_claim(self, claim_id: uuid.UUID) -> None: ...

    def analyze_narratives(self) -> None: ...

    def run_org_task(self, task_id: uuid.UUID) -> None: ...


def build_context(session: Session, settings: Settings) -> PipelineContext:
    return PipelineContext(
        session=session,
        settings=settings,
        llm=get_llm_provider(),
        critic_llm=get_critic_llm_provider(),
        search_providers=list(get_search_providers()),
        fetcher=SafeFetcher(settings),
        ocr=TesseractOCR(),
    )


class CeleryDispatcher:
    def submit(self, submission_id: uuid.UUID) -> None:
        from app.workers.tasks import process_submission_task

        process_submission_task.delay(str(submission_id))

    def rerun_claim(self, claim_id: uuid.UUID) -> None:
        from app.workers.tasks import process_claim_task

        process_claim_task.delay(str(claim_id))

    def analyze_narratives(self) -> None:
        from app.workers.tasks import analyze_narratives_task

        analyze_narratives_task.delay()

    def run_org_task(self, task_id: uuid.UUID) -> None:
        from app.workers.tasks import run_org_task_task

        run_org_task_task.delay(str(task_id))


class InlineDispatcher:
    """Runs the pipeline synchronously with the given context (and its session)."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx

    def submit(self, submission_id: uuid.UUID) -> None:
        self.ctx.session.commit()
        orchestrator.process_submission(self.ctx, submission_id)
        self.analyze_narratives()

    def rerun_claim(self, claim_id: uuid.UUID) -> None:
        self.ctx.session.commit()
        orchestrator.process_claim(self.ctx, claim_id)
        self.analyze_narratives()

    def analyze_narratives(self) -> None:
        from app.narratives.engine import run_engine

        self.ctx.session.commit()
        run_engine(self.ctx.session)
        self.ctx.session.commit()

    def run_org_task(self, task_id: uuid.UUID) -> None:
        from app.org.engine import run_task

        self.ctx.session.commit()
        run_task(self.ctx, task_id)
        self.ctx.session.commit()
