"""Agent organization API (AGENT_ORGANIZATION.md)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import Analyst, Reviewer
from app.api.deps import get_db, get_dispatcher, get_settings_dep
from app.core.config import Settings
from app.domain.enums import OrgTaskStatus, WorkflowType
from app.models import OrgTask
from app.org import engine
from app.org.agents import AGENTS
from app.org.policy import SUPPORTED_LANGUAGES
from app.org.queries import agent_states, definition, org_chart, task_detail, task_summary
from app.org.workflows import WORKFLOWS
from app.pipeline.dispatch import PipelineDispatcher
from app.services.errors import NotFound

router = APIRouter(prefix="/org", tags=["organization"])
DB = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
Dispatcher = Annotated[PipelineDispatcher, Depends(get_dispatcher)]


class TaskCreate(BaseModel):
    workflow: WorkflowType
    input: dict[str, Any]


class Notes(BaseModel):
    notes: str = Field(min_length=3, max_length=5000)


class OptionalNotes(BaseModel):
    notes: str | None = Field(default=None, max_length=5000)


class RevisionIn(BaseModel):
    step_key: str = Field(min_length=1, max_length=60)
    notes: str = Field(min_length=3, max_length=5000)


@router.get("/agents")
def list_agents(_: Analyst, db: DB, settings: SettingsDep) -> list[dict[str, Any]]:
    states = agent_states(db, settings)
    return [{**definition(a), **states[a.key]} for a in AGENTS.values()]


@router.get("/agents/{agent_key}")
def get_agent(agent_key: str, _: Analyst, db: DB, settings: SettingsDep) -> dict[str, Any]:
    if agent_key not in AGENTS:
        raise NotFound("Agent not found.")
    return {**definition(AGENTS[agent_key]), **agent_states(db, settings)[agent_key]}


@router.get("/chart")
def get_chart(_: Analyst, db: DB, settings: SettingsDep) -> dict[str, Any]:
    return org_chart(db, settings)


@router.get("/workflows")
def list_workflows(_: Analyst) -> list[dict[str, Any]]:
    return [
        {
            "workflow": w.type.value,
            "approval": w.approval.value,
            "input_schema": w.input_schema.model_json_schema(),
            "steps": [
                {
                    "key": s.key,
                    "agent": s.agent,
                    "reviewer": s.reviewer.value,
                    "depends_on": list(s.depends_on),
                    "revisable": s.revisable,
                }
                for s in w.steps
            ],
        }
        for w in WORKFLOWS.values()
    ] + [{"supported_languages": SUPPORTED_LANGUAGES}]


@router.post("/tasks", status_code=201)
def create_task(body: TaskCreate, user: Analyst, db: DB, dispatcher: Dispatcher) -> dict:
    task = engine.create_task(db, user, body.workflow, body.input)
    db.commit()
    dispatcher.run_org_task(task.id)
    db.refresh(task)
    return task_summary(task)


@router.get("/tasks")
def list_tasks(_: Analyst, db: DB, status: OrgTaskStatus | None = None) -> list[dict]:
    q = select(OrgTask).order_by(OrgTask.created_at.desc()).limit(200)
    if status:
        q = q.where(OrgTask.status == status)
    return [task_summary(t) for t in db.scalars(q)]


@router.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, _: Analyst, db: DB) -> dict[str, Any]:
    detail = task_detail(db, task_id)
    if detail is None:
        raise NotFound("Task not found.")
    return detail


@router.post("/tasks/{task_id}/approve")
def approve(task_id: uuid.UUID, body: OptionalNotes, user: Reviewer, db: DB) -> dict:
    task = engine.approve(db, task_id, user, body.notes)
    db.commit()
    return task_summary(task)


@router.post("/tasks/{task_id}/reject")
def reject(task_id: uuid.UUID, body: Notes, user: Reviewer, db: DB) -> dict:
    task = engine.reject(db, task_id, user, body.notes)
    db.commit()
    return task_summary(task)


@router.post("/tasks/{task_id}/request-revision")
def request_revision(
    task_id: uuid.UUID, body: RevisionIn, user: Reviewer, db: DB, dispatcher: Dispatcher
) -> dict:
    task = engine.request_revision(db, task_id, user, body.step_key, body.notes)
    db.commit()
    dispatcher.run_org_task(task.id)
    db.refresh(task)
    return task_summary(task)


@router.post("/tasks/{task_id}/retry")
def retry(task_id: uuid.UUID, body: Notes, user: Analyst, db: DB, dispatcher: Dispatcher) -> dict:
    task = engine.retry(db, task_id, user, body.notes)
    db.commit()
    dispatcher.run_org_task(task.id)
    db.refresh(task)
    return task_summary(task)


@router.post("/tasks/{task_id}/cancel")
def cancel(task_id: uuid.UUID, body: Notes, user: Analyst, db: DB) -> dict:
    task = engine.cancel(db, task_id, user, body.notes)
    db.commit()
    return task_summary(task)
