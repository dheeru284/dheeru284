"""Organization read models: agent definitions, live status, performance and the org chart."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    AIRunStatus,
    ExecutionKind,
    ExecutionStatus,
    OrgTaskStatus,
    StepStatus,
)
from app.models import AIRun, OrgApproval, OrgExecution, OrgTask, OrgTaskStep
from app.org.agents import AGENTS, AgentDefinition, chain_of_command, direct_reports
from app.org.policy import MAX_EXECUTIONS_PER_TASK, MAX_HUMAN_REVISIONS, MAX_STEP_RETRIES

WORK_KINDS = (ExecutionKind.EXECUTION, ExecutionKind.REVISION)


def definition(a: AgentDefinition) -> dict[str, Any]:
    return {
        "key": a.key,
        "name": a.name,
        "role": a.role,
        "responsibilities": list(a.responsibilities),
        "manager": a.manager,
        "direct_reports": direct_reports(a.key),
        "chain_of_command": chain_of_command(a.key),
        "input_schema": a.input_schema.model_json_schema(),
        "output_schema": a.output_schema.model_json_schema(),
        "permissions": sorted(p.value for p in a.permissions),
        "tools": list(a.tools),
        "model": a.model.value,
        "max_input_tokens": a.max_input_tokens,
        "max_output_tokens": a.max_output_tokens,
        "max_iterations": a.max_iterations,
        "escalation_rules": [
            {"condition": r.condition.value, "target": r.target.value, "description": r.description}
            for r in a.escalation_rules
        ],
        "pipeline_agents": list(a.pipeline_agents),
        "independent": a.independent,
    }


def _model_label(a: AgentDefinition, settings) -> str:
    if a.model.value == "rules":
        return "rules (deterministic)"
    if settings.llm_provider == "mock":
        return "mock/mock-scripted-v1"
    model = settings.ollama_critic_model if a.model.value == "critic" else None
    return f"ollama/{model or settings.ollama_model}"


def agent_states(session: Session, settings) -> dict[str, dict[str, Any]]:
    """Live status, current task, performance and recent activity for every agent."""
    open_steps = session.execute(
        select(OrgTaskStep, OrgTask)
        .join(OrgTask, OrgTask.id == OrgTaskStep.task_id)
        .where(
            OrgTask.status.notin_(
                [
                    OrgTaskStatus.COMPLETED,
                    OrgTaskStatus.REJECTED,
                    OrgTaskStatus.CANCELLED,
                    OrgTaskStatus.FAILED,
                ]
            )
        )
        .order_by(OrgTask.created_at.desc())
    ).all()
    current: dict[str, tuple[str, dict]] = {}
    priority = {"WORKING": 0, "ESCALATED": 1, "WAITING": 2}
    for step, task in open_steps:
        if step.status in (StepStatus.RUNNING, StepStatus.IN_REVIEW):
            status = "WORKING"
        elif step.status == StepStatus.ESCALATED:
            status = "ESCALATED"
        elif step.status == StepStatus.DONE and task.status == OrgTaskStatus.AWAITING_APPROVAL:
            status = "WAITING"
        else:
            continue
        info = {
            "task_id": str(task.id),
            "title": task.title,
            "step": step.step_key,
            "task_status": task.status.value,
        }
        prev = current.get(step.agent_key)
        if prev is None or priority[status] < priority[prev[0]]:
            current[step.agent_key] = (status, info)

    stats: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(int))
    for agent_key, kind, status, n, latency, ptok, ctok in session.execute(
        select(
            OrgExecution.agent_key,
            OrgExecution.kind,
            OrgExecution.status,
            func.count(),
            func.avg(OrgExecution.latency_ms),
            func.sum(OrgExecution.prompt_tokens),
            func.sum(OrgExecution.completion_tokens),
        ).group_by(OrgExecution.agent_key, OrgExecution.kind, OrgExecution.status)
    ):
        s = stats[agent_key]
        if kind in WORK_KINDS:
            s["executions"] += n
            s["revisions"] += n if kind == ExecutionKind.REVISION else 0
            s["succeeded"] += n if status == ExecutionStatus.SUCCEEDED else 0
            s["failed"] += n if status == ExecutionStatus.FAILED else 0
            s["latency_total"] += (latency or 0) * n
            s["tokens"] += (ptok or 0) + (ctok or 0)
        elif kind == ExecutionKind.REVIEW:
            s["reviews_given"] += n
        elif kind == ExecutionKind.ESCALATION:
            s["escalations"] += n
        elif kind == ExecutionKind.DELEGATION:
            s["delegations"] += n
        elif kind == ExecutionKind.APPROVAL:
            s["approvals"] += n
    pipeline: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for name, status, n in session.execute(
        select(AIRun.agent_name, AIRun.status, func.count()).group_by(
            AIRun.agent_name, AIRun.status
        )
    ):
        pipeline[name][status.value] += n

    recent: dict[str, list[dict]] = defaultdict(list)
    for e, task in session.execute(
        select(OrgExecution, OrgTask)
        .join(OrgTask, OrgTask.id == OrgExecution.task_id)
        .order_by(OrgExecution.seq.desc())
        .limit(400)
    ):
        if len(recent[e.agent_key]) < 5:
            recent[e.agent_key].append(
                {
                    "at": e.created_at.isoformat(),
                    "kind": e.kind.value,
                    "status": e.status.value,
                    "task_id": str(task.id),
                    "task": task.title,
                }
            )

    out = {}
    for a in AGENTS.values():
        s = stats.get(a.key, {})
        executions = s.get("executions", 0)
        pipeline_runs = sum(sum(pipeline[p].values()) for p in a.pipeline_agents)
        pipeline_ok = sum(
            pipeline[p].get(AIRunStatus.SUCCEEDED.value, 0) for p in a.pipeline_agents
        )
        status, task = current.get(a.key, ("IDLE", None))
        out[a.key] = {
            "status": status,
            "current_task": task,
            "model": _model_label(a, settings),
            "performance": {
                "executions": executions,
                "success_rate": round(s.get("succeeded", 0) / executions, 3)
                if executions
                else None,
                "revision_rate": round(s.get("revisions", 0) / executions, 3)
                if executions
                else None,
                "failures": s.get("failed", 0),
                "escalations": s.get("escalations", 0),
                "reviews_given": s.get("reviews_given", 0),
                "delegations": s.get("delegations", 0),
                "approvals": s.get("approvals", 0),
                "mean_latency_ms": int(s["latency_total"] / executions) if executions else None,
                "tokens": s.get("tokens", 0),
                "pipeline_runs": pipeline_runs,
                "pipeline_success_rate": round(pipeline_ok / pipeline_runs, 3)
                if pipeline_runs
                else None,
            },
            "recent_activity": recent.get(a.key, []),
        }
    return out


def org_chart(session: Session, settings) -> dict[str, Any]:
    states = agent_states(session, settings)
    nodes = [
        {
            "id": "human_oversight",
            "kind": "HUMAN",
            "name": "Human oversight",
            "role": "Admins and reviewers: approve public-facing work, resolve escalations.",
            "manager": None,
            "direct_reports": [k for k, a in AGENTS.items() if not a.manager],
        }
    ]
    edges = []
    for a in AGENTS.values():
        nodes.append(
            {
                "id": a.key,
                "kind": "AGENT",
                "name": a.name,
                "role": a.role,
                "manager": a.manager or "human_oversight",
                "direct_reports": direct_reports(a.key),
                "independent": a.independent,
                "max_iterations": a.max_iterations,
                **states[a.key],
            }
        )
        edges.append(
            {
                "id": f"{a.manager or 'human_oversight'}->{a.key}",
                "source": a.manager or "human_oversight",
                "target": a.key,
            }
        )
    open_tasks = session.scalar(
        select(func.count()).where(
            OrgTask.status.in_(
                [
                    OrgTaskStatus.PENDING,
                    OrgTaskStatus.IN_PROGRESS,
                    OrgTaskStatus.AWAITING_APPROVAL,
                    OrgTaskStatus.ESCALATED,
                ]
            )
        )
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "bounds": {
            "max_executions_per_task": MAX_EXECUTIONS_PER_TASK,
            "max_human_revisions": MAX_HUMAN_REVISIONS,
            "max_step_retries": MAX_STEP_RETRIES,
        },
        "open_tasks": open_tasks or 0,
    }


def task_detail(session: Session, task_id: uuid.UUID) -> dict[str, Any] | None:
    task = session.get(OrgTask, task_id)
    if task is None:
        return None
    steps = session.scalars(
        select(OrgTaskStep).where(OrgTaskStep.task_id == task.id).order_by(OrgTaskStep.seq)
    ).all()
    executions = session.scalars(
        select(OrgExecution).where(OrgExecution.task_id == task.id).order_by(OrgExecution.seq)
    ).all()
    step_keys = {s.id: s.step_key for s in steps}
    approvals = session.scalars(
        select(OrgApproval).where(OrgApproval.task_id == task.id).order_by(OrgApproval.created_at)
    ).all()
    return {
        **task_summary(task),
        "input": task.input,
        "output": task.output,
        "steps": [
            {
                "step_key": s.step_key,
                "seq": s.seq,
                "agent_key": s.agent_key,
                "agent_name": AGENTS[s.agent_key].name,
                "delegated_by": s.delegated_by,
                "depends_on": s.depends_on,
                "reviewer": s.reviewer.value,
                "status": s.status.value,
                "iterations": s.iterations,
                "max_iterations": AGENTS[s.agent_key].max_iterations,
                "retries": s.retries,
                "output": s.output,
                "feedback": s.feedback,
                "escalation": s.escalation,
            }
            for s in steps
        ],
        "executions": [
            {
                "id": str(e.id),
                "kind": e.kind.value,
                "status": e.status.value,
                "agent_key": e.agent_key,
                "step_id": str(e.step_id) if e.step_id else None,
                "step_key": step_keys.get(e.step_id),
                "iteration": e.iteration,
                "input": e.input,
                "output": e.output,
                "tool_calls": e.tool_calls,
                "ai_run_id": str(e.ai_run_id) if e.ai_run_id else None,
                "model": e.model,
                "prompt_tokens": e.prompt_tokens,
                "completion_tokens": e.completion_tokens,
                "latency_ms": e.latency_ms,
                "error": e.error,
                "at": e.created_at.isoformat(),
            }
            for e in executions
        ],
        "approvals": [
            {
                "approver_type": a.approver_type.value,
                "approver": str(a.approver_user_id) if a.approver_user_id else a.approver_agent,
                "decision": a.decision.value,
                "target_step": a.target_step,
                "notes": a.notes,
                "at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
    }


def task_summary(task: OrgTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "workflow": task.workflow.value,
        "title": task.title,
        "status": task.status.value,
        "approval_level": task.approval_level.value,
        "executions_used": task.executions_used,
        "max_executions": MAX_EXECUTIONS_PER_TASK,
        "human_revisions": task.human_revisions,
        "escalation_reason": task.escalation_reason,
        "created_by_id": str(task.created_by_id),
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
